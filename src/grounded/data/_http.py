"""Small HTTP helpers shared by the public asset and episode resolvers."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Mapping, Optional


def json_request(
    url: str,
    *,
    bearer_token: Optional[str] = None,
    method: str = "GET",
    payload: Optional[Mapping[str, Any]] = None,
) -> urllib.request.Request:
    headers = {"Accept": "application/json", "User-Agent": "grounded-python-sdk"}
    body = None
    if payload is not None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    if bearer_token:
        request.add_header("Authorization", f"Bearer {bearer_token}")
    return request


def open_json_response(
    request: urllib.request.Request,
    *,
    opener: Any,
    timeout_seconds: float,
) -> tuple[Any, int]:
    with opener(request, timeout=timeout_seconds) as response:
        return json.load(response), int(getattr(response, "status", 0) or 0)
