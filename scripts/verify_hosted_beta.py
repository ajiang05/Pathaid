#!/usr/bin/env python3
"""Verify a deployed PathAid beta through its public origin.

The canary creates a uniquely named synthetic student, exercises the saved
profile and discovery APIs, and deletes that account in a ``finally`` block.
It never needs administrator credentials and never uses real student data.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request


PROFILE = {
    "school": "University of Massachusetts Amherst",
    "state": "MA",
    "study_level": "undergraduate",
    "enrollment": "full_time",
    "assistance_categories": ["scholarships"],
}


class VerificationError(RuntimeError):
    """A public deployment invariant did not hold."""


class Client:
    """Small same-origin JSON client with browser-like cookie handling."""

    def __init__(self, origin: str) -> None:
        self.origin = origin.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict | None = None,
        csrf: str | None = None,
    ) -> tuple[int, object | None, urllib.response.addinfourl]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Accept": "application/json", "Origin": self.origin}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRF-Token"] = csrf
        request = urllib.request.Request(
            self.origin + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise VerificationError(
                f"{method} {path} returned HTTP {error.code}: {detail}"
            ) from error
        raw = response.read()
        payload = json.loads(raw) if raw else None
        return response.status, payload, response


def require(condition: bool, message: str) -> None:
    """Raise a concise verifier failure instead of relying on assertions."""

    if not condition:
        raise VerificationError(message)


def validate_origin(origin: str, allow_http_localhost: bool) -> str:
    """Require HTTPS in hosted use and allow HTTP only for an explicit local run."""

    parsed = urllib.parse.urlsplit(origin)
    require(not parsed.query and not parsed.fragment, "Origin cannot contain a query or fragment")
    require(bool(parsed.hostname), "Origin must include a hostname")
    if parsed.scheme == "https":
        return origin.rstrip("/")
    local = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    require(
        allow_http_localhost and local,
        "Hosted verification requires HTTPS; use --allow-http-localhost only for a local stack",
    )
    return origin.rstrip("/")


def verify(origin: str, *, allow_http_localhost: bool = False) -> None:
    """Run public health, security, authentication, profile, and discovery checks."""

    origin = validate_origin(origin, allow_http_localhost)
    hosted = urllib.parse.urlsplit(origin).scheme == "https"
    client = Client(origin)
    created = False
    csrf: str | None = None
    suffix = secrets.token_hex(8)
    credentials = {
        "email": f"pathaid-canary-{suffix}@example.invalid",
        "password": f"canary-{secrets.token_urlsafe(24)}",
    }

    try:
        status, live, response = client.request("/health/live")
        require(status == 200 and live == {"status": "live"}, "Liveness check failed")
        if hosted:
            require(
                "max-age=" in (response.headers.get("Strict-Transport-Security") or ""),
                "HTTPS response is missing Strict-Transport-Security",
            )
            require(
                response.headers.get("X-Content-Type-Options") == "nosniff",
                "HTTPS response is missing X-Content-Type-Options: nosniff",
            )
        print("PASS public liveness and security headers")

        status, ready, _ = client.request("/health/ready")
        require(status == 200 and ready == {"status": "ready"}, "Readiness check failed")
        print("PASS database readiness and migrations")

        status, signup, _ = client.request(
            "/api/auth/signup", method="POST", body=credentials
        )
        require(status == 201 and isinstance(signup, dict), "Synthetic signup failed")
        csrf = signup.get("csrf_token")
        require(isinstance(csrf, str) and bool(csrf), "Signup did not return a CSRF token")
        created = True
        print("PASS student signup and session cookie")

        status, saved, _ = client.request(
            "/api/profile",
            method="PATCH",
            body={"fields": PROFILE, "ai_opt_in": False},
            csrf=csrf,
        )
        require(status == 200 and saved == {"fields": PROFILE, "ai_opt_in": False}, "Profile was not saved exactly")
        print("PASS profile validation and persistence")

        status, discovery, _ = client.request(
            "/api/evaluate",
            method="POST",
            body={"answers": {}, "categories": ["scholarships"]},
        )
        require(status == 200 and isinstance(discovery, dict), "Discovery failed")
        require(discovery.get("categories") == ["scholarships"], "Discovery changed the requested category")
        results = discovery.get("results")
        require(isinstance(results, list), "Discovery did not return a result list")
        print(f"PASS deterministic discovery ({len(results)} published results visible)")
    finally:
        if created and csrf:
            try:
                status, _, _ = client.request(
                    "/api/profile", method="DELETE", csrf=csrf
                )
                require(status == 204, "Synthetic account deletion failed")
                print("PASS synthetic account deletion")
            except Exception as cleanup_error:
                print(
                    f"CLEANUP FAILED: synthetic account {credentials['email']} must be removed: {cleanup_error}",
                    file=sys.stderr,
                )
                raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", help="Public origin, for example https://pathaid.example.com")
    parser.add_argument(
        "--allow-http-localhost",
        action="store_true",
        help="Permit an HTTP localhost origin for a pre-deployment dry run",
    )
    args = parser.parse_args()
    try:
        verify(args.origin, allow_http_localhost=args.allow_http_localhost)
    except (VerificationError, OSError, json.JSONDecodeError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    print("Hosted beta canary passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
