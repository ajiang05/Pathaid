"""Secret storage boundary backed by macOS Keychain in production."""

from __future__ import annotations

import secrets
from typing import Protocol


GEMINI_API_KEY = "gemini-api-key"
EXTENSION_TOKEN = "extension-installation-token"
DOCUMENT_KEY = "document-encryption-key"
MANAGED_SECRET_NAMES = (GEMINI_API_KEY, EXTENSION_TOKEN, DOCUMENT_KEY)


class SecretStoreError(RuntimeError):
    """Raised when the OS secret service cannot complete an operation."""


class SecretStore(Protocol):
    """Small interface that keeps secret storage replaceable in tests."""

    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class KeychainSecretStore:
    """Store PathAid secrets through Python keyring's macOS Keychain backend."""

    def __init__(self, service: str):
        self.service = service

    @staticmethod
    def _keyring():
        try:
            import keyring
        except ImportError as error:  # pragma: no cover
            raise SecretStoreError("The keyring package is not installed") from error
        return keyring

    def get(self, name: str) -> str | None:
        try:
            return self._keyring().get_password(self.service, name)
        except Exception as error:
            raise SecretStoreError("macOS Keychain is unavailable") from error

    def set(self, name: str, value: str) -> None:
        if not value:
            raise ValueError("Secret values cannot be empty")
        try:
            self._keyring().set_password(self.service, name, value)
        except Exception as error:
            raise SecretStoreError("Could not save a secret in macOS Keychain") from error

    def delete(self, name: str) -> None:
        keyring = self._keyring()
        try:
            keyring.delete_password(self.service, name)
        except keyring.errors.PasswordDeleteError:
            return
        except Exception as error:
            raise SecretStoreError("Could not remove a secret from macOS Keychain") from error


def get_or_create_extension_token(store: SecretStore) -> str:
    """Return the stable installation token, creating a strong token once."""

    existing = store.get(EXTENSION_TOKEN)
    if existing:
        return existing
    token = secrets.token_urlsafe(48)
    store.set(EXTENSION_TOKEN, token)
    return token


def get_or_create_document_key(store: SecretStore) -> str:
    """Return a stable 256-bit document key encoded for future vault use."""

    existing = store.get(DOCUMENT_KEY)
    if existing:
        return existing
    key = secrets.token_urlsafe(32)
    store.set(DOCUMENT_KEY, key)
    return key
