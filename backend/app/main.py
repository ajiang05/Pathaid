"""FastAPI routes and security helpers for student accounts and profiles."""

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .catalog import get_published_revision, list_published_revisions
from .catalog_schemas import ProgramDetail, ProgramSummary, SourceReference
from .database import get_db
from .discovery import RankingRecord, rank_records
from .eligibility import RuleValidationError, evaluate_eligibility
from .evaluation_schemas import (
    CriterionResponse,
    EvaluationRequest,
    EvaluationResponse,
    MissingFieldResponse,
    ProgramEvaluationResponse,
)
from .models import AuthAttempt, ProgramRevision, Student, StudentSession
from .profile_fields import FIELDS, validate_profile_patch


# The FastAPI object connects route decorators below to the ASGI application.
app = FastAPI(title="Pathaid API")
COOKIE_NAME = "pathaid_session"
SESSION_DAYS = 7
# This is a deliberately small syntax check, not an attempt to determine
# whether an address or its mail server actually exists.
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@app.exception_handler(RequestValidationError)
def safe_validation_error(_request: Request, error: RequestValidationError):
    """Return field names without echoing rejected profile or auth values."""

    # FastAPI's default validation response can include the submitted value.
    # Returning only locations still tells a client what needs correction.
    fields = sorted({str(item["loc"][-1]) for item in error.errors() if item.get("loc")})
    return JSONResponse(status_code=422, content={"detail": {"fields": fields, "message": "Invalid request"}})


class Credentials(BaseModel):
    """Request body accepted by both sign-up and login routes."""

    # Reject misspelled or unexpected properties rather than ignoring them.
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=256)


class ProfilePatch(BaseModel):
    """Partial saved-profile update plus the student's AI consent choice."""

    model_config = ConfigDict(extra="forbid")
    fields: dict
    ai_opt_in: bool | None = None


def program_summary(revision: ProgramRevision) -> ProgramSummary:
    """Convert an internal revision into its stable public list contract."""

    return ProgramSummary(
        id=revision.program_id,
        revision_id=revision.id,
        slug=revision.program.slug,
        name=revision.name,
        description=revision.description,
        categories=revision.categories,
        coverage=revision.coverage,
        assistance_amount=revision.assistance_amount,
        application_deadline=revision.application_deadline,
        deadline_timezone=revision.deadline_timezone,
        application_availability=revision.application_availability,
        verified_at=revision.verified_at,
    )


def program_detail(revision: ProgramRevision) -> ProgramDetail:
    """Convert a revision to detail output while omitting retained source text."""

    summary = program_summary(revision).model_dump()
    return ProgramDetail(
        **summary,
        checklist=revision.checklist,
        eligibility_tree=revision.eligibility_tree,
        coverage_complete=revision.coverage_complete,
        award_cycle=revision.award_cycle,
        selection_factors=revision.selection_factors,
        provider_url=revision.provider_url,
        application_url=revision.application_url,
        sources=[
            SourceReference(
                id=source.id,
                source_url=source.source_url,
                acquired_at=source.acquired_at,
                acquisition_method=source.acquisition_method,
            )
            for source in revision.sources
        ],
    )


def missing_field_response(field_name: str) -> MissingFieldResponse:
    """Convert registry metadata into a safe follow-up question contract."""

    spec = FIELDS[field_name]
    return MissingFieldResponse(
        field=field_name,
        question=spec["question"],
        answer_type=spec["type"],
        values=spec.get("values"),
        sensitive=spec["sensitive"],
    )


def evaluate_revision(revision: ProgramRevision, profile: dict) -> ProgramEvaluationResponse:
    """Evaluate and serialize one exact published program revision."""

    evaluated = evaluate_eligibility(
        revision_id=revision.id,
        rule=revision.eligibility_tree,
        profile=profile,
        field_registry=FIELDS,
        coverage_complete=revision.coverage_complete,
    )
    return ProgramEvaluationResponse(
        program_id=revision.program_id,
        revision_id=revision.id,
        name=revision.name,
        label=evaluated.label.value,
        truth=evaluated.truth.value,
        criteria=[
            CriterionResponse(
                field=criterion.field,
                operator=criterion.operator,
                truth=criterion.truth.value,
                reason=criterion.reason,
                answerable=criterion.answerable,
                evidence=dict(criterion.evidence),
            )
            for criterion in evaluated.criteria
        ],
        missing_fields=[missing_field_response(field_name) for field_name in evaluated.missing_fields],
        unresolved_conditions=list(evaluated.unresolved_conditions),
        application_availability=revision.application_availability,
        application_deadline=revision.application_deadline.isoformat() if revision.application_deadline else None,
        deadline_timezone=revision.deadline_timezone,
        coverage=revision.coverage,
    )


def now() -> datetime:
    """Return an aware UTC time for consistent expiry comparisons."""

    return datetime.now(timezone.utc)


def digest(value: str) -> str:
    """Create a fixed-length one-way digest for tokens and addresses."""

    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str) -> str:
    """Hash a password with a random salt and the memory-hard scrypt KDF."""

    # A unique salt prevents equal passwords from producing equal stored
    # hashes. The encoded result retains the parameters needed for verification.
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against its encoded scrypt hash safely."""

    try:
        # Reuse the work parameters stored with the hash so they can be changed
        # for newly created accounts later without breaking existing accounts.
        _, n, r, p, salt, expected = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        # Constant-time comparison avoids leaking where two hashes differ.
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def normalize_email(value: str) -> str:
    """Normalize an email used as a login identifier and check its shape."""

    email = value.strip().casefold()
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(422, detail={"field": "email", "message": "Invalid email"})
    return email


def check_origin(request: Request) -> None:
    """Reject browser mutations coming from an unexpected web origin."""

    # This supplements the CSRF token. PATHAID_PUBLIC_ORIGIN should be set to
    # the deployed frontend origin, such as https://pathaid.example.
    allowed = os.environ.get("PATHAID_PUBLIC_ORIGIN")
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site" or (origin and allowed and origin != allowed):
        raise HTTPException(403, detail="Origin not allowed")


def address_key(request: Request) -> str:
    """Return a privacy-reduced key for per-address rate limiting."""

    # Only the direct peer address is trusted. Proxy forwarding headers are ignored.
    address = request.client.host if request.client else "unknown"
    return digest(address)


def check_rate_limit(db: Session, request: Request) -> None:
    """Reject an address after ten auth requests in a fifteen-minute window."""

    cutoff = now() - timedelta(minutes=15)
    address = address_key(request)
    attempts = db.scalar(select(func.count()).select_from(AuthAttempt).where(AuthAttempt.address == address, AuthAttempt.created_at >= cutoff))
    if attempts >= 10:
        raise HTTPException(429, detail="Too many authentication attempts")


def record_attempt(db: Session, request: Request) -> None:
    """Store an auth request and remove expired records for this address."""

    # Opportunistic cleanup keeps the table bounded without a separate worker.
    db.execute(delete(AuthAttempt).where(AuthAttempt.address == address_key(request), AuthAttempt.created_at < now() - timedelta(minutes=15)))
    db.add(AuthAttempt(address=address_key(request), created_at=now()))
    db.commit()


def issue_session(db: Session, student: Student, response: Response) -> dict:
    """Create a database session and attach its opaque token as a cookie."""

    # The raw session token goes only to the HttpOnly cookie. JavaScript cannot
    # read that cookie, and the database retains only its digest.
    token = secrets.token_urlsafe(32)
    # The CSRF token is deliberately readable by the client, which sends it in
    # a custom header for profile mutations and logout.
    csrf = secrets.token_urlsafe(32)
    db.add(StudentSession(token_hash=digest(token), student_id=student.id, csrf_hash=digest(csrf), expires_at=now() + timedelta(days=SESSION_DAYS)))
    db.commit()
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True,
        # Production must enable Secure so browsers send this cookie via HTTPS
        # only. Local HTTP development can leave it disabled.
        secure=os.environ.get("PATHAID_SECURE_COOKIES", "false").lower() == "true",
        samesite="lax", path="/api",
    )
    return {"id": student.id, "csrf_token": csrf}


def current_session(request: Request, db: Session = Depends(get_db)) -> tuple[Student, StudentSession]:
    """Resolve the cookie to its authenticated student and session record."""

    token = request.cookies.get(COOKIE_NAME)
    # Hash the browser's token before looking it up because raw tokens are never
    # stored in the database.
    session = db.get(StudentSession, digest(token)) if token else None
    expiry = session.expires_at if session is not None else None
    # SQLite can return a naive datetime even for timezone-aware columns. Treat
    # that local-development value as UTC so it compares correctly.
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if session is None or expiry <= now():
        raise HTTPException(401, detail="Authentication required")
    student = db.get(Student, session.student_id)
    if student is None:
        raise HTTPException(401, detail="Authentication required")
    return student, session


def require_csrf(request: Request, identity: tuple[Student, StudentSession] = Depends(current_session)) -> tuple[Student, StudentSession]:
    """Require both a valid login cookie and matching CSRF header."""

    check_origin(request)
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(digest(supplied), identity[1].csrf_hash):
        raise HTTPException(403, detail="CSRF token required")
    return identity


@app.get("/api/profile-fields")
def profile_fields():
    """Expose question metadata without requiring a student account."""

    # None is the wire representation of an unanswered or unknown value.
    return {"fields": FIELDS, "unknown_answer": None}


@app.get("/api/programs", response_model=list[ProgramSummary])
def programs(
    categories: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """List current published revisions, optionally filtered by category."""

    requested = categories or []
    unknown = sorted(set(requested).difference(FIELDS["assistance_categories"]["values"]))
    if unknown:
        # Return field names rather than reflecting arbitrary submitted values.
        raise HTTPException(422, detail={"field": "categories", "message": "Invalid category"})
    return [program_summary(revision) for revision in list_published_revisions(db, categories=requested)]


@app.get("/api/programs/{program_id}", response_model=ProgramDetail)
def program(program_id: str, db: Session = Depends(get_db)):
    """Return the current published detail for one stable program ID."""

    revision = get_published_revision(db, program_id)
    if revision is None:
        # Draft-only, rejected, unknown, and malformed pointers all look absent
        # through the public endpoint.
        raise HTTPException(404, detail="Program not found")
    return program_detail(revision)


@app.post("/api/evaluate", response_model=EvaluationResponse)
def evaluate_programs(
    body: EvaluationRequest,
    request: Request,
    identity: tuple[Student, StudentSession] = Depends(current_session),
    db: Session = Depends(get_db),
):
    """Evaluate published candidates without persisting temporary answers."""

    check_origin(request)
    student = identity[0]
    # Validation returns a new dictionary; it never mutates the JSON profile
    # currently attached to the authenticated student record.
    combined_profile = validate_profile_patch(body.answers, student.profile)
    categories = body.categories or combined_profile.get("assistance_categories", [])
    allowed_categories = set(FIELDS["assistance_categories"]["values"])
    if not categories or any(category not in allowed_categories for category in categories) or len(set(categories)) != len(categories):
        raise HTTPException(422, detail={"field": "categories", "message": "Invalid category selection"})

    candidates = list_published_revisions(db, categories=categories)
    try:
        evaluated_by_id = {
            revision.program_id: evaluate_revision(revision, combined_profile)
            for revision in candidates
        }
    except RuleValidationError:
        # Invalid rule trees should be blocked before publication. Avoid
        # exposing internal catalog content if that invariant is ever broken.
        raise HTTPException(500, detail="A published program cannot be evaluated") from None
    ranked = rank_records(
        [
            RankingRecord(
                program_id=revision.program_id,
                name=revision.name,
                eligibility_label=evaluated_by_id[revision.program_id].label,
                application_availability=revision.application_availability,
                application_deadline=revision.application_deadline,
                coverage=revision.coverage,
            )
            for revision in candidates
        ],
        combined_profile,
    )
    results: list[ProgramEvaluationResponse] = []
    for ranked_record in ranked:
        result = evaluated_by_id[ranked_record.record.program_id]
        result.availability_section = ranked_record.section
        result.relevance = ranked_record.relevance
        result.ranking_factors = dict(ranked_record.ranking_factors)
        results.append(result)
    return EvaluationResponse(categories=categories, results=results)


@app.post("/api/auth/signup", status_code=201)
def signup(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create a student account and immediately start its first session."""

    check_origin(request)
    check_rate_limit(db, request)
    email = normalize_email(body.email)
    student = Student(email=email, password_hash=password_hash(body.password), profile={})
    db.add(student)
    try:
        # The database unique constraint is the final defense against duplicate
        # sign-ups that arrive concurrently.
        db.commit()
    except IntegrityError:
        db.rollback()
        record_attempt(db, request)
        raise HTTPException(409, detail="Account already exists") from None
    db.refresh(student)
    record_attempt(db, request)
    return issue_session(db, student, response)


@app.post("/api/auth/login")
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    """Verify credentials and issue a new revocable login session."""

    check_origin(request)
    check_rate_limit(db, request)
    email = normalize_email(body.email)
    student = db.scalar(select(Student).where(Student.email == email))
    # Use the same response for unknown email and wrong password so the endpoint
    # does not reveal which email addresses have accounts.
    if student is None or not verify_password(body.password, student.password_hash):
        record_attempt(db, request)
        raise HTTPException(401, detail="Invalid credentials")
    return issue_session(db, student, response)


@app.get("/api/auth/session")
def session_info(request: Request, identity: tuple[Student, StudentSession] = Depends(current_session), db: Session = Depends(get_db)):
    """Confirm login and rotate the CSRF token after a page reload."""

    # A fresh token on reload avoids storing CSRF tokens in browser storage.
    check_origin(request)
    csrf = secrets.token_urlsafe(32)
    identity[1].csrf_hash = digest(csrf)
    db.commit()
    return {"id": identity[0].id, "authenticated": True, "csrf_token": csrf}


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response, identity: tuple[Student, StudentSession] = Depends(require_csrf), db: Session = Depends(get_db)):
    """Revoke the current server-side session and clear its browser cookie."""

    db.delete(identity[1])
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/api")


@app.get("/api/profile")
def get_profile(identity: tuple[Student, StudentSession] = Depends(current_session)):
    """Return only the profile belonging to the authenticated student."""

    student = identity[0]
    return {"fields": student.profile, "ai_opt_in": student.ai_opt_in}


@app.patch("/api/profile")
def patch_profile(body: ProfilePatch, identity: tuple[Student, StudentSession] = Depends(require_csrf), db: Session = Depends(get_db)):
    """Validate and save a partial update to the current student's profile."""

    student = identity[0]
    student.profile = validate_profile_patch(body.fields, student.profile)
    if body.ai_opt_in is not None:
        student.ai_opt_in = body.ai_opt_in
    db.commit()
    return {"fields": student.profile, "ai_opt_in": student.ai_opt_in}


@app.delete("/api/profile", status_code=204)
def delete_account(response: Response, identity: tuple[Student, StudentSession] = Depends(require_csrf), db: Session = Depends(get_db)):
    """Delete the authenticated account, profile, and related sessions."""

    # The ORM relationship and database foreign key cascade remove sessions.
    db.delete(identity[0])
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/api")
