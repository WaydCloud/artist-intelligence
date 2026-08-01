"""`data/live` 1층(관측 원본)만 골라 날짜별로 압축해 오브젝트 스토리지에 증분 업로드한다.

세 층 구조(HANDOFF)에서 **1층만** 올린다: 관측 원본은 불변·추가만·**재취득 불가**다.
2층(`*_series.json` · `social_merged.json`)과 모델 캐시는 언제든 1층에서 재생성되므로
올리지 않는다. 불변식 하나 — **재생성이 안 되면 그건 2층이 아니라 1층이다.**

멱등하다. 날짜별 아카이브는 **내용의 함수**다(멤버 정렬 · mtime 0 · gzip mtime 0), 그래서
같은 내용이면 같은 바이트고 같은 sha256이다. 매니페스트의 해시와 같으면 건너뛴다 —
"이미 올린 날"이 아니라 **"내용이 그대로인 날"**을 건너뛰므로, 지난 날짜에 파일이 늘면
(재시도가 자정을 넘겨 붙는 경우) 다시 올라간다.

🔴 이 스크립트의 실패 양식은 하나뿐이다: **올렸다고 믿었는데 비어 있는 것.** 그래서
매니페스트를 믿지 않는 경로를 따로 둔다 — `--verify`는 원격 목록을 실제로 받아 와
매니페스트와 대조하고, 로컬에 있는데 한 번도 오른 적 없는 날짜까지 센다.

    python scripts/backup_live.py --init-bucket  # 최초 1회 — 비공개 버킷 생성(멱등)
    python scripts/backup_live.py                # 증분 업로드
    python scripts/backup_live.py --restore --live <dir>   # 되돌리기(러너 부트스트랩·재난 복구)
    #   기본값은 **덮어쓰지 않는다**. 살아 있는 트리 위에 얹으려면 --force.
    python scripts/backup_live.py --dry-run      # 네트워크 0 -- 무엇이 오를지만 본다
    python scripts/backup_live.py --verify       # 원격 목록 x 매니페스트 x 로컬 대조
    python scripts/backup_live.py --verify --deep  # 위 + 아카이브 재빌드해 해시까지 대조
    python scripts/backup_live.py --selftest     # 네트워크 0 -- 그룹핑·결정성·건너뛰기

환경변수(둘 다 없으면 아무것도 나가지 않는다 · exit 2):
    SUPABASE_URL          https://<ref>.supabase.co
    SUPABASE_SERVICE_KEY  service_role 키 (비공개 버킷 쓰기 권한)
    BACKUP_BUCKET         기본 "live-raw" (버킷 생성은 대시보드에서 -- MCP는 read_only)

⚠ 이 스크립트는 **차트 원본과 유료 소셜 스냅샷을 3자 서비스로 내보낸다.** 재배포가 아니라
비공개 버킷 백업이지만 외부 전송인 것은 같다. `data/live/PAUSE`가 있으면 아무것도 보내지
않는다(유료 레그와 같은 레버).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_UA = "artist-intelligence backup_live/1 (private-bucket backup)"
_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_TIMEOUT = 120
_RETRIES = 3

# 1층(관측 원본). 각 디렉터리를 통째로, 파일명의 날짜로 묶는다.
_LAYER1: tuple[str, ...] = ("chart", "social", "sonic", "yt", "plans", "state")
# 로그는 디렉터리 전체가 아니라 이 한 장만 — 유료 지출 감사 기록이다.
_LOG_REL = "logs/daily.log"

# 🔴 빼기로 한 것. "빠뜨린 것"과 구별되도록 사유를 함께 적는다. 여기에도 위에도 없는
# 항목이 data/live 에 나타나면 _unclassified 로 보고한다 — 새 관측원이 백업 밖에서
# 조용히 자라는 것이 이 프로젝트가 반복해 맞은 실패 양식이다.
_EXCLUDED: dict[str, str] = {
    "logs": f"{_LOG_REL} 한 장만 올린다 (지출 감사). 나머지는 재생성",
    "melon_raw": "2층 — Wayback에서 다시 받는다",
    "bridge_real": "3층 — report 산출물",
    "quarantine": "PII 게이트가 REJECT한 스냅샷 — 내보내지 않는다",
    "backup": "이 스크립트의 매니페스트 — 원격 목록에서 재구성된다",
    "PAUSE": "가드 파일",
    "chart_series.json": "2층 — 1층에서 재생성",
    "chart_kr_series.json": "2층 — 1층에서 재생성",
    "social_series.json": "2층 — 1층에서 재생성",
    "social_merged.json": "2층 — 1층에서 재생성",
    "sonic_series.json": "2층 — 1층에서 재생성",
    "yt_series.json": "2층 — 1층에서 재생성",
}

_MANIFEST_REL = "backup/manifest.json"


def _say(msg: str) -> None:
    """출력은 **항상 ASCII**다. 이 스크립트의 stdout은 `daily.log`로 들어간다.

    콘솔이 cp949라 비ASCII는 두 가지로 끝난다: 운이 좋으면 mojibake, 나쁘면
    `UnicodeEncodeError`로 레그 전체가 죽는다. 2026-08-01에 유료 지출 감사 한 줄이
    정확히 이 이유로 깨진 채 실렸다(`daily_collect.ps1` 머리말). 원격이 돌려주는 오류
    본문처럼 우리가 못 고르는 문자열도 여기를 지나므로, 규율을 사람이 지키게 두지 않고
    함수가 집행한다.
    """
    print(msg.encode("ascii", "backslashreplace").decode("ascii"))


# ─────────────────────────────────────────────────────────── 로컬: 그룹 · 아카이브


def _groups(live: Path) -> dict[tuple[str, str], list[Path]]:
    """1층 파일을 `(종류, 날짜)`로 묶는다. 날짜가 안 읽히면 `_undated`로 모은다.

    ⚠ `_undated`(와 `logs/daily`)는 **키가 하나라 매일 덮어쓴다** — 그 그룹만은 이력이
    아니라 최신본만 남는다. 지금 여기 드는 것은 `sonic/cache.json`(특징 캐시 · 누적)과
    `sonic/cohort.json`(그날 코호트 목록 · 차트 스냅샷에서 재구성 가능)이고, 둘 다 누적
    또는 재생성이라 최신본만으로 족하다. **날짜별 이력이 필요한 원본이 여기 들어오면
    안 된다** — 파일명에 날짜를 넣는 쪽이 답이다.
    """
    out: dict[tuple[str, str], list[Path]] = {}
    for kind in _LAYER1:
        base = live / kind
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            m = _DATE.search(f.name)
            out.setdefault((kind, m.group(1) if m else "_undated"), []).append(f)
    log = live / _LOG_REL
    if log.is_file():
        out[("logs", "daily")] = [log]
    return out


def _unclassified(live: Path) -> list[str]:
    """1층에도 제외 목록에도 없는 `data/live` 최상위 항목."""
    known = set(_LAYER1) | set(_EXCLUDED)
    return sorted(p.name for p in live.iterdir() if p.name not in known)


def _key(kind: str, group: str, prefix: str) -> str:
    return f"{prefix}/{kind}/{group}.tar.gz" if prefix else f"{kind}/{group}.tar.gz"


def _archive(files: list[Path], root: Path) -> bytes:
    """결정적 tar.gz — 같은 내용이면 언제 어디서 만들어도 같은 바이트다.

    멤버를 경로로 정렬하고 mtime·소유자·모드를 고정한다. gzip 헤더의 mtime도 0으로
    둔다(기본값은 현재 시각이라 그것만으로 매 실행 해시가 바뀐다). 이 결정성이
    "내용이 그대로면 건너뛴다"와 원격 크기 대조의 전제다.
    """
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for f in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
            data = f.read_bytes()
            info = tarfile.TarInfo(f.relative_to(root).as_posix())
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


# ─────────────────────────────────────────────────────────── 매니페스트


def _extract(blob: bytes, root: Path, *, force: bool) -> tuple[int, int]:
    """아카이브를 `root` 아래로 푼다 → `(쓴 것, 건너뛴 것)`.

    🔴 기본값은 **덮어쓰지 않는 것**이다. 러너 부트스트랩(빈 디스크)에서는 차이가 없지만,
    사람이 살아 있는 `data/live` 위에 복원을 돌리는 순간 기본값이 파괴적이면 그날의 관측을
    어제 것으로 되돌린다. 덮어쓰려면 `--force`를 명시해야 한다.

    `filter="data"`로 푼다 — 아카이브 안의 절대경로·`..`이 root 밖에 쓰는 것을 막는다.
    우리가 만든 아카이브만 다루지만, 신뢰의 근거를 "우리 것이니까"에 두지 않는다.
    """
    written = skipped = 0
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            dest = root / member.name
            if dest.exists() and not force:
                skipped += 1
                continue
            src = tar.extractfile(member)
            if src is None:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read())
            written += 1
    return written, skipped


def _manifest_load(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    objs = doc.get("objects") if isinstance(doc, dict) else None
    return objs if isinstance(objs, dict) else {}


def _manifest_save(path: Path, objects: dict[str, dict[str, object]], bucket: str, prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": 1,
        "bucket": bucket,
        "prefix": prefix,
        "updatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "objects": dict(sorted(objects.items())),
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────── 원격: Supabase Storage


class Remote:
    """Supabase Storage REST. 비공개 버킷이라 service_role 키가 필요하다."""

    def __init__(self, base_url: str, key: str, bucket: str) -> None:
        self.base = base_url.rstrip("/")
        self.key = key
        self.bucket = bucket

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.key}",
            "apikey": self.key,
            "User-Agent": _UA,
        }
        h.update(extra or {})
        return h

    def _call(self, req: urllib.request.Request) -> bytes:
        last = ""
        for attempt in range(1, _RETRIES + 1):
            try:
                # trusted host: SUPABASE_URL은 운영자가 환경변수로 준 우리 프로젝트다
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:400]
                if exc.code < 500:  # 인증·권한·버킷 없음 — 재시도해도 같다
                    raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
                last = f"HTTP {exc.code}: {body}"
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = f"{type(exc).__name__}: {exc}"
            if attempt < _RETRIES:
                time.sleep(2**attempt)
        raise RuntimeError(f"{_RETRIES} attempts failed -- {last}")

    def bucket_info(self) -> dict[str, object] | None:
        """버킷 메타 (없으면 None).

        🔴 없는 버킷에 Supabase Storage는 **HTTP 400을 주면서 본문에 `"statusCode":"404"`**를
        싣는다(2026-08-01 실측). 상태코드만 보면 "없다"가 "요청이 틀렸다"로 읽혀 생성 경로가
        영영 안 돈다. 그래서 본문의 `NoSuchBucket`까지 본다.
        """
        url = f"{self.base}/storage/v1/bucket/{urllib.parse.quote(self.bucket)}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            doc = json.loads(self._call(req).decode("utf-8", "replace"))
        except RuntimeError as exc:
            if "HTTP 404" in str(exc) or "NoSuchBucket" in str(exc):
                return None
            raise
        return doc if isinstance(doc, dict) else None

    def create_bucket(self) -> None:
        """비공개 버킷을 만든다. `public`은 **항상 False**다 — 인자로 받지 않는다."""
        url = f"{self.base}/storage/v1/bucket"
        body = json.dumps({"id": self.bucket, "name": self.bucket, "public": False}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers=self._headers({"Content-Type": "application/json"}), method="POST"
        )
        self._call(req)

    def download(self, key: str) -> bytes:
        url = f"{self.base}/storage/v1/object/{urllib.parse.quote(self.bucket)}/{urllib.parse.quote(key)}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        return self._call(req)

    def upload(self, key: str, payload: bytes) -> None:
        url = f"{self.base}/storage/v1/object/{urllib.parse.quote(self.bucket)}/{urllib.parse.quote(key)}"
        req = urllib.request.Request(
            url,
            data=payload,
            headers=self._headers(
                {
                    "Content-Type": "application/gzip",
                    "Cache-Control": "max-age=31536000",
                    "x-upsert": "true",
                }
            ),
            method="POST",
        )
        self._call(req)

    def list(self, prefix: str) -> dict[str, int]:
        """`prefix` 바로 아래 객체 → `{키: 바이트}`. 하위 폴더(크기 없음)는 건너뛴다."""
        url = f"{self.base}/storage/v1/object/list/{urllib.parse.quote(self.bucket)}"
        found: dict[str, int] = {}
        offset, page = 0, 100
        while True:
            body = json.dumps(
                {
                    "prefix": prefix,
                    "limit": page,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                url, data=body, headers=self._headers({"Content-Type": "application/json"}), method="POST"
            )
            items = json.loads(self._call(req).decode("utf-8", "replace"))
            if not isinstance(items, list) or not items:
                break
            for it in items:
                if not isinstance(it, dict):
                    continue
                meta = it.get("metadata")
                if not isinstance(meta, dict):  # 폴더 엔트리
                    continue
                name = str(it.get("name") or "")
                size = meta.get("size")
                found[f"{prefix}/{name}" if prefix else name] = int(size) if isinstance(size, int) else -1
            if len(items) < page:
                break
            offset += page
        return found


# ─────────────────────────────────────────────────────────── 명령


def _config(bucket_arg: str | None) -> tuple[str, str, str]:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    bucket = (bucket_arg or os.environ.get("BACKUP_BUCKET", "") or "live-raw").strip()
    if not url or not key:
        # 조용한 성공이 이 스크립트의 최악이다. 설정이 없으면 exit 2 로 죽는다.
        _say(
            "!! SUPABASE_URL / SUPABASE_SERVICE_KEY not set -- nothing left this machine.\n"
            "   setx SUPABASE_URL https://<ref>.supabase.co\n"
            "   setx SUPABASE_SERVICE_KEY <service_role key>"
        )
        raise SystemExit(2)
    return url, key, bucket


def cmd_init_bucket(bucket_arg: str | None) -> int:
    """버킷을 **비공개로** 만든다. 일회성이고 멱등하다 (있으면 만들지 않는다).

    MCP는 `read_only=true`라 버킷을 못 만들고 그 플래그는 끄지 않는 것이 옳다. 그래서
    최초 세팅 경로를 여기 둔다 -- 대시보드에 가지 않아도 되지만, **명령을 따로 쳐야
    한다.** 업로드가 버킷을 슬쩍 만들게 두지 않는 이유는, 원격 자원을 만드는 것은
    데이터를 올리는 것과 다른 종류의 행위라서다.
    """
    url, key, bucket = _config(bucket_arg)
    remote = Remote(url, key, bucket)
    try:
        info = remote.bucket_info()
        if info is not None:
            if info.get("public") is True:
                # 🔴 공개 버킷에는 올리지 않는다. 차트 원본과 유료 소셜 스냅샷이다.
                _say(f"!! bucket '{bucket}' exists but is PUBLIC -- refusing. Make it private first.")
                return 1
            _say(f"bucket '{bucket}' already exists (private) -- nothing to do")
            return 0
        remote.create_bucket()
        # 만들었다고 믿지 않고 다시 읽는다 -- 비공개로 돌아오는지가 요건이다.
        after = remote.bucket_info()
    except RuntimeError as exc:
        # 스택 트레이스를 daily.log 에 흘리지 않는다 -- 한 줄로 사유를 적는다.
        _say(f"!! bucket init FAILED -- {exc}")
        return 1
    if after is None or after.get("public") is True:
        _say(f"!! bucket '{bucket}' did not come back private -- check the dashboard")
        return 1
    _say(f"bucket '{bucket}' created (private)")
    return 0


def _plan(live: Path, prefix: str) -> list[tuple[str, list[Path], bytes]]:
    """올릴 후보를 `(키, 파일들, 아카이브 바이트)`로. 아카이브는 여기서 만든다."""
    plan: list[tuple[str, list[Path], bytes]] = []
    for (kind, group), files in sorted(_groups(live).items()):
        plan.append((_key(kind, group, prefix), files, _archive(files, live)))
    return plan


def cmd_upload(live: Path, prefix: str, bucket_arg: str | None, dry_run: bool) -> int:
    if (live / "PAUSE").is_file():
        _say("backup skipped -- data/live/PAUSE present (nothing sent)")
        return 0
    remote: Remote | None = None
    if not dry_run:
        url, key, bucket = _config(bucket_arg)
        remote = Remote(url, key, bucket)
    else:
        bucket = (bucket_arg or os.environ.get("BACKUP_BUCKET", "") or "live-raw").strip()

    for name in _unclassified(live):
        _say(f"!! unclassified under data/live: {name} -- neither layer-1 nor excluded, NOT backed up")

    manifest_path = live / _MANIFEST_REL
    manifest = _manifest_load(manifest_path)
    uploaded = skipped = 0
    sent_bytes = 0
    failures: list[str] = []

    for key_name, files, blob in _plan(live, prefix):
        sha = hashlib.sha256(blob).hexdigest()
        prev = manifest.get(key_name)
        if isinstance(prev, dict) and prev.get("sha256") == sha:
            skipped += 1
            continue
        if dry_run:
            _say(f"would upload {key_name}  {len(blob):,}B  ({len(files)} files)")
            uploaded += 1
            sent_bytes += len(blob)
            continue
        assert remote is not None
        try:
            remote.upload(key_name, blob)
        except RuntimeError as exc:
            failures.append(f"{key_name}: {exc}")
            _say(f"!! upload FAILED {key_name} -- {exc}")
            continue
        manifest[key_name] = {
            "sha256": sha,
            "size": len(blob),
            "files": len(files),
            "uploadedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        uploaded += 1
        sent_bytes += len(blob)
        # 매 객체마다 저장한다 — 중간에 죽어도 이미 올린 것을 다시 올리지 않는다.
        _manifest_save(manifest_path, manifest, bucket, prefix)

    if not dry_run:
        _manifest_save(manifest_path, manifest, bucket, prefix)
    verb = "would upload" if dry_run else "uploaded"
    _say(f"backup {verb} {uploaded} object(s) {sent_bytes / 1e6:.2f}MB, skipped {skipped} unchanged (bucket {bucket})")
    if failures:
        _say(f"!! backup incomplete -- {len(failures)} object(s) failed")
        return 1
    return 0


def cmd_restore(live: Path, prefix: str, bucket_arg: str | None, force: bool, dry_run: bool) -> int:
    """원격 1층을 `live`로 되돌린다. 러너 부트스트랩이자 재난 복구 경로다.

    🔑 **매니페스트도 함께 재구성한다.** 안 그러면 복원 직후의 첫 업로드가 54객체를 전부
    다시 올린다 -- 러너에서는 그게 매 실행 반복이 된다. 받은 바이트의 해시를 그대로 쓰므로
    매니페스트는 "우리가 올렸다고 믿는 것"이 아니라 **"원격에 실제로 있는 것"**이 된다.

    🔴 받은 아카이브는 **풀기 전에 해시를 본다.** 손상된 것을 풀어 1층 위에 얹으면
    백업이 복구가 아니라 오염이 된다.
    """
    url, key, bucket = _config(bucket_arg)
    remote = Remote(url, key, bucket)

    listed: dict[str, int] = {}
    for kind in (*_LAYER1, "logs"):
        listed.update(remote.list(f"{prefix}/{kind}" if prefix else kind))
    if not listed:
        _say(f"!! nothing to restore -- no objects under '{prefix}/' in bucket {bucket}")
        return 1

    if dry_run:
        total = sum(v for v in listed.values() if v > 0)
        _say(f"would restore {len(listed)} object(s) {total / 1e6:.2f}MB into {live}")
        for k in sorted(listed):
            _say(f"  {k}  {listed[k]:,}B")
        return 0

    live.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, object]] = {}
    written = skipped = failed = 0
    got_bytes = 0
    for key_name in sorted(listed):
        try:
            blob = remote.download(key_name)
        except RuntimeError as exc:
            failed += 1
            _say(f"!! download FAILED {key_name} -- {exc}")
            continue
        size = listed[key_name]
        if size > 0 and len(blob) != size:
            failed += 1
            _say(f"!! size mismatch on {key_name}: listed {size}B, got {len(blob)}B -- not extracted")
            continue
        try:
            w, s = _extract(blob, live, force=force)
        except (tarfile.TarError, OSError) as exc:
            failed += 1
            _say(f"!! extract FAILED {key_name} -- {type(exc).__name__}: {exc}")
            continue
        written += w
        skipped += s
        got_bytes += len(blob)
        manifest[key_name] = {
            "sha256": hashlib.sha256(blob).hexdigest(),
            "size": len(blob),
            "files": w + s,
            "uploadedAt": "(restored)",
        }
    _manifest_save(live / _MANIFEST_REL, manifest, bucket, prefix)
    mode = "overwriting" if force else "keeping local files"
    _say(
        f"restored {written} file(s) from {len(manifest)} archive(s) {got_bytes / 1e6:.2f}MB "
        f"into {live} ({mode}); {skipped} already present"
    )
    if failed:
        _say(f"!! restore incomplete -- {failed} archive(s) failed")
        return 1
    return 0


def cmd_verify(live: Path, prefix: str, bucket_arg: str | None, deep: bool) -> int:
    url, key, bucket = _config(bucket_arg)
    remote = Remote(url, key, bucket)
    manifest = _manifest_load(live / _MANIFEST_REL)
    groups = _groups(live)
    expected = {_key(k, g, prefix): files for (k, g), files in groups.items()}

    listed: dict[str, int] = {}
    kinds = sorted({k for k, _ in groups} | {"chart", "social", "sonic", "yt", "plans", "state", "logs"})
    for kind in kinds:
        listed.update(remote.list(f"{prefix}/{kind}" if prefix else kind))

    red: list[str] = []
    for name in _unclassified(live):
        red.append(f"unclassified under data/live: {name} — not backed up, not declared excluded")
    for key_name in sorted(expected):
        if key_name not in manifest:
            red.append(f"never uploaded: {key_name} ({len(expected[key_name])} local files)")
    for key_name, rec in sorted(manifest.items()):
        if key_name not in listed:
            red.append(f"manifest says uploaded but REMOTE HAS NOTHING: {key_name}")
            continue
        size = rec.get("size")
        if isinstance(size, int) and listed[key_name] >= 0 and listed[key_name] != size:
            red.append(f"size mismatch: {key_name} local {size}B vs remote {listed[key_name]}B")
    if deep:
        for key_name, files in sorted(expected.items()):
            rec = manifest.get(key_name)
            if not isinstance(rec, dict):
                continue
            sha = hashlib.sha256(_archive(files, live)).hexdigest()
            if rec.get("sha256") != sha:
                red.append(f"stale: {key_name} — local content changed since upload")

    orphans = sorted(set(listed) - set(manifest))
    for key_name in orphans:
        _say(f"~  remote object not in manifest: {key_name} (harmless -- manifest can be rebuilt)")

    _say(
        f"verify: {len(expected)} local group(s), {len(manifest)} in manifest, "
        f"{len(listed)} remote object(s), bucket {bucket}"
        + (" (deep)" if deep else "")
    )
    if red:
        for line in red:
            _say(f"!! {line}")
        _say(f"!! backup NOT trustworthy -- {len(red)} finding(s)")
        return 1
    _say("verify OK -- every layer-1 group is on the remote at the size we recorded")
    return 0


# ─────────────────────────────────────────────────────────── selftest (네트워크 0)


def cmd_selftest() -> int:
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)

    # 출력이 ASCII를 벗어나면 cp949 콘솔에서 레그가 통째로 죽는다. 원격 오류 본문은
    # 우리가 고를 수 없는 문자열이므로 그 경로를 실제로 태워 본다.
    buf = io.StringIO()
    stdout, sys.stdout = sys.stdout, buf
    try:
        _say("remote said: 오류 — quota")
    finally:
        sys.stdout = stdout
    check(buf.getvalue().isascii(), f"_say must emit ASCII only, got {buf.getvalue()!r}")

    with tempfile.TemporaryDirectory() as td:
        live = Path(td) / "live"
        for rel, body in (
            ("chart/apple/kr/2026-07-19.html", "<html>a</html>"),
            ("chart/apple/us/2026-07-19.html", "<html>b</html>"),
            ("chart/apple/kr/2026-07-20.html", "<html>c</html>"),
            ("social/2026-07-19_illit.json", '{"records":[]}'),
            ("sonic/2026-07-19.json", "{}"),
            ("state/run_2026-07-19.json", "{}"),
            ("logs/daily.log", "line\n"),
            ("logs/other.log", "noise\n"),
            ("quarantine/2026-07-19_rejected.json", '{"pii":true}'),
            ("melon_raw/2026-07-20_p1.txt", "x"),
            ("social_merged.json", "{}"),
            ("newsource/2026-07-19.json", "{}"),
        ):
            p = live / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

        g = _groups(live)
        check(len(g[("chart", "2026-07-19")]) == 2, "chart 2026-07-19 should group 2 market files")
        check(len(g[("chart", "2026-07-20")]) == 1, "chart 2026-07-20 should group 1 file")
        check(("logs", "daily") in g and len(g[("logs", "daily")]) == 1, "logs/daily.log should be its own group")
        check(not any(k == "quarantine" for k, _ in g), "quarantine must never be archived (PII REJECT)")
        check(not any(k == "melon_raw" for k, _ in g), "melon_raw is layer-2, must not be archived")
        check(
            not any(f.name == "other.log" for files in g.values() for f in files),
            "logs/ must contribute daily.log only",
        )
        check(_unclassified(live) == ["newsource"], "a new dir under data/live must be reported unclassified")

        files = g[("chart", "2026-07-19")]
        a, b = _archive(files, live), _archive(list(reversed(files)), live)
        check(a == b, "archive must be deterministic (member order must not change bytes)")
        (live / "chart/apple/kr/2026-07-19.html").write_text("<html>CHANGED</html>", encoding="utf-8")
        check(_archive(_groups(live)[("chart", "2026-07-19")], live) != a, "content change must change the archive")

        with tarfile.open(fileobj=io.BytesIO(a), mode="r:gz") as tar:
            names = sorted(tar.getnames())
        check(
            names == ["chart/apple/kr/2026-07-19.html", "chart/apple/us/2026-07-19.html"],
            f"archive members must be live-relative posix paths, got {names}",
        )
        check(_key("chart", "2026-07-19", "live") == "live/chart/2026-07-19.tar.gz", "remote key shape")

        mpath = live / _MANIFEST_REL
        _manifest_save(mpath, {"live/chart/2026-07-19.tar.gz": {"sha256": "x", "size": 1}}, "b", "live")
        check(_manifest_load(mpath)["live/chart/2026-07-19.tar.gz"]["sha256"] == "x", "manifest roundtrip")
        check(_manifest_load(live / "backup/none.json") == {}, "missing manifest must read as empty, not crash")

        # 🔴 백업의 유일한 주장은 "되돌릴 수 있다"는 것이다. 원본을 풀어 바이트로 대조한다 --
        # 압축이 되는지가 아니라 **복원이 되는지**를 봐야 그 주장이 검사된 것이다.
        restored = Path(td) / "restored"
        for (kind, group), files in _groups(live).items():
            with tarfile.open(fileobj=io.BytesIO(_archive(files, live)), mode="r:gz") as tar:
                tar.extractall(restored, filter="data")
            for f in files:
                back = restored / f.relative_to(live)
                if not back.is_file() or back.read_bytes() != f.read_bytes():
                    check(False, f"restore mismatch in {kind}/{group}: {f.relative_to(live).as_posix()}")
        check(
            sorted(p.relative_to(restored).as_posix() for p in restored.rglob("*") if p.is_file())
            == sorted(f.relative_to(live).as_posix() for fs in _groups(live).values() for f in fs),
            "restored tree must be exactly the layer-1 set -- no more, no less",
        )

        # 내용이 그대로면 건너뛴다(멱등). 매니페스트를 실제 해시로 채우고 두 번째 실행이
        # 아무것도 올리지 않는지 본다 -- 이게 "하루 1.2MB"의 근거다.
        objs = {
            _key(k, gp, "live"): {"sha256": hashlib.sha256(_archive(fs, live)).hexdigest(), "size": 0}
            for (k, gp), fs in _groups(live).items()
        }
        _manifest_save(mpath, objs, "b", "live")
        buf2 = io.StringIO()
        stdout2, sys.stdout = sys.stdout, buf2
        try:
            rc = cmd_upload(live, "live", "b", dry_run=True)
        finally:
            sys.stdout = stdout2
        check(rc == 0, "dry-run with a matching manifest must succeed")
        check("would upload 0 object(s)" in buf2.getvalue(), f"unchanged content must upload nothing, got {buf2.getvalue()!r}")

        # --- 복원(_extract) — 백업이 하는 주장의 나머지 절반 ---
        arch = _archive(_groups(live)[("chart", "2026-07-19")], live)
        fresh = Path(td) / "bootstrap"          # 러너의 새 디스크
        w, s = _extract(arch, fresh, force=False)
        check((w, s) == (2, 0), f"bootstrap into an empty dir must write everything, got {(w, s)}")
        check(
            (fresh / "chart/apple/us/2026-07-19.html").read_bytes()
            == (live / "chart/apple/us/2026-07-19.html").read_bytes(),
            "bootstrap must restore byte-for-byte",
        )
        # 🔴 살아 있는 트리 위에서는 기본값이 **안 덮어쓰는 것**이다. 오늘의 관측을
        # 어제 것으로 되돌리는 일이 기본 동작이면 복원이 복구가 아니라 사고가 된다.
        victim = fresh / "chart/apple/us/2026-07-19.html"
        victim.write_bytes(b"<html>TODAY</html>")
        w2, s2 = _extract(arch, fresh, force=False)
        check((w2, s2) == (0, 2), f"existing files must be kept by default, got {(w2, s2)}")
        check(victim.read_bytes() == b"<html>TODAY</html>", "default restore must not clobber a live file")
        w3, _ = _extract(arch, fresh, force=True)
        check(w3 == 2, "--force must overwrite")
        check(victim.read_bytes() != b"<html>TODAY</html>", "--force must actually replace the file")

    for f in fails:
        _say(f"!! selftest: {f}")
    _say(f"selftest: {'FAILED' if fails else 'ok'} ({len(fails)} finding(s))")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="incremental backup of data/live layer-1 originals")
    ap.add_argument("--live", default="data/live", help="live data root (default data/live)")
    ap.add_argument("--prefix", default="live", help="remote key prefix (default 'live')")
    ap.add_argument("--bucket", default=None, help="bucket name (default $BACKUP_BUCKET or 'live-raw')")
    ap.add_argument("--dry-run", action="store_true", help="build archives, send nothing")
    ap.add_argument("--verify", action="store_true", help="list the remote and cross-check the manifest")
    ap.add_argument("--deep", action="store_true", help="with --verify: rebuild archives and compare hashes")
    ap.add_argument("--selftest", action="store_true", help="offline checks, no network")
    ap.add_argument("--init-bucket", action="store_true", help="one-time: create the bucket, always private")
    ap.add_argument("--restore", action="store_true", help="pull layer-1 back down (runner bootstrap / recovery)")
    ap.add_argument("--force", action="store_true", help="with --restore: overwrite local files that already exist")
    args = ap.parse_args(argv)

    if args.selftest:
        return cmd_selftest()
    if args.init_bucket:
        return cmd_init_bucket(args.bucket)
    live = Path(args.live)
    prefix = args.prefix.strip("/")
    dry = args.dry_run or os.environ.get("AI_DRYRUN", "") == "1"
    # 🔴 복원은 **없는 디렉터리에서 시작하는 것이 정상 경로**다(러너의 새 디스크). 아래
    # 존재 확인보다 먼저 갈라야 하며, 여기서 막으면 부트스트랩이 첫 줄에서 죽는다.
    if args.restore:
        return cmd_restore(live, prefix, args.bucket, args.force, dry)
    if not live.is_dir():
        _say(f"!! live root not found: {live}")
        return 2
    if args.verify:
        return cmd_verify(live, prefix, args.bucket, args.deep)
    return cmd_upload(live, prefix, args.bucket, dry)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
