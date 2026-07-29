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

# (파일명, URL, 기대 크기) — 크기는 부분 다운로드를 잡는 최소 무결성 검사
MODELS: dict[str, tuple[str, int]] = {
    "discogs-effnet-bsdynamic-1.onnx": (
        f"{BASE}/feature-extractors/discogs-effnet/discogs-effnet-bsdynamic-1.onnx", 18027718),
    "discogs-effnet-bsdynamic-1.json": (
        f"{BASE}/feature-extractors/discogs-effnet/discogs-effnet-bsdynamic-1.json", 14986),
    "mtg_jamendo_instrument-discogs-effnet-1.onnx": (
        f"{BASE}/classification-heads/mtg_jamendo_instrument/"
        "mtg_jamendo_instrument-discogs-effnet-1.onnx", 2706492),
    "mtg_jamendo_instrument-discogs-effnet-1.json": (
        f"{BASE}/classification-heads/mtg_jamendo_instrument/"
        "mtg_jamendo_instrument-discogs-effnet-1.json", 3382),
    "mtg_jamendo_genre-discogs-effnet-1.onnx": (
        f"{BASE}/classification-heads/mtg_jamendo_genre/"
        "mtg_jamendo_genre-discogs-effnet-1.onnx", 2802925),
    "mtg_jamendo_genre-discogs-effnet-1.json": (
        f"{BASE}/classification-heads/mtg_jamendo_genre/"
        "mtg_jamendo_genre-discogs-effnet-1.json", 4267),
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
    return {
        "tagger": "discogs-effnet-bsdynamic-1",
        "tagger_heads": ["mtg_jamendo_instrument-1", "mtg_jamendo_genre-1"],
        "tagger_sample_rate": 16000,
        "tagger_license": LICENSE,
        "attribution": ATTRIBUTION,
    }
