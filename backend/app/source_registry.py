"""Validation and state transitions for user-approved scholarship sources."""

from __future__ import annotations

import csv
import posixpath
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from sqlalchemy import Text, or_, select, update
from sqlalchemy.orm import Session

from .models import Institution, LocalProfile, ManualLead, SourcePolicyAssessment, SourceScope
from .source_acquisition import AcquisitionError, ValidatedUrl, validate_source_url


MANUAL_ONLY_HOSTS = ("bigfuture.collegeboard.org", "scholarshipamerica.org", "bold.org")


class RegistryError(ValueError):
    """Value-free source-registry failure suitable for the local API."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.safe_message = message
        super().__init__(message)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _host_is(hostname: str, boundary: str) -> bool:
    return hostname == boundary or hostname.endswith(f".{boundary}")


def _validated(raw_url: str) -> ValidatedUrl:
    try:
        return validate_source_url(raw_url)
    except AcquisitionError as error:
        raise RegistryError(error.code, error.safe_message) from error


def normalize_path_prefix(raw_prefix: str) -> str:
    """Return one absolute decoded path boundary without widening it."""

    if not isinstance(raw_prefix, str) or not raw_prefix.startswith("/") or "?" in raw_prefix or "#" in raw_prefix:
        raise RegistryError("invalid_path_prefix", "An absolute path prefix is required.")
    decoded = unquote(raw_prefix)
    if "\x00" in decoded or "\\" in decoded or any(segment == ".." for segment in decoded.split("/")):
        raise RegistryError("invalid_path_prefix", "The path prefix is unsafe.")
    normalized = posixpath.normpath(decoded)
    if normalized == ".":
        normalized = "/"
    if not normalized.startswith("/") or normalized.startswith("//"):
        raise RegistryError("invalid_path_prefix", "The path prefix is unsafe.")
    return normalized if normalized == "/" else normalized.rstrip("/")


def path_is_within(path: str, prefix: str) -> bool:
    """Match an exact prefix segment, never a coincidental string prefix."""

    normalized_path = posixpath.normpath(unquote(path or "/"))
    return prefix == "/" or normalized_path == prefix or normalized_path.startswith(f"{prefix}/")


def scope_allows_url(scope: SourceScope, raw_url: str) -> bool:
    """Enforce both the confirmed hostname and path boundary."""

    try:
        candidate = _validated(raw_url)
    except RegistryError:
        return False
    return candidate.hostname == scope.hostname and path_is_within(urlsplit(candidate.url).path, scope.allowed_path_prefix)


def manual_only_host(hostname: str) -> bool:
    """Return whether a host may supply leads but never official evidence."""

    return any(_host_is(hostname, boundary) for boundary in MANUAL_ONLY_HOSTS)


def _official_school_host(institution: Institution, hostname: str) -> bool:
    if not institution.website_url:
        return False
    official = _validated(institution.website_url).hostname
    institutional_domain = official.removeprefix("www.")
    return hostname == official or hostname == institutional_domain or hostname.endswith(f".{institutional_domain}")


def create_scope_proposal(
    db: Session,
    *,
    name: str,
    ownership: str,
    adapter: str,
    canonical_url: str,
    allowed_path_prefix: str,
    institution_unit_id: str | None,
    max_depth: int,
    page_budget: int,
    requests_per_minute: int,
    scan_interval_hours: int,
) -> SourceScope:
    """Create an inert proposal; confirmation is a separate operation."""

    validated = _validated(canonical_url)
    if urlsplit(validated.url).query:
        raise RegistryError("invalid_scope_url", "Directory scope URLs cannot contain a query string.")
    prefix = normalize_path_prefix(allowed_path_prefix)
    if not path_is_within(urlsplit(validated.url).path, prefix):
        raise RegistryError("scope_mismatch", "The directory URL is outside the requested path prefix.")
    if manual_only_host(validated.hostname):
        raise RegistryError("manual_only_source", "This provider can be saved only as an individual lead.")
    if ownership not in {"school", "sponsor"} or adapter not in {"generic", "academicworks", "kaleidoscope"}:
        raise RegistryError("invalid_scope", "The source type or adapter is unsupported.")
    if adapter == "academicworks" and (prefix != "/" or urlsplit(validated.url).path.rstrip("/") not in {"", "/opportunities"}):
        raise RegistryError("invalid_adapter_boundary", "AcademicWorks requires an explicitly confirmed root path and public listing URL.")
    if adapter == "kaleidoscope" and (
        validated.hostname != "apply.mykaleidoscope.com"
        or prefix != "/"
        or urlsplit(validated.url).path.rstrip("/") != ""
        or ownership != "sponsor"
    ):
        raise RegistryError("invalid_adapter_boundary", "Kaleidoscope requires its explicitly confirmed public marketplace root as a sponsor source.")
    profile = db.get(LocalProfile, 1)
    institution = db.get(Institution, institution_unit_id) if institution_unit_id else None
    if ownership == "school":
        if institution is None or profile is None or profile.data.get("school_id") != institution.unit_id:
            raise RegistryError("school_mismatch", "School sources must belong to the currently selected institution.")
        if adapter == "generic" and not _official_school_host(institution, validated.hostname):
            raise RegistryError("unofficial_school_host", "A generic school source must use the institution's official host.")
    elif institution_unit_id is not None:
        raise RegistryError("invalid_ownership", "Sponsor sources cannot claim school ownership.")
    if not 0 <= max_depth <= 2 or not 1 <= page_budget <= 100 or not 1 <= requests_per_minute <= 60 or not 6 <= scan_interval_hours <= 720:
        raise RegistryError("invalid_limits", "Source limits are outside the supported bounds.")
    return SourceScope(
        id=str(uuid4()), name=name.strip(), ownership=ownership, adapter=adapter,
        canonical_url=validated.url, hostname=validated.hostname, allowed_path_prefix=prefix,
        institution_unit_id=institution_unit_id, school_revision=profile.school_revision if ownership == "school" else None,
        status="proposed", confirmed_at=None, max_depth=max_depth, page_budget=page_budget,
        requests_per_minute=requests_per_minute, scan_interval_hours=scan_interval_hours,
        policy_status="unknown", next_scan_at=None,
    )


def update_scope(
    db: Session,
    scope: SourceScope,
    **values,
) -> bool:
    """Validate a complete edit and revoke approval when scan behavior changes."""

    candidate = create_scope_proposal(db, **values)
    behavior_fields = (
        "ownership", "adapter", "canonical_url", "hostname", "allowed_path_prefix",
        "institution_unit_id", "school_revision", "max_depth", "page_budget",
        "requests_per_minute", "scan_interval_hours",
    )
    behavior_changed = any(getattr(scope, name) != getattr(candidate, name) for name in behavior_fields)
    scope.name = candidate.name
    for name in behavior_fields:
        setattr(scope, name, getattr(candidate, name))
    if behavior_changed:
        # A prior confirmation and policy decision apply only to the old crawl behavior.
        scope.status = "proposed"
        scope.confirmed_at = None
        scope.policy_status = "unknown"
        scope.policy_checked_at = None
        scope.next_scan_at = None
        scope.scan_requested_at = None
        scope.last_error_code = None
    return behavior_changed


def confirm_scope(scope: SourceScope, *, now: datetime | None = None) -> None:
    if scope.status == "active":
        return
    if scope.status != "proposed":
        raise RegistryError("invalid_transition", "Only a current proposal can be confirmed.")
    moment = now or utcnow()
    scope.status = "active"
    scope.confirmed_at = moment
    # Boundary approval and policy approval are deliberately separate gates.
    scope.next_scan_at = moment if scope.policy_status == "allowed" else None


def pause_scope(scope: SourceScope) -> None:
    if scope.status != "active":
        raise RegistryError("invalid_transition", "Only an active source can be paused.")
    scope.status = "paused"
    scope.next_scan_at = None


def resume_scope(scope: SourceScope, *, now: datetime | None = None) -> None:
    if scope.status != "paused":
        raise RegistryError("invalid_transition", "Only a paused source can be resumed.")
    if scope.policy_status != "allowed":
        raise RegistryError("policy_unchecked", "Review the source automation policy before resuming scans.")
    scope.status = "active"
    scope.next_scan_at = now or utcnow()


def request_scan(scope: SourceScope, *, now: datetime | None = None) -> None:
    if scope.status != "active" or scope.confirmed_at is None:
        raise RegistryError("source_not_schedulable", "Only a confirmed active source can be scanned.")
    if scope.policy_status != "allowed":
        code = "policy_blocked" if scope.policy_status == "blocked" else "policy_unchecked"
        raise RegistryError(code, "Review and allow the source automation policy before scanning.")
    moment = now or utcnow()
    scope.scan_requested_at = moment
    scope.next_scan_at = moment


def record_source_policy(
    db: Session,
    scope: SourceScope,
    *,
    outcome: str,
    evidence_url: str | None,
    evidence_excerpt: str | None,
    now: datetime | None = None,
) -> SourcePolicyAssessment:
    """Append a policy decision and apply its safe source-state transition."""

    if scope.confirmed_at is None or scope.status not in {"active", "paused", "policy_blocked"}:
        raise RegistryError("source_not_confirmed", "Confirm the source boundary before reviewing its policy.")
    if outcome not in {"allowed", "blocked"}:
        raise RegistryError("invalid_policy", "The source policy outcome is unsupported.")
    cleaned_excerpt = evidence_excerpt.strip() if evidence_excerpt else None
    cleaned_url = _validated(evidence_url).url if evidence_url else None
    moment = now or utcnow()
    assessment = SourcePolicyAssessment(
        id=str(uuid4()), source_scope_id=scope.id, outcome=outcome,
        evidence_url=cleaned_url, evidence_excerpt=cleaned_excerpt,
        checked_at=moment,
    )
    db.add(assessment)
    scope.policy_status = outcome
    scope.policy_checked_at = moment
    if outcome == "blocked":
        scope.status = "policy_blocked"
        scope.next_scan_at = None
        scope.scan_requested_at = None
        scope.last_error_code = "policy_blocked"
    else:
        # Clearing a prohibition never resumes crawling automatically.
        if scope.status == "policy_blocked":
            scope.status = "paused"
        scope.next_scan_at = moment if scope.status == "active" else None
        scope.last_error_code = None
    return assessment


def deactivate_prior_school_scopes(db: Session, *, current_revision: int) -> int:
    """Deactivate only school-owned rows from earlier profile revisions."""

    result = db.execute(
        update(SourceScope)
        .where(SourceScope.ownership == "school", or_(SourceScope.school_revision.is_(None), SourceScope.school_revision < current_revision))
        .values(status="inactive", next_scan_at=None)
    )
    return result.rowcount


def create_manual_lead(db: Session, *, title: str, url: str) -> ManualLead:
    validated = _validated(url)
    return ManualLead(id=str(uuid4()), title=title.strip(), canonical_url=validated.url, hostname=validated.hostname, status="unverified")


def _website_url(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if ";" in value:
        value = value.split(";", 1)[0].strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    try:
        return _validated(value).url
    except RegistryError:
        return None


def import_ipeds_directory(db: Session, csv_path: Path, *, source_year: int) -> int:
    """Upsert the official IPEDS HD directory CSV into the local catalog."""

    required = {"UNITID", "INSTNM", "CITY", "STABBR", "WEBADDR"}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise RegistryError("invalid_ipeds_file", "The file is not an IPEDS directory CSV.")
        rows = list(reader)
    if not rows:
        raise RegistryError("invalid_ipeds_file", "The IPEDS directory CSV is empty.")
    for row in rows:
        unit_id, name = row["UNITID"].strip(), row["INSTNM"].strip()
        state = row["STABBR"].strip().upper()
        if not unit_id.isdigit() or not name or len(state) != 2:
            raise RegistryError("invalid_ipeds_file", "The IPEDS directory CSV contains an invalid institution.")
        aliases = [item.strip() for item in row.get("ALIAS", "").split("|") if item.strip()]
        item = db.get(Institution, unit_id)
        if item is None:
            item = Institution(unit_id=unit_id)
            db.add(item)
        item.name = name
        item.aliases = aliases
        item.city = row["CITY"].strip()
        item.state = state
        item.website_url = _website_url(row["WEBADDR"])
        item.source_year = source_year
    return len(rows)


def search_institutions(db: Session, query: str, *, limit: int = 20) -> list[Institution]:
    term = query.strip().casefold()
    if len(term) < 2:
        return []
    pattern = f"%{term}%"
    return list(db.scalars(select(Institution).where(or_(Institution.name.ilike(pattern), Institution.aliases.cast(Text).ilike(pattern))).order_by(Institution.name, Institution.unit_id).limit(limit)))
