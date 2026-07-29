"""사전학습 모델 페치 — 런타임에 내려받고 **저장소에 커밋하지 않는다**.

RULES §3.4: 가중치는 MTG-UPF Essentia models(CC BY-NC-SA 4.0). 원본 재배포를 피하려고
런타임에 공식 URL에서 받아 gitignore 경로(`data/models/`)에 둔다. 파일이 이미 있고 크기가
맞으면 아무것도 하지 않는다(멱등).

네트워크를 타므로 오프라인 경로(analyze·signals·selftest)에서는 호출되지 않는다.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Any

UA = "artist-intelligence/1.0 (research; sonic-profile)"
BASE = "https://essentia.upf.edu/models"
# URL을 한 줄에 담아 암묵 문자열 연결을 없앤다 — 컬렉션 안의 암묵 연결은
# 쉼표 누락과 눈으로 구분되지 않는다(ISC004).
_FEAT = f"{BASE}/feature-extractors"
_HEADS = f"{BASE}/classification-heads"

# (파일명, URL, 기대 크기) — 크기는 부분 다운로드를 잡는 최소 무결성 검사
MODELS: dict[str, tuple[str, int]] = {
    "discogs-effnet-bsdynamic-1.onnx": (
        f"{_FEAT}/discogs-effnet/discogs-effnet-bsdynamic-1.onnx", 18027718),
    "discogs-effnet-bsdynamic-1.json": (
        f"{_FEAT}/discogs-effnet/discogs-effnet-bsdynamic-1.json", 14986),
    "mtg_jamendo_instrument-discogs-effnet-1.onnx": (
        f"{_HEADS}/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.onnx", 2706492),
    "mtg_jamendo_instrument-discogs-effnet-1.json": (
        f"{_HEADS}/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.json", 3382),
    "mtg_jamendo_genre-discogs-effnet-1.onnx": (
        f"{_HEADS}/mtg_jamendo_genre/mtg_jamendo_genre-discogs-effnet-1.onnx", 2802925),
    "mtg_jamendo_genre-discogs-effnet-1.json": (
        f"{_HEADS}/mtg_jamendo_genre/mtg_jamendo_genre-discogs-effnet-1.json", 4267),
    # ── 구성물 지표 (C층, D-031 · RULES §3.1.6.2) ─────────────────────────────
    # 아래 둘은 **기존 effnet 1280 임베딩에 그대로 얹힌다** — 전처리 변경도 추가
    # 추론 사슬도 없다. 이 편승이 D-031을 싸게 만든 이유다.
    "mtg_jamendo_moodtheme-discogs-effnet-1.onnx": (
        f"{_HEADS}/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.onnx", 2739322),
    "mtg_jamendo_moodtheme-discogs-effnet-1.json": (
        f"{_HEADS}/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.json", 3646),
    "danceability-discogs-effnet-1.onnx": (
        f"{_HEADS}/danceability/danceability-discogs-effnet-1.onnx", 514101),
    "danceability-discogs-effnet-1.json": (
        f"{_HEADS}/danceability/danceability-discogs-effnet-1.json", 1989),
    # valence·arousal만 **다른 임베딩**(msd-musicnn 200차원)을 요구한다. mel 사양은
    # 우리 것과 동일하고 패치 길이만 128→187이라 §3.3 지뢰를 새로 밟지는 않는다.
    "msd-musicnn-1.onnx": (f"{_FEAT}/musicnn/msd-musicnn-1.onnx", 3168334),
    "msd-musicnn-1.json": (f"{_FEAT}/musicnn/msd-musicnn-1.json", 3299),
    # 헤드는 **deam**이다. 처음 고른 `muse`(약 9만 트랙, 표본 최대)는 실측에서 **퇴화**했다 —
    # 말러 5.249 · Happy 5.469 · 스크릴렉스 5.299로 순서도 폭(0.22)도 없었다. 같은 코드
    # 경로에서 deam은 4.385 / 5.418 / 6.190으로 순서가 맞는다(TESTS §6.4). "표본이 크니
    # 낫다"는 사전 근거가 실측으로 뒤집힌 사례다.
    "deam-msd-musicnn-1.onnx": (f"{_HEADS}/deam/deam-msd-musicnn-1.onnx", 4259),
    "deam-msd-musicnn-1.json": (f"{_HEADS}/deam/deam-msd-musicnn-1.json", 2701),
}

DEFAULT_DIR = Path("data") / "models"

# RULES §3.4 — BY(출처표시) 의무. provenance와 리포트에 실린다.
ATTRIBUTION = (
    "Essentia models by MTG-UPF (CC BY-NC-SA 4.0) · "
    "MTG-Jamendo (Bogdanov et al., ICML 2019 workshop)"
)
LICENSE = "CC BY-NC-SA 4.0 (non-commercial)"


def model_dir(override: str | None = None) -> Path:
    return Path(override) if override else DEFAULT_DIR


def ensure_models(directory: Path | None = None) -> Path:
    """필요한 파일이 다 있으면 즉시 반환, 없으면 받는다(멱등)."""
    d = directory or DEFAULT_DIR
    d.mkdir(parents=True, exist_ok=True)
    for name, (url, size) in MODELS.items():
        p = d / name
        if p.exists() and p.stat().st_size == size:
            continue
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            blob = r.read()
        if len(blob) != size:
            raise OSError(f"{name}: 크기 불일치 {len(blob)} != {size} (부분 다운로드 의심)")
        p.write_bytes(blob)
    return d


def models_present(directory: Path | None = None) -> bool:
    d = directory or DEFAULT_DIR
    return all((d / n).exists() and (d / n).stat().st_size == s for n, (_, s) in MODELS.items())


def tagger_provenance() -> dict[str, Any]:
    """값의 일부인 태거 설정 — 캐시 키·시리즈 버전 분리에 쓰인다(RULES §2)."""
    from sonic_profile.tagging import PATCH_MSD, TOP_K, TOP_K_INSTRUMENT, VA_HEAD

    return {
        "tagger": "discogs-effnet-bsdynamic-1",
        "tagger_heads": [
            "mtg_jamendo_instrument-1", "mtg_jamendo_genre-1",
            "mtg_jamendo_moodtheme-1", "danceability-1",
        ],
        "tagger_sample_rate": 16000,
        # C층 (D-031). **어느 주석 기준인가가 정의의 일부**라 provenance에 남긴다
        # (RULES §3.1.7 B) — 모델을 바꾸면 값의 뜻이 바뀌므로 캐시도 무효화돼야 한다.
        "mood_head": "mtg_jamendo_moodtheme-discogs-effnet-1",
        "valence_head": VA_HEAD,
        "valence_embedding": "msd-musicnn-1",
        "valence_patch": PATCH_MSD,
        # 저장 라벨 수는 **값의 일부다** — 잘라 두면 임계 집계가 하한이 된다(RULES §3.1.6.1).
        # 캐시 키에 들어가야 이 값을 늘렸을 때 옛 절단본이 조용히 되살아나지 않는다.
        "tagger_top_k": TOP_K,
        "tagger_top_k_instrument": TOP_K_INSTRUMENT,
        "tagger_license": LICENSE,
        "attribution": ATTRIBUTION,
    }
