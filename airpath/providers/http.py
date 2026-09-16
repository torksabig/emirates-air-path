"""Shared HTTP GET for weather archives. Inject fetch() in tests — no network."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "emirates-air-path/0.2 (+phase1-match)"
TIMEOUT_S = 60
# OpenSky SSL handshakes often hang; keep these short so failed track pulls
# do not dominate a multi-provider live batch.
OPENSKY_TIMEOUT_S = 12


class AuthRequired(RuntimeError):
    """Commercial / CDS adapter called without the required env key."""


@dataclass
class PlannedRequest:
    provider: str
    product: str
    url: str
    waypoint_seq: int | None = None
    icao: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    timeout_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "product": self.product,
            "url": self.url,
            "waypoint_seq": self.waypoint_seq,
            "icao": self.icao,
            "meta": self.meta,
        }

    def effective_timeout(self) -> float:
        if self.timeout_s is not None:
            return float(self.timeout_s)
        if self.provider == "opensky":
            return float(OPENSKY_TIMEOUT_S)
        return float(TIMEOUT_S)


FetchFn = Callable[[PlannedRequest], Any]


def http_get(req: PlannedRequest) -> Any:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"}
    headers.update(req.headers)
    request = Request(req.url, headers=headers)
    try:
        with urlopen(request, timeout=req.effective_timeout()) as resp:
            raw = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
    except TimeoutError as exc:
        raise RuntimeError(
            f"{req.provider} {req.product} network error: timed out after "
            f"{req.effective_timeout():.0f}s"
        ) from exc
    except HTTPError as exc:
        raise RuntimeError(f"{req.provider} {req.product} HTTP {exc.code}: {req.url}") from exc
    except URLError as exc:
        raise RuntimeError(f"{req.provider} {req.product} network error: {exc.reason}") from exc
    text = raw.decode("utf-8", errors="replace")
    if "json" in ctype or text[:1] in "{[":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise AuthRequired(f"Set {name} to call this provider")
    return value
