"""수집 소스가 **이 IP에서 열리는지**만 잰다. 상태코드·바이트수·소요시간, 그 이상은 없다.

HANDOFF 3단계(이전 결정의 갈림길). `DRAFT-saas-platform.md` §2.2.1이 "데이터센터 IP에서
소스가 열리는지는 여기서 잴 수 없다 — 실제로 한 번 돌려 봐야 안다"고 적어 둔 것에 대한
도구다. **판정하지 않는다** — 두 곳(이 PC · 러너)에서 같은 것을 재서 나란히 놓을 뿐이다.

    python scripts/ip_probe.py                 # 로컬 기준선
    python scripts/ip_probe.py --json out.json # 대조용 저장
    (러너: .github/workflows/ip-probe.yml — workflow_dispatch 전용)

🔴 **아무것도 저장하지 않는다.** 응답 본문은 길이만 세고 버린다. 수집이 아니라 도달 여부
확인이므로 원본이 디스크에 남을 이유가 없다.

무료만 때린다. Apify는 토큰·플랜 조회(과금 0)뿐이고 액터를 돌리지 않는다 — 이 시험이
돈을 쓰면 시험을 자주 못 돌린다. 키가 없는 항목은 **skip으로 표시**한다(통과가 아니다).
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_UA = "Mozilla/5.0 (research; artist-intelligence reachability probe)"
_TIMEOUT = 30


def _say(msg: str) -> None:
    """출력은 항상 ASCII (cp949 콘솔 · D-054 ⑥ · D-058 ⑤)."""
    print(msg.encode("ascii", "backslashreplace").decode("ascii"))


def _probe(
    name: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    expect_bytes: bool = True,
) -> dict[str, object]:
    h = {"User-Agent": _UA, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, method=method)
    t0 = time.monotonic()
    try:
        # trusted hosts: 수집기가 매일 때리는 바로 그 주소들이다 (daily_collect.ps1)
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ssl.create_default_context()) as resp:
            body = resp.read() if expect_bytes else b""
            return {
                "name": name,
                "url": url,
                "status": resp.status,
                "bytes": len(body),
                "ms": round((time.monotonic() - t0) * 1000),
                "server": resp.headers.get("Server", ""),
            }
    except urllib.error.HTTPError as exc:
        return {
            "name": name,
            "url": url,
            "status": exc.code,
            "bytes": 0,
            "ms": round((time.monotonic() - t0) * 1000),
            "error": exc.reason if isinstance(exc.reason, str) else str(exc.reason),
        }
    except Exception as exc:  # noqa: BLE001 — 무엇이 막든 한 줄로 적고 다음 소스로 간다
        return {
            "name": name,
            "url": url,
            "status": 0,
            "bytes": 0,
            "ms": round((time.monotonic() - t0) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _skip(name: str, why: str) -> dict[str, object]:
    return {"name": name, "url": "", "status": -1, "bytes": 0, "ms": 0, "error": f"skipped: {why}"}


def run() -> list[dict[str, object]]:
    out: list[dict[str, object]] = []

    # 러너의 나가는 IP — 기록용. 어느 대역에서 잰 결과인지 모르면 두 실행을 못 비교한다.
    out.append(_probe("meta:egress-ip", "https://api.ipify.org"))

    # 1) Kworb — 차트 원본 3종 (스크레이프 · 무료 · 지역 차단 표면이 가장 넓다)
    out.append(_probe("kworb:spotify-kr", "https://kworb.net/spotify/country/kr_daily.html"))
    out.append(_probe("kworb:youtube-kr", "https://kworb.net/youtube/insights/kr_daily.html"))
    out.append(_probe("kworb:shazam-kr", "https://kworb.net/charts/shazam/kr.html"))

    # 2) Apple RSS — 공식 피드
    out.append(
        _probe("apple:rss-kr", "https://rss.marketingtools.apple.com/api/v2/kr/music/most-played/10/songs.json")
    )

    # 3) iTunes — 검색 -> 프리뷰 CDN. 프리뷰는 **1바이트만** 받는다(오디오를 끌어올 이유가 없다).
    q = urllib.parse.urlencode({"term": "aespa", "media": "music", "limit": 1, "country": "kr"})
    search = _probe("itunes:search", f"https://itunes.apple.com/search?{q}")
    out.append(search)
    preview_url = ""
    if search.get("status") == 200:
        try:
            with urllib.request.urlopen(  # trusted host
                urllib.request.Request(f"https://itunes.apple.com/search?{q}", headers={"User-Agent": _UA}),
                timeout=_TIMEOUT,
            ) as resp:
                results = json.loads(resp.read().decode("utf-8", "replace")).get("results") or []
            preview_url = str(results[0].get("previewUrl") or "") if results else ""
        except Exception as exc:  # noqa: BLE001
            out.append({"name": "itunes:preview", "url": "", "status": 0, "bytes": 0, "ms": 0, "error": str(exc)})
    if preview_url:
        out.append(_probe("itunes:preview-cdn", preview_url, headers={"Range": "bytes=0-0"}))
    elif search.get("status") == 200:
        out.append(_skip("itunes:preview-cdn", "search returned no previewUrl"))

    # 4) Apify — 토큰·플랜 조회만. 액터를 돌리지 않으므로 과금 0.
    tok = os.environ.get("APIFY_TOKEN", "").strip()
    if tok:
        out.append(_probe("apify:users-me", "https://api.apify.com/v2/users/me", headers={"Authorization": f"Bearer {tok}"}))
    else:
        out.append(_skip("apify:users-me", "APIFY_TOKEN not set"))

    # 5) YouTube Data API — 무료 할당량 1 unit짜리 호출
    ytk = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if ytk:
        yq = urllib.parse.urlencode({"part": "id", "id": "dQw4w9WgXcQ", "key": ytk})
        out.append(_probe("youtube:videos-list", f"https://www.googleapis.com/youtube/v3/videos?{yq}"))
    else:
        out.append(_skip("youtube:videos-list", "YOUTUBE_API_KEY not set"))

    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="reachability probe for the collector's sources")
    ap.add_argument("--json", default=None, help="write raw results here for side-by-side comparison")
    args = ap.parse_args(argv)

    results = run()
    _say(f"{'source':24} {'status':>6} {'bytes':>9} {'ms':>6}  note")
    _say("-" * 72)
    for r in results:
        status = r["status"]
        mark = "skip" if status == -1 else str(status)
        note = str(r.get("error") or r.get("server") or "")
        if r["name"] == "meta:egress-ip":
            note = "(see raw json for the address)"
        _say(f"{r['name']:24} {mark:>6} {r['bytes']:>9} {r['ms']:>6}  {note[:40]}")

    ok = [r for r in results if r["status"] == 200]
    blocked = [r for r in results if isinstance(r["status"], int) and r["status"] not in (200, 206, -1)]
    skipped = [r for r in results if r["status"] == -1]
    _say("")
    _say(f"reachable {len(ok)} / blocked-or-failed {len(blocked)} / skipped {len(skipped)}")
    if blocked:
        _say("!! " + ", ".join(str(r["name"]) for r in blocked))
    # 🔴 판정하지 않는다: 이 스크립트는 언제나 0으로 끝난다. 막힌 것이 있어도 그것은
    #    "실패"가 아니라 **이전 결정의 입력**이고, CI가 빨개질 일이 아니다.
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"results": results}, fh, ensure_ascii=False, indent=2)
        _say(f"raw -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
