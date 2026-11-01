"""Command-line operations for the local PathAid foundation."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from .config import Settings
from .local_data import backup_database, reset_local_data, restore_database, upgrade_database, validate_database
from .secrets import GEMINI_API_KEY, KeychainSecretStore, get_or_create_document_key, get_or_create_extension_token


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
