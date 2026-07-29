# HANDOFF — 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 현재 위치 (2026-07-29)

- 프로젝트: `C:\Projects\artist-intelligence`. 로컬: Python 3.14.5 · Node 24 · **Windows(win32/AMD64)**. Docker Desktop/WSL2 있음.
- **바닥 전제(D-006)**: **책임소재 불변식**(판단=책임질 인간·도구=증거에서 종료) + **기준 원장**(엔지니어=형식/도메인 소유자=값). 정본 `DOMAIN.md §0`·`AGENTS.md §2.1·§5`. **모든 신규 모듈 구속.**
- **모듈 5종** 모두 핵심 흐름(`모듈 CLI → 스키마 유효 report.json → 대시보드`) 관통:
  1. **chart-history v5** — 차트 5렌즈(Spotify·Apple·YouTube·Shazam·멜론 세션보조) · 통합 진입 지도 · `tracks` 명령(D-007).
  2. **fandom-pulse v3.1** — IG 해시태그 화력·참여·모멘텀 + 이중 귀속 + 은어 태그 51종.
  3. **signal-bridge v2** — 3소스 조인·분류 + 원인분석 레이어(D-021).
  4. **yt-pulse v1** — 워치리스트 공식 채널 velocity·신작.
  5. **sonic-profile v2.2** — 프리뷰 30초·**오디오 무보관** · DSP 7지표 · 리듬 패턴 · 장르/악기 태깅 · **발매일 축 트렌드**.
- **공유 계약**: `snapshot-schema` · `signal-series` · `report-schema`(무변경) + PII 게이트 + `packages/entity-master`.
- 최근 작업 이력: [`Handoffs/2026-07-29-rhythm-audit-drilldown-release-axis.md`](Handoffs/2026-07-29-rhythm-audit-drilldown-release-axis.md) (D-027·D-028·D-029)

## 🔴 가동 중: 전향 실증 자동 수집 (매일 09:00 + 2시간 간격 재시도)

- **Task Scheduler `AI-daily-collect`** → `scripts/daily_collect.ps1`. 설정 정본은 [`scripts/register_task.ps1`](scripts/register_task.ps1)(멱등).
- **7개 레그**: spotify · apple · youtube · shazam(무료) → social(유료 $3/일) → yt → sonic(프리뷰·무보관).
- **재개 가능**(D-018): `data/live/state/run_<date>.json`. 완주일 재실행 = no-op.
- **가드**: PAUSE 파일 · `experiment_end=2026-08-19` · `AI_DRYRUN=1`. 중단: `schtasks /Delete /TN "AI-daily-collect" /F`.
- ⚠ **다음 실행은 sonic 레그가 콜드 실행**이다 — 엔진 키에 `tagger_top_k_instrument`가 추가돼 캐시가 무효화됐다(D-028). 프리뷰 ~200건 재취득(무료). 정상 동작이니 놀라지 말 것.

## 🚫 배포하지 말 것 (2026-07-29 도메인 소유자 지시)

- **Vercel 배포는 당분간 하지 않는다.** 그리고 **`redslippers` 계정/팀으로는 배포하면 안 된다.**
- 경위: 이 세션에서 에이전트가 `apps/dashboard/.vercel/`에 남아 있던 기존 링크(`redslippers-projects`)를 보고 **계정 확인 없이** 프로덕션 배포를 실행했다. 도메인 소유자가 즉시 중단시켰고 Vercel 프로젝트는 제거됐다(배포 URL `HTTP 410 Gone` 확인). **남아 있는 배포물 없음.**
- **교훈 — 배포 대상 계정은 로컬 설정에서 추론할 값이 아니다.** `.vercel/project.json`이 있다는 건 "여기로 배포해도 된다"는 뜻이 아니다. 배포는 되돌리기 어렵고 외부에 노출되므로, **어느 계정·어느 프로젝트인지 먼저 확인받고** 실행한다.
- ⚠ `apps/dashboard/.vercel/`(gitignore)에 죽은 링크와 `.env.production.local`이 아직 남아 있다. 배포를 재개할 때 **이 링크를 재사용하지 말고** 올바른 계정으로 새로 `vercel link` 할 것.

## ❌ CI 적색 (2026-07-29)

- **main = `bcbb3fb`** (fast-forward, `audio-analysis-v2`에서). 로컬 게이트 전부 통과: ruff · pyright 0 · selftest 26/26 · 5모듈 schema valid · dashboard lint·tsc·build.
- **CI는 2026-07-20부터 5연속 적색이며, 이번 머지 이전부터 그랬다.** 두 원인 모두 우리 코드 결함이 아니라 **CI 설정 결함**이다:
  1. **secret scan — 실패지만 유출은 없다. 더 나쁜 건 스캔을 안 하고 있었다는 것.** 로그: `no leaks found in partial scan` · `scanned ~0 bytes (0)`. `actions/checkout@v4`가 shallow clone(depth 1)이라 gitleaks가 잡은 커밋 범위(`<base>^..<head>`)의 베이스가 로컬에 없어 `fatal: ambiguous argument`로 죽는다. **즉 이 보안 게이트는 통과해도 아무것도 검증하지 않는다** — 적색이 오히려 사실을 말해주고 있었다. 고침: security 잡의 checkout에 `with: { fetch-depth: 0 }`.
  2. **ruff — 버전 드리프트.** CI는 `uvx ruff`(=항상 최신), 로컬은 **0.15.22**. 최신 쪽에서 31건(RUF046·RUF100 등)이 새로 뜬다. **레포에 루트 ruff 설정이 없어** 규칙 세트가 디렉터리마다 갈린다(`pyproject.toml`은 chart-history·fandom-pulse에만 있고 sonic-profile·signal-bridge·yt-pulse는 ruff 기본값). 고침: CI에서 ruff 버전 핀 + 루트 `ruff.toml` 신설 → 그 다음에 31건 처리. **핀 없이 31건만 고치면 다음 릴리스에 또 깨진다.**
  - ⚠ 위 두 개는 **로컬에서 재현되지 않는다** — 로컬 게이트를 다 통과해도 CI는 빨갛다. 이 비대칭 자체가 고쳐야 할 대상이다.

## ⚠ 재개 첫 액션 후보

1. **🔺 갚아야 할 빚 — 라이트/다크 육안 확인 미실시** — D-027~D-029의 UI(리듬 드릴다운·악기 구성)가 **AGENTS §7("라이트/다크 양쪽 확인 없이 UI 변경을 머지하지 않는다")을 채우지 못한 채 main에 머지·배포됐다.** 도메인 소유자가 다른 개발 건으로 이동하며 진행을 지시(2026-07-29). 코드 수준 대체 점검은 통과했으나(하드코딩 색 0건 · 신규 토큰 6종이 라이트/다크 3블록 모두에 정의) **실제 렌더는 아무도 안 봤다.** 재개 시 첫 액션으로 `/artist-intelligence`를 양쪽 테마로 열 것 — 요주의는 `<details>` 펼침 행, 동점 겹침 막대(`--series2`), `해당 없음` muted 막대(`--baseline` opacity 0.6)가 다크에서 배경과 붙는지.
2. **`data/live/`는 gitignore** — 복구한 101곡 악기 라벨이 **이 PC에만** 있다. 유실 시 `retag`로 재복구는 되지만(멱등), 관측 이력이 git 밖이라는 점은 아래 서버 논의의 실질 쟁점이다.
3. **`check-dev-off` 가드의 실제 걸림돌은 3000이었다** — 3100(우리 dev)을 내려도 `C:\Projects\Redslippers 2`의 dev가 3000을 물고 있어 막힌다. 가드 주석이 예외로 적어둔 경우이므로 전면 우회(`AI_ALLOW_BUILD=1`)가 아니라 **`$env:AI_DEV_PORTS='3100'`으로 검사 범위만 좁힐 것** — 우리 dev 보호는 살아 있다.

## 🟡 논의 중 — 상시 서버 / 트랙 원장 저장 형태 (미결정)

도메인 소유자가 **NestJS 도입까지 검토** 중. 동기는 "상시 서버가 있으면 컴퓨터에 의존하지 않아도 됨". 이어서 논의할 때 쓸 정리:

- **세 관심사가 한 덩어리로 묶여 있는데 따로 풀린다**: (a) 수집이 내 PC에 묶임 · (b) 데이터 저장 형태 · (c) 조회·서빙.
- **(a)가 실제 통증인데 NestJS는 그걸 풀지 않는다** — 수집·분석이 전부 Python(librosa·torch·onnxruntime·PyAV)이라 NestJS는 Python 워커 오케스트레이터가 될 뿐이고, NestJS 서버 자체도 어딘가에서 돌아야 한다(같은 PC면 의존 그대로).
- **(a)만의 최저비용 답**: 수집을 **GitHub Actions cron**으로 이전 → 서버·DB 없이 PC 의존 소멸, 결과 커밋, git이 곧 이력. 걸리는 것: 유료 소셜 레그 키를 CI 시크릿으로, **MCP 레그(멜론)는 대화형 인증이라 헤드리스 불가**(별도 경로 필요), 모델·torch 캐시 단계.
- **문서 상태**: `ARCHITECTURE.md`는 `금지: 임의 라이브 백엔드·인증/DB`, **D-003**은 "라이브 분석이 필요해지면 **Python 비동기 워커(Modal 1순위)**로 분리"로 이미 정해져 있다. NestJS 도입은 규칙 위반이 아니라 **결정 번복**이며 근거를 새 결정으로 남기면 된다.
- **서버가 정당해지는 조건**: ① 여러 사람/기기가 **쓰기** ② 온디맨드 분석(곡을 던지면 즉석 분석) ③ JSON-in-git이 감당 못 할 규모. 현재 102트랙·일 1회라 셋 다 아님. **미확인 전제**: 협업자 유입 계획·온디맨드 요구가 있으면 답이 달라진다.
- **트랙 원장 설계안(보류)**: 날짜 스냅샷 = 관측(순위·코호트) / 트랙 원장 = 녹음의 성질(발매일·지표·최초·최종 관측). 지금은 `cache.json`이 그 역할을 겸하는데 **엔진 키가 바뀌면 통째로 버려진다** — 관측 이력이 캐시에 얹혀 있으면 안 된다는 것이 분리 근거.

## ⚠ 도메인 소유자 결정 대기 (엔지니어가 정할 수 없는 값)

전부 **관습값**이며 결과를 보기 전에 정하는 것이 옳다(AGENTS §2.1 케이스 오버핏 경계). `min_posts` 기본 20과 같은 성격.

| 기준 | 기본값 | 어디에 |
|---|---|---|
| 리듬 유형 배정 임계 θ | 0.30 | `--rhythm-min-match` · 튜너 |
| 동점 폭 | 0.05 | `--rhythm-tie-gap` · 튜너 |
| 악기 검출 확률 | 0.30 | `--min-prob` · 튜너 |
| 신곡 경계 | 90일 | `--new-release-days` |
| 빈티지 칸 최소 표본 | 3곡 | `VINTAGE_MIN_N` |
| 소셜 최소 표본 | 20건 | `--min-posts` (signal-bridge) |

- **`tresillo(16분·반마디)` 제거 여부** — 관용 패턴이 아니라 제거를 권고했으나 값은 도메인 소유자 소유라 이름만 바로잡고 남겼다(현재 5곡 배정).
- **`dembow` 템플릿의 정체** — 킥+스네어 합주 패턴인데 프로파일은 킥만 접는다. 무엇을 재고 있는지 **스템 분리 전까지 불확실**(6곡).

## ⚠ sonic-profile 축에서 이어서 할 것

1. **사람 라벨 50~100곡** — 장르·악기 **정확도 미측정**. 지금은 `정확도 미측정`을 병기하고 단독 근거 사용을 금지 중. 이걸 재야 원장이 완성된다(RULES §3.1.7).
2. **스템 분리** — **트랩·저지클럽 판별 불가**(하이햇 롤·하프타임 스네어). 중역 대비 1.22가 원인이며 악기 태깅 정확도도 같이 오른다. `melband-roformer-infer`가 cp314에서 해석됨(비용·체크포인트 라이선스 미검증).
3. **다운비트 실음악 검증** — 합성 픽스처는 다운비트를 과소평가한다. 정답 채보 코퍼스(AI Hub 등) 필요. 그전까지 `beats_per_bar`는 집계 전용.
4. **상업 전환 시** — 태거 가중치가 CC BY-NC-SA라 **먼저 걷어내야 한다**(RULES §3.4). 비상업 확인은 2026-07-29 도메인 소유자.
5. **30초 발췌 천장** — 곡 구조·전곡 다이내믹 아크·드롭 타이밍은 원리적으로 불가(SPEC §6 밖). **Apple/유통사 라이선스 문의가 실질적 잠금 해제**(멜론 화이트리스트와 같은 경로).

## 그 외 대기 목록

- **멜론 복구**: 삭제 원인(D-018 ⑦)은 고쳤다. 대화형 세션에서 `/mcp` 재연결 → 4콜 → `convert-melon`이면 4번째 렌즈 복귀. 화이트리스트 회신 대기.
- **yt-pulse v2**(레이블 채널 영상 레지스트리·댓글 밀도) · **댄스 모듈 v1**(문서만 존재, sonic-profile과 온셋 추출 공유 예정) · 케이스 스터디 · Vercel 배포 · 써클차트 제휴.

## 참고 — 종료된 조사 (재조사 불필요)

- MERT·MuQ·CLaMP 3 = 라이선스 배제 · CLAP 제로샷 태깅 = 붕괴(24/26 동일 라벨) · AST 악기 = 실패 · AudioSet에 저지클럽·뭄바톤 라벨 없음. 상세는 [`docs/INVESTIGATION-audio-engine.md`](docs/INVESTIGATION-audio-engine.md) 1~3부.
- **Essentia**: PyPI 휠이 macOS·manylinux뿐 — Windows 설치 불가(단 ONNX 직접 구동으로 우회 완료, D-026). **madmom**: `numpy<1.20`으로 Python ≤3.9 고착. **Demucs**: 저장소 아카이브됨(현 SOTA는 BS-RoFormer 계열). **AcousticBrainz**: CC0 756만 레코딩이나 2022년 수집 중단 → 과거 기준선 전용.
- **한국 저작권법에 TDM 면책 조항 없음**(개정안 계류). YouTube ToS는 다운로드 명시 금지. → 오디오 취득 경로는 프리뷰(회색) 또는 라이선스(백색)뿐.

## 로컬 실행 메모

```bash
# ── 전체 daily 1회 (재개 가능·멱등, 완주일이면 no-op)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\daily_collect.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_task.ps1 [-WhatIf]

# ── sonic-profile  (콘솔이 cp949라 PYTHONIOENCODING=utf-8 필요)
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile selftest          # 26/26, 네트워크 0
PYTHONPATH=modules/chart-history/src python -m chart_history tracks \
  --store data/live/chart/apple/kr --top 100 -o data/live/sonic/cohort.json
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile fetch \
  --watchlist packages/entity-master/watchlist.json --cohort data/live/sonic/cohort.json \
  -o data/live/sonic/<date>.json                                               # 오디오 미저장
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile analyze data/live/sonic \
  --watchlist packages/entity-master/watchlist.json -o modules/sonic-profile/output/
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile retag data/live/sonic --dry-run
                                                                # 상위 k 절단 복구(멱등)

# ── 브리지(원인분석 레이어)
PYTHONPATH=modules/signal-bridge/src python -m signal_bridge analyze \
  --social data/live/social_series.json --chart data/live/chart_series.json \
  --youtube data/live/yt_series.json --theta-rank 200 --focus-social --min-posts 20 \
  --watchlist packages/entity-master/watchlist.json -o modules/signal-bridge/output/

# ── 상태·게이트
python scripts/bridge_summary.py · Get-ChildItem data\live\state
python -m ruff check modules/ scripts/ · python -m pyright modules/<m>
node apps/dashboard/scripts/collect-reports.mjs
cd apps/dashboard && npm run dev -- --port 3100    # 3000은 다른 프로젝트가 점유 중
```
