"""라이브 수집 — 프리뷰 해석 + 무보관 처리 (RULES §1).

**무보관 불변식**: 오디오 바이트는 디스크에 영속하지 않는다. 디코드를 위해 임시 파일이
필요하지만, 예외 경로를 포함해 **반드시** 지운다(finally). 남는 것은 수치와 provenance뿐.

**아티스트 검증**: 검색 첫 결과를 그대로 믿지 않는다 — "KISS OF LIFE" 검색이 Sade의
"Kiss of Life"를 반환하는 실측 사례가 있었다. 워치리스트 별칭과 대조해 확인된 것만 쓰고,
확인 못 하면 **미해석**으로 남긴다(추측 금지, chart-history §4.2와 같은 규율).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from typing import Any

import numpy as np

from sonic_profile.features import SR, Unresolved, extract

UA = "artist-intelligence/1.0 (research; sonic-profile)"
ITUNES = "https://itunes.apple.com/search"
DEEZER = "https://api.deezer.com/search"
_TIMEOUT = 25


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").casefold())


def _artist_ok(found: str, aliases: list[str]) -> bool:
    """반환된 아티스트가 워치리스트 별칭과 일치하는가 (오매칭 차단)."""
    f = _norm(found)
    return bool(f) and any(_norm(a) == f for a in aliases)


def _get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _apple(term: str, aliases: list[str], country: str, limit: int) -> list[dict[str, Any]]:
    q = urllib.parse.urlencode({"term": term, "entity": "song", "country": country, "limit": limit})
    out = []
    for item in _get_json(f"{ITUNES}?{q}").get("results") or []:
        if item.get("previewUrl") and _artist_ok(str(item.get("artistName") or ""), aliases):
            out.append(
                {
                    "source": "apple",
                    "track_id": str(item.get("trackId") or ""),
                    "artist": item.get("artistName"),
                    "title": item.get("trackName"),
                    "release_date": (item.get("releaseDate") or "")[:10],
                    "preview_url": item["previewUrl"],
                    "suffix": ".m4a",
                }
            )
    return out


def _deezer(term: str, aliases: list[str], limit: int) -> list[dict[str, Any]]:
    q = urllib.parse.urlencode({"q": term, "limit": limit})
    out = []
    for item in _get_json(f"{DEEZER}?{q}").get("data") or []:
        artist = (item.get("artist") or {}).get("name") or ""
        if item.get("preview") and _artist_ok(str(artist), aliases):
            out.append(
                {
                    "source": "deezer",
                    "track_id": str(item.get("id") or ""),
                    "artist": artist,
                    "title": item.get("title"),
                    "release_date": "",
                    "preview_url": item["preview"],
                    "suffix": ".mp3",
                }
            )
    return out


def candidates(term: str, aliases: list[str], *, country: str = "KR", limit: int = 5) -> list[dict[str, Any]]:
    """별칭으로 검증된 프리뷰 후보들. Apple 우선(커버리지·메타 우수), Deezer 폴백."""
    found: list[dict[str, Any]] = []
    for fn in (lambda: _apple(term, aliases, country, limit), lambda: _deezer(term, aliases, limit)):
        try:
            found.extend(fn())
        # S112(로깅하라)는 붙이지 않는다 — 여기서 삼키는 건 폴백 사슬의 제어 흐름이고,
        # 실패 자체는 후보 0건 → 상위에서 `미해석`으로 리포트에 남는다(삼켜서 사라지지 않는다).
        except Exception:  # noqa: BLE001, S112 — 소스 장애는 폴백으로, 원인은 미해석으로 기록
            continue
    return found


def _core(s: str) -> str:
    """버전 표기를 걷어낸 제목 비교용 (`(Feat. …)`·`[Inst.]` 등)."""
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s or "")
    s = re.sub(r"(?i)\b(feat|ft|with|prod)\b.*", " ", s)
    return _norm(s)


def track_candidates(
    artist: str, title: str, *, country: str = "KR", limit: int = 3
) -> list[dict[str, Any]]:
    """차트 트랙(아티스트+곡명) → 검증된 프리뷰 후보.

    워치리스트와 달리 별칭 목록이 없으므로 **아티스트 또는 제목의 정규화 일치**로 검증한다.
    아티스트+제목을 함께 검색하므로 제목 완전일치는 강한 증거다. 둘 다 어긋나면 미해석
    (실측: 같은 Apple 차트를 코호트로 쓰면 표기 체계가 같아 25/25 채택 — RULES §1.1).
    """
    q = urllib.parse.urlencode(
        {"term": f"{artist} {title}", "entity": "song", "country": country, "limit": limit}
    )
    try:
        results = _get_json(f"{ITUNES}?{q}").get("results") or []
    except Exception:  # noqa: BLE001
        return []
    out: list[dict[str, Any]] = []
    for item in results:
        if not item.get("previewUrl"):
            continue
        ra, rt = str(item.get("artistName") or ""), str(item.get("trackName") or "")
        if _norm(ra) == _norm(artist):
            how = "artist"
        elif _norm(rt) == _norm(title):
            how = "title"
        elif _core(rt) and _core(rt) == _core(title):
            how = "title-core"
        else:
            continue
        out.append(
            {
                "source": "apple",
                "track_id": str(item.get("trackId") or ""),
                "artist": ra,
                "title": rt,
                "release_date": (item.get("releaseDate") or "")[:10],
                "preview_url": item["previewUrl"],
                "suffix": ".m4a",
                "matched_by": how,
            }
        )
    return out


def _decode(path: str) -> np.ndarray:
    """오디오 파일 → 모노 float32 @ SR. libsndfile(MP3/WAV/FLAC) → PyAV(m4a/AAC) 순."""
    try:
        import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

        y, _ = librosa.load(path, sr=SR, mono=True)
        if y.size:
            return np.asarray(y, dtype=np.float32)
    # 최종 실패는 아래에서 Unresolved로 올라간다 — 여기서 삼키는 건 백엔드 전환뿐이다.
    except Exception:  # noqa: BLE001, S110 — 다음 백엔드로
        pass
    try:
        import av  # type: ignore[import-not-found]  # PyAV: FFmpeg 번들 — AAC/m4a 해독용
    except ImportError as exc:
        raise Unresolved("no decoder for this container (install 'av' for m4a/AAC)") from exc
    try:
        with av.open(path) as container:
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="flt", layout="mono", rate=SR)
            chunks: list[np.ndarray] = []
            for frame in container.decode(stream):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray().reshape(-1))
        if not chunks:
            raise Unresolved("decoded empty")
        return np.concatenate(chunks).astype(np.float32)
    except Unresolved:
        raise
    except Exception as exc:
        raise Unresolved(f"decode failed: {type(exc).__name__}") from exc


def _decode_stereo(path: str) -> np.ndarray | None:
    """오디오 파일 → **2×N 스테레오** float32 @ SR. 모노 소스·실패는 None.

    **모노 경로(`_decode`)를 건드리지 않는 것이 이 함수의 존재 이유다**(D-031). width를
    얻자고 기존 로드를 스테레오로 바꾸면 `to_mono`와 리샘플의 **순서가 뒤바뀌어** 전 지표의
    부동소수 말단이 흔들릴 수 있다 — 과거 값과 비교 불가가 되는 위험(RULES §2)을 감수할
    이유가 없다. 디코드 한 번이 더 들지만 그 비용은 신경망 추론 옆에서 무시할 만하다.
    """
    try:
        import librosa  # type: ignore  # 선택적 중량 의존성 (CI 타입체크 환경에 없음)

        y, _ = librosa.load(path, sr=SR, mono=False)
        arr = np.asarray(y, dtype=np.float32)
        if arr.ndim == 2 and arr.shape[0] >= 2:
            return arr[:2]
        if arr.size:
            return None  # 모노 소스 — "좁다"가 아니라 정보 없음(§0)
    except Exception:  # noqa: BLE001, S110 — 다음 백엔드로
        pass
    try:
        import av  # type: ignore[import-not-found]  # PyAV: FFmpeg 번들 — AAC/m4a 해독용

        with av.open(path) as container:
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="flt", layout="stereo", rate=SR)
            chunks: list[np.ndarray] = []
            for frame in container.decode(stream):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray().reshape(-1))
        if not chunks:
            return None
        # PyAV의 packed 'flt' 스테레오는 L,R,L,R… 순서다
        inter = np.concatenate(chunks).astype(np.float32)
        if inter.size < 2:
            return None
        return np.stack([inter[0::2], inter[1::2]])
    except Exception:  # noqa: BLE001 — width는 선택 지표다. 실패는 결측으로 남는다
        return None


def lookup_preview(source: str, track_id: str, *, country: str = "KR") -> dict[str, Any] | None:
    """(소스, 트랙 ID) → 그 **정확한 녹음**의 프리뷰 후보. 검색이 아니라 ID 조회다.

    이미 관측한 트랙을 다시 재려면 검색으로 되찾아선 안 된다 — 표기·리마스터·지역판이
    끼어들어 **다른 녹음**을 잴 수 있다. ID 조회는 그 위험이 없다(RULES §1 별칭 검증의 연장).
    """
    tid = str(track_id or "").strip()
    if not tid:
        return None
    try:
        if source == "apple":
            q = urllib.parse.urlencode({"id": tid, "country": country, "entity": "song"})
            items = _get_json(f"https://itunes.apple.com/lookup?{q}").get("results") or []
            item = next((x for x in items if x.get("previewUrl")), None)
            if not item:
                return None
            return {
                "source": "apple", "track_id": tid, "suffix": ".m4a",
                "artist": str(item.get("artistName") or ""),
                "title": str(item.get("trackName") or ""),
                "preview_url": item["previewUrl"],
            }
        if source == "deezer":
            item = _get_json(f"https://api.deezer.com/track/{urllib.parse.quote(tid)}")
            if not item.get("preview"):
                return None
            return {
                "source": "deezer", "track_id": tid, "suffix": ".mp3",
                "artist": str((item.get("artist") or {}).get("name") or ""),
                "title": str(item.get("title") or ""),
                "preview_url": item["preview"],
            }
    except Exception:  # noqa: BLE001 — 조회 실패는 복구 대상에서 빠질 뿐 치명적이지 않다
        return None
    return None


def _audio_from_url(
    url: str, suffix: str, *, want_stereo: bool = False
) -> tuple[np.ndarray, np.ndarray | None]:
    """프리뷰 URL → (모노 배열, 스테레오 2×N 또는 None). **오디오 파일은 이 함수를
    벗어나지 않는다**(무보관 §1).

    다운로드·임시파일·삭제가 한 곳에만 있어야 무보관 불변식을 한 곳에서 보증한다 —
    호출자가 늘 때마다 복사하면 언젠가 한 곳에서 삭제가 빠진다. 스테레오를 추가하면서도
    **같은 임시파일 하나**를 두 디코드가 나눠 쓰게 해 이 성질을 유지한다.
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        blob = r.read()
    if not blob:
        raise Unresolved("empty preview body")
    fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="sonic_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(blob)
        mono = _decode(tmp)
        return mono, (_decode_stereo(tmp) if want_stereo else None)
    finally:
        try:
            os.unlink(tmp)  # 무보관 불변식 — 예외 경로에서도 반드시
        except OSError:
            pass


def tags_from_preview(url: str, *, suffix: str = ".audio") -> dict[str, Any]:
    """프리뷰 URL → 태그만. 이미 잰 DSP·리듬을 건드리지 않고 라벨만 다시 딴다(retag 경로).

    지표는 녹음의 성질이라 값이 같게 나오지만, **불필요한 재계산과 재기록을 하지 않는 것**이
    복구를 감사 가능하게 만든다 — 바뀐 필드가 악기 라벨뿐이어야 diff로 확인된다.
    """
    from sonic_profile.tagging import extract_tags

    return extract_tags(_audio_from_url(url, suffix)[0], SR)


def features_from_preview(
    url: str, *, low_hz: float, suffix: str = ".audio",
    rhythm: bool = True, tags: bool = True,
) -> dict[str, Any]:
    """프리뷰 URL → 지표. 오디오는 이 함수를 벗어나지 않는다(무보관 §1).

    DSP 지표(§3)에 이어 리듬(§3.1.5)·태깅(§3.1.6)을 **같은 배열 위에서** 잰다.
    둘 중 하나가 실패해도 나머지는 낸다 — 결측은 0이 아니라 사유와 함께 비워둔다.
    """
    y, stereo = _audio_from_url(url, suffix, want_stereo=True)
    feats = extract(y, SR, low_hz=low_hz, stereo=stereo)
    if rhythm:
        from sonic_profile.rhythm import extract_rhythm

        try:
            feats.update(extract_rhythm(y, SR))
        except Exception as exc:  # noqa: BLE001 — 리듬 실패가 지표를 죽이지 않는다
            feats["rhythm_unresolved"] = f"{type(exc).__name__}: {exc}"[:120]
        # RULES §3: tempo_bpm은 **적합값**이 정본이고 librosa 격자값은 과거 시리즈
        # 연속성 전용으로 내려간다. 적합이 실패하면 격자값이 그대로 정본을 유지한다.
        if isinstance(feats.get("tempo_bpm_fit"), (int, float)):
            feats["tempo_bpm_grid"] = feats["tempo_bpm"]
            feats["tempo_bpm"] = feats.pop("tempo_bpm_fit")
            feats["tempo_source"] = "beat_this-fit"
        else:
            feats["tempo_source"] = "librosa-grid"
    if tags:
        from sonic_profile.tagging import extract_tags

        try:
            feats.update(extract_tags(y, SR))
        except Exception as exc:  # noqa: BLE001 — 태깅 실패가 지표를 죽이지 않는다
            feats["tags_unresolved"] = f"{type(exc).__name__}: {exc}"[:120]
    return feats


def decoder_provenance() -> dict[str, Any]:
    try:
        import av  # type: ignore[import-not-found]

        return {"decoders": ["libsndfile", f"pyav {getattr(av, '__version__', '?')}"], "aac_capable": True}
    except ImportError:
        return {"decoders": ["libsndfile"], "aac_capable": False}
