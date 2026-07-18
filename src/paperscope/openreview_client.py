"""OpenReview client construction.

Supports three auth modes, tried in order of preference:
  1. OPENREVIEW_TOKEN -- a previously-obtained session token.
  2. OPENREVIEW_USERNAME + OPENREVIEW_PASSWORD -- standard login.
  3. Guest/unauthenticated -- openreview-py's client accepts no credentials at all and
     works for public read endpoints; restricted invitations will 401/403.

Rate-limit retry (429/500/502/503/504, exponential backoff, honoring Retry-After) is
already handled inside openreview-py's underlying requests session -- verified against
the library's constructor, which mounts a `Retry` adapter. We don't duplicate that logic
here; the CI-level retry (see the fetch workflow) is a coarser safety net for whole-process
failures, not a substitute for it.
"""

from __future__ import annotations

import os

try:
    import openreview
except ImportError as e:  # pragma: no cover
    raise SystemExit("Missing dependency: pip install openreview-py") from e

_client_v1 = None
_client_v2 = None


def _credentials() -> dict:
    token = os.environ.get("OPENREVIEW_TOKEN", "").strip()
    username = os.environ.get("OPENREVIEW_USERNAME", "").strip()
    password = os.environ.get("OPENREVIEW_PASSWORD", "").strip()
    if token:
        return {"token": token}
    if username and password:
        return {"username": username, "password": password}
    return {}  # guest mode


def get_client(version: str):
    """Return a cached OpenReview client for the given API version ("v1" or "v2")."""
    global _client_v1, _client_v2
    creds = _credentials()
    if version == "v1":
        if _client_v1 is None:
            _client_v1 = openreview.Client(baseurl="https://api.openreview.net", **creds)
        return _client_v1
    if _client_v2 is None:
        _client_v2 = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net", **creds)
    return _client_v2


def auth_mode() -> str:
    creds = _credentials()
    if "token" in creds:
        return "token"
    if "username" in creds:
        return "password"
    return "guest"


def reset_clients() -> None:
    """Drop cached clients -- used by tests so credential changes take effect."""
    global _client_v1, _client_v2
    _client_v1 = None
    _client_v2 = None
