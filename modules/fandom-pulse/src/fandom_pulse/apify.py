"""Live Apify collection for fandom-pulse (IG hashtag scraper).

Runs the Actor and returns RAW dataset items; the caller strips them to
facts-only via ``normalize.to_record`` BEFORE anything is written (§4). The
Actor is pay-per-result, so callers always pass cost caps. Reads ``APIFY_TOKEN``
from env (see ``.env.example`` / ``scripts/apify_probe.py``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

_API = "https://api.apify.com/v2"
_UA = "Mozilla/5.0 (research; artist-intelligence fandom-pulse collector)"
_ACTOR = "apify~instagram-hashtag-scraper"


def _token() -> str:
    tok = os.environ.get("APIFY_TOKEN", "").strip()
    if not tok:
        raise SystemExit(
            "APIFY_TOKEN not set — issue at console.apify.com/settings/integrations, "
            "then setx APIFY_TOKEN (see .env.example) or verify with scripts/apify_probe.py"
        )
    return tok


def fetch_hashtag(
    hashtag: str,
    *,
    results_type: str = "posts",
    results_limit: int = 30,
    max_items: int = 30,
    max_usd: float = 0.10,
    timeout: int = 180,
) -> list[dict[str, object]]:
    """Run the IG hashtag scraper synchronously; return raw dataset items."""
    body = {
        "hashtags": [hashtag.lstrip("#")],
        "resultsType": results_type,
        "resultsLimit": results_limit,
    }
    query = urllib.parse.urlencode(
        {"maxItems": max_items, "maxTotalChargeUsd": max_usd, "timeout": timeout, "format": "json"}
    )
    url = f"{_API}/acts/{_ACTOR}/run-sync-get-dataset-items?{query}"
    headers = {
        "Authorization": f"Bearer {_token()}",
        "User-Agent": _UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout + 30) as resp:  # noqa: S310 (trusted host)
            items = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"Apify API {exc.code}: {detail}") from exc
    return items if isinstance(items, list) else []
