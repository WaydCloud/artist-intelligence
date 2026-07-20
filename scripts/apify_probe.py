"""Apify data-rail probe — verify the rail without hoarding data.

Rail order (D-002): Firecrawl -> YouTube API -> **Apify** -> Bright Data.
Apify is a *managed scraper* (risk-transfer 2nd-tier rail): pay-per-use and
ToS responsibility falls to us (DATA_SOURCES.md §4). So this probe is built to
be safe by construction:

  * defaults to a FREE token/plan check (`GET /v2/users/me`) — zero Actor cost;
  * spends money ONLY behind an explicit `--run`, with hard cost caps sent to
    Apify itself (`--max-items` -> `maxItems`, `--max-usd` -> `maxTotalChargeUsd`);
  * summarizes any results as METRICS ONLY (item count, field presence, numeric
    aggregates) and never prints raw text or PII (§4 — 원문 최소저장·지표 중심).

Usage:

    python scripts/apify_probe.py                          # free: token + plan
    python scripts/apify_probe.py --run apify~instagram-scraper \
        --input-file in.json --max-items 5 --max-usd 0.05  # one small paid run

Token is read from the APIFY_TOKEN env var. On Windows you can
`setx APIFY_TOKEN "apify_api_..."` and — without restarting — inject the
User-scope value for a single call:

    $env:APIFY_TOKEN = [Environment]::GetEnvironmentVariable('APIFY_TOKEN','User')
    python scripts/apify_probe.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_API = "https://api.apify.com/v2"
_UA = "Mozilla/5.0 (research; artist-intelligence apify-probe)"

# Field names that may carry personal / identifying data. The probe reports
# their *presence* but never their values (§4: PII 제거·해시).
_PII_KEYS = {
    "id", "username", "ownername", "ownerusername", "fullname", "ownerfullname",
    "name", "email", "phone", "url", "inputurl", "profileurl", "posturl",
    "displayurl", "profilepicurl", "avatar", "ownerid", "userid", "authorname",
    "authorusername", "author", "text", "caption", "comment", "message", "bio",
}


def _request(method: str, url: str, token: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": _UA,
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=310) as resp:  # noqa: S310 (trusted host)
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        try:
            msg = json.loads(detail).get("error", {}).get("message", detail)
        except json.JSONDecodeError:
            msg = detail
        raise SystemExit(f"Apify API {exc.code}: {msg}") from exc


def whoami(token: str) -> int:
    """Free token/plan check — proves the rail without running any Actor."""
    payload = _request("GET", f"{_API}/users/me", token)
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    plan = data.get("plan") or {}
    plan_id = plan.get("id") or plan.get("planId") or "?" if isinstance(plan, dict) else "?"
    print("token: VALID")
    print(f"account: {data.get('username', '?')}  |  plan: {plan_id}")
    print("(free check - no Actor was run; monthly credits: console.apify.com)")
    return 0


def _num_stats(values: list[float]) -> str:
    lo, hi = min(values), max(values)
    return f"min={lo:g} max={hi:g} mean={sum(values) / len(values):g}"


def summarize(items: list[Any]) -> None:
    """Print a METRICS-ONLY view of dataset items: shape + volume, never content."""
    print(f"\ndataset: {len(items)} item(s)")
    if not items:
        return
    keys: dict[str, int] = {}
    numeric: dict[str, list[float]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        for k, v in it.items():
            keys[k] = keys.get(k, 0) + (0 if v is None else 1)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                numeric.setdefault(k, []).append(float(v))
    print("fields (name | non-null count | note):")
    for k in sorted(keys):
        note = ""
        if k.lower() in _PII_KEYS:
            note = "[PII - value redacted]"
        elif k in numeric and numeric[k]:
            note = _num_stats(numeric[k])
        print(f"  - {k}  |  {keys[k]}/{len(items)}  {note}")


def run_actor(args: argparse.Namespace, token: str) -> int:
    if args.input_file:
        actor_input = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
    elif args.input:
        actor_input = json.loads(args.input)
    else:
        actor_input = {}
    query = urllib.parse.urlencode({
        "maxItems": args.max_items,
        "maxTotalChargeUsd": args.max_usd,
        "timeout": args.timeout,
        "format": "json",
    })
    url = f"{_API}/acts/{args.run}/run-sync-get-dataset-items?{query}"
    print(
        f"running {args.run}  |  caps: maxItems={args.max_items} "
        f"maxTotalChargeUsd=${args.max_usd}  |  (this may incur cost - DATA_SOURCES sec.4)",
        file=sys.stderr,
    )
    items = _request("POST", url, token, body=actor_input)
    if not isinstance(items, list):
        raise SystemExit(f"unexpected response (not a dataset array): {type(items).__name__}")
    summarize(items)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="apify_probe",
        description="Verify the Apify data rail (free by default; paid runs are opt-in).",
    )
    parser.add_argument("--run", metavar="ACTOR", help="run one Actor sync (e.g. apify~instagram-scraper)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--input", help="Actor input as an inline JSON string")
    group.add_argument("--input-file", help="path to a JSON file with the Actor input")
    parser.add_argument("--max-items", type=int, default=5, help="cap billable items (maxItems), default 5")
    parser.add_argument("--max-usd", type=float, default=0.05, help="cap total cost USD (maxTotalChargeUsd), default 0.05")
    parser.add_argument("--timeout", type=int, default=120, help="Actor run timeout seconds, default 120")
    args = parser.parse_args(argv)

    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        print(
            "APIFY_TOKEN not set. Issue one at https://console.apify.com/settings/integrations,\n"
            '  then: setx APIFY_TOKEN "apify_api_..."  (see .env.example).\n'
            "  Same session (no restart): "
            '$env:APIFY_TOKEN = [Environment]::GetEnvironmentVariable(\'APIFY_TOKEN\',\'User\')',
            file=sys.stderr,
        )
        return 2

    if args.run:
        return run_actor(args, token)
    return whoami(token)


if __name__ == "__main__":
    raise SystemExit(main())
