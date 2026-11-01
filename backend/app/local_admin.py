"""Command-line operations for the local PathAid foundation."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from .config import Settings
from .database import Database
from .local_data import backup_database, reset_local_data, restore_database, upgrade_database, validate_database
from .secrets import GEMINI_API_KEY, KeychainSecretStore, get_or_create_document_key, get_or_create_extension_token
from .source_registry import import_ipeds_directory
from .source_scanning import execute_registered_scan


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Manage local PathAid data")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create secrets and migrate SQLite")
    backup = commands.add_parser("backup", help="create a consistent database backup")
    backup.add_argument("destination", type=Path)
    restore = commands.add_parser("restore", help="restore a verified database backup")
    restore.add_argument("source", type=Path)
    reset = commands.add_parser("reset", help="delete local PathAid data and secrets")
    reset.add_argument("--yes", action="store_true", help="confirm destructive reset")
    commands.add_parser("set-gemini-key", help="save a Gemini key in macOS Keychain")
    commands.add_parser("status", help="validate the local database")
    institutions = commands.add_parser("import-institutions", help="import an official NCES IPEDS HD directory CSV")
    institutions.add_argument("source", type=Path)
    institutions.add_argument("--year", type=int, required=True)
    scan = commands.add_parser("scan-source", help="run one confirmed source with its registered adapter")
    scan.add_argument("source_id")
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
        backup_database(settings.database_path, args.destination)
        print(f"Backup created at {args.destination.expanduser().resolve()}")
    elif args.command == "restore":
        restore_database(args.source, settings.database_path)
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
    elif args.command == "status":
        validate_database(settings.database_path)
        print("PathAid database is current and passes its integrity check.")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
