"""Local-only FastAPI foundation for the PathAid desktop companion."""

from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .database import Database
from .document_api import create_document_router
from .essay_api import create_essay_router
from .essay_recommendation import EssayAnalysisProvider
from .extension_api import create_extension_router
from .home_api import create_home_router
from .local_data import EXPECTED_MIGRATION, REQUIRED_TABLES
from .profile_api import create_profile_router
from .saved_api import create_saved_router
from .scheduler import SchedulerThread
from .settings_api import create_settings_router
from .secrets import KeychainSecretStore, SecretStore, SecretStoreError, get_or_create_extension_token
from .source_api import create_source_router


def create_app(
    settings: Settings | None = None,
    secret_store: SecretStore | None = None,
    essay_provider_factory: Callable[[str], EssayAnalysisProvider] | None = None,
) -> FastAPI:
    """Build an app whose database and secret boundaries can be isolated in tests."""

    settings = settings or Settings.from_env()
    database = Database(settings)
    secret_store = secret_store or KeychainSecretStore(settings.keychain_service)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.prepare_directories()
        scheduler = SchedulerThread(database, secret_store)
        scheduler.start()
        try:
            yield
        finally:
            scheduler.stop()
            database.close()

    application = FastAPI(title="PathAid Local API", version="0.1.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.database = database
    application.state.secret_store = secret_store
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver", "api"])
    allowed_origins = [settings.web_origin]
    if settings.extension_origin:
        allowed_origins.append(settings.extension_origin)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-PathAid-Token", "Content-Type"],
    )
    application.include_router(create_profile_router(database))
    application.include_router(create_saved_router(database))
    application.include_router(create_source_router(database))
    application.include_router(create_document_router(database, secret_store))
    application.include_router(create_essay_router(database, secret_store, essay_provider_factory))
    application.include_router(create_settings_router(settings, secret_store))
    application.include_router(create_home_router(database, secret_store))

    def get_db() -> Session:
        yield from database.session()

    @application.exception_handler(RequestValidationError)
    async def safe_validation_error(_request: Request, error: RequestValidationError):
        fields = sorted({str(item["loc"][-1]) for item in error.errors() if item.get("loc")})
        return JSONResponse(status_code=422, content={"detail": {"fields": fields, "message": "Invalid request"}})

    @application.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "live"}

    @application.get("/health/ready")
    def readiness(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
        try:
            db.execute(text("SELECT 1"))
            available = set(inspect(db.get_bind()).get_table_names())
            version = db.scalar(text("SELECT version_num FROM alembic_version")) if "alembic_version" in available else None
            journal_mode = str(db.scalar(text("PRAGMA journal_mode"))).casefold()
            foreign_keys = db.scalar(text("PRAGMA foreign_keys"))
        except SQLAlchemyError:
            response.status_code = 503
            return {"status": "not_ready", "reason": "database_unavailable"}
        if not REQUIRED_TABLES.issubset(available) or version != EXPECTED_MIGRATION:
            response.status_code = 503
            return {"status": "not_ready", "reason": "database_migration_required"}
        if journal_mode != "wal" or foreign_keys != 1:
            response.status_code = 503
            return {"status": "not_ready", "reason": "database_configuration_invalid"}
        return {"status": "ready"}

    @application.get("/api/local/status")
    def local_status() -> dict[str, object]:
        """Expose non-secret local configuration for the web interface."""

        return {
            "mode": "local_single_user",
            "database": "sqlite",
            "extension_configured": settings.extension_origin is not None,
            "extension_id": settings.extension_id,
        }

    def require_extension(
        request: Request,
        x_pathaid_token: str | None = Header(default=None, alias="X-PathAid-Token"),
    ) -> None:
        expected_origin = settings.extension_origin
        if expected_origin is None:
            raise HTTPException(503, detail="Chrome extension is not configured")
        if request.headers.get("origin") != expected_origin:
            raise HTTPException(403, detail="Extension origin not allowed")
        try:
            expected_token = get_or_create_extension_token(secret_store)
        except SecretStoreError as error:
            raise HTTPException(503, detail="Local secret storage is unavailable") from error
        if x_pathaid_token is None or not hmac.compare_digest(x_pathaid_token, expected_token):
            raise HTTPException(401, detail="Invalid extension token")

    @application.get("/api/extension/ping", dependencies=[Depends(require_extension)])
    def extension_ping() -> dict[str, str]:
        """Prove the narrow extension authentication boundary without private data."""

        return {"status": "connected"}

    application.include_router(create_extension_router(database, require_extension, secret_store))

    return application


app = create_app()
