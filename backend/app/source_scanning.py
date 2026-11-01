"""Dispatch one confirmed source to its registered public acquisition adapter."""

from __future__ import annotations

from .academicworks import execute_academicworks_scan
from .database import Database
from .generic_directory import execute_generic_scan
from .models import SourceScope
from .source_registry import RegistryError


def execute_registered_scan(database: Database, source_id: str):
    with database.sessions() as db:
        scope = db.get(SourceScope, source_id)
        if scope is None:
            raise RegistryError("source_not_found", "Source not found.")
        adapter = scope.adapter
    if adapter == "generic":
        return execute_generic_scan(database, source_id)
    if adapter == "academicworks":
        return execute_academicworks_scan(database, source_id)
    raise RegistryError("adapter_not_implemented", "The registered source adapter is not implemented yet.")
