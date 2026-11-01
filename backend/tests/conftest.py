"""Shared local-foundation test doubles."""

from __future__ import annotations


class FakeSecretStore:
    """In-memory secret store that records deletion without touching Keychain."""

    def __init__(self, values: dict[str, str] | None = None):
        self.values = dict(values or {})
        self.deleted: list[str] = []

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)
        self.deleted.append(name)
