"""Command-line operations for the local PathAid foundation."""

from __future__ import annotations

import argparse
import getpass
import subprocess
from pathlib import Path

from sqlalchemy import select

from .config import Settings
from .database import Database
from .local_data import backup_database, reset_local_data, restore_database, upgrade_database, validate_database
from .secrets import DOCUMENT_KEY, EXTENSION_TOKEN, GEMINI_API_KEY, KeychainSecretStore, get_or_create_document_key, get_or_create_extension_token
from .scheduler import local_provider_factory, run_scheduler_cycle
from .models import DiscoveryJob
from .source_registry import import_ipeds_directory
from .source_scanning import execute_registered_scan


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Manage local PathAid data")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create secrets and migrate SQLite")
    backup = commands.add_parser("backup", help="create a versioned encrypted backup")
    backup.add_argument("destination", type=Path)
    restore = commands.add_parser("restore", help="restore a verified encrypted backup")
    restore.add_argument("source", type=Path)
    reset = commands.add_parser("reset", help="delete local PathAid data and secrets")
    reset.add_argument("--yes", action="store_true", help="confirm destructive reset")
    commands.add_parser("set-gemini-key", help="save a Gemini key in macOS Keychain")
    commands.add_parser("copy-extension-token", help="copy the extension token to the macOS clipboard")
    commands.add_parser("status", help="validate the local database")
    institutions = commands.add_parser("import-institutions", help="import an official NCES IPEDS HD directory CSV")
    institutions.add_argument("source", type=Path)
    institutions.add_argument("--year", type=int, required=True)
    scan = commands.add_parser("scan-source", help="run one confirmed source with its registered adapter")
    scan.add_argument("source_id")
    commands.add_parser("scheduler-once", help="enqueue due sources and drain one local scheduler cycle")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = Settings.from_env()
    store = KeychainSecretStore(settings.keychain_service)
    if args.command == "init":
        upgrade_database(settings)
        get_or_create_extension_token(store)
        get_or_create_document_key(store)
        print("PathAid local data and Keychain secrets are initialized.")
    elif args.command == "backup":
        passphrase = getpass.getpass("New backup passphrase (12+ characters): ")
        confirmation = getpass.getpass("Confirm backup passphrase: ")
        if passphrase != confirmation:
            raise SystemExit("Backup passphrases do not match")
        backup_database(settings.database_path, args.destination, passphrase=passphrase)
        print(f"Backup created at {args.destination.expanduser().resolve()}")
    elif args.command == "restore":
        passphrase = getpass.getpass("Backup passphrase: ")
        restore_database(args.source, settings.database_path, passphrase=passphrase)
        print("Backup restored.")
    elif args.command == "reset":
        reset_local_data(settings, store, confirmed=args.yes)
        print("PathAid local data and managed Keychain secrets were removed.")
    elif args.command == "set-gemini-key":
        value = getpass.getpass("Gemini API key: ").strip()
        if not value:
            raise SystemExit("Gemini API key cannot be empty")
        store.set(GEMINI_API_KEY, value)
        print("Gemini API key saved in macOS Keychain.")
    elif args.command == "copy-extension-token":
        copy_extension_token_to_clipboard(store)
        print("Extension token copied to the clipboard. It was not printed.")
    elif args.command == "status":
        validate_database(settings.database_path)
        database = Database(settings)
        try:
            with database.sessions() as db:
                latest_job = db.scalar(select(DiscoveryJob).order_by(DiscoveryJob.created_at.desc()).limit(1))
        finally:
            database.close()
        print("Database: current and integrity-checked")
        print(f"Gemini: {'configured' if store.get(GEMINI_API_KEY) else 'not configured'}")
        print(f"Extension token: {'available' if store.get(EXTENSION_TOKEN) else 'missing'}")
        print(f"Document vault key: {'available' if store.get(DOCUMENT_KEY) else 'missing'}")
        if latest_job is None:
            print("Latest discovery job: none")
        else:
            print(f"Latest discovery job: {latest_job.status} ({latest_job.stage})")
    elif args.command == "import-institutions":
        upgrade_database(settings)
        database = Database(settings)
        try:
            with database.sessions.begin() as db:
                count = import_ipeds_directory(db, args.source, source_year=args.year)
        finally:
            database.close()
        print(f"Imported {count} NCES IPEDS institutions for {args.year}.")
    elif args.command == "scan-source":
        upgrade_database(settings)
        database = Database(settings)
        try:
            run = execute_registered_scan(database, args.source_id)
        finally:
            database.close()
        print(
            f"Scan {run.status}: {run.pages_attempted} pages, "
            f"{run.snapshots_created} new snapshots, {run.unchanged_pages} unchanged."
        )
        if run.status == "failed":
            print(f"Safe error code: {run.error_code}")
            return 1
    elif args.command == "scheduler-once":
        upgrade_database(settings)
        database = Database(settings)
        try:
            count = run_scheduler_cycle(
                database, worker_id="local-admin",
                provider_factory=local_provider_factory(store),
            )
        finally:
            database.close()
        print(f"Scheduler cycle processed {count} job(s).")
    return 0


def copy_extension_token_to_clipboard(store, *, runner=subprocess.run) -> None:
    """Transfer the Keychain token without exposing it in terminal output."""

    token = get_or_create_extension_token(store)
    try:
        runner(["pbcopy"], input=token, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit("Could not copy the extension token with macOS pbcopy") from error


if __name__ == "__main__":
    raise SystemExit(main())
