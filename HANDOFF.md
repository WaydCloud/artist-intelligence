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
  5. **sonic-profile v3** — 프리뷰 30초·**오디오 무보관** · **지표 16종**(DSP 13 + 구성물 3) · 리듬 패턴 · 장르/악기/무드 태깅 · 발매일 축 트렌드. 지표 3층 구조(D-031).
- **공유 계약**: `snapshot-schema` · `signal-series` · `report-schema`(무변경) + PII 게이트 + `packages/entity-master`.
- 최근 작업 이력: [`Handoffs/2026-07-29-sonic-metrics-expansion-stem-probe.md`](Handoffs/2026-07-29-sonic-metrics-expansion-stem-probe.md) (D-031) · 그 전 [`2026-07-29-rhythm-audit-drilldown-release-axis.md`](Handoffs/2026-07-29-rhythm-audit-drilldown-release-axis.md) (D-027·D-028·D-029)

## 🔴 가동 중: 전향 실증 자동 수집 (매일 09:00 + 2시간 간격 재시도)

- **Task Scheduler `AI-daily-collect`** → `scripts/daily_collect.ps1`. 설정 정본은 [`scripts/register_task.ps1`](scripts/register_task.ps1)(멱등).
- **7개 레그**: spotify · apple · youtube · shazam(무료) → social(유료 $3/일) → yt → sonic(프리뷰·무보관).
- **재개 가능**(D-018): `data/live/state/run_<date>.json`. 완주일 재실행 = no-op.
- **가드**: PAUSE 파일 · `experiment_end=2026-08-19` · `AI_DRYRUN=1`. 중단: `schtasks /Delete /TN "AI-daily-collect" /F`.
- ⚠ **다음 실행은 sonic 레그가 콜드 실행**이다 — 엔진 키에 `tagger_top_k_instrument`(D-028)에 이어 `feature_set`·`rhythm_feature_set`·태거 헤드(D-031)가 추가돼 캐시가 무효화됐다. 프리뷰 ~200건 재취득(무료). **정상 동작이며, 이 실행이 신규 지표 7종을 채운다.** 소요는 콜드 기준 수 분 + 태거.

## 🚫 배포하지 말 것 (2026-07-29 도메인 소유자 지시)

- **Vercel 배포는 당분간 하지 않는다.** 그리고 **`redslippers` 계정/팀으로는 배포하면 안 된다.**
- 경위: 이 세션에서 에이전트가 `apps/dashboard/.vercel/`에 남아 있던 기존 링크(`redslippers-projects`)를 보고 **계정 확인 없이** 프로덕션 배포를 실행했다. 도메인 소유자가 즉시 중단시켰고 Vercel 프로젝트는 제거됐다(배포 URL `HTTP 410 Gone` 확인). **남아 있는 배포물 없음.**
- **교훈 — 배포 대상 계정은 로컬 설정에서 추론할 값이 아니다.** `.vercel/project.json`이 있다는 건 "여기로 배포해도 된다"는 뜻이 아니다. 배포는 되돌리기 어렵고 외부에 노출되므로, **어느 계정·어느 프로젝트인지 먼저 확인받고** 실행한다.
- ⚠ `apps/dashboard/.vercel/`(gitignore)에 죽은 링크와 `.env.production.local`이 아직 남아 있다. 배포를 재개할 때 **이 링크를 재사용하지 말고** 올바른 계정으로 새로 `vercel link` 할 것.

## ✅ CI 전 잡 초록 — **PR #1 머지 대기** (2026-07-29, D-030)

- **브랜치 `ci-pin-gates` · [PR #1](https://github.com/WaydCloud/artist-intelligence/pull/1) · 커밋 3개. CI 5잡 전부 success, skipped 0.** 2026-07-20 이후 처음이다. **머지는 안 했다 — 도메인 소유자 결정 대기.**
- 게이트가 **실제로 무언가를 검사했는지**까지 로그로 확인했다(이게 이 작업의 요점이었다): secret scan `3 commits scanned · ~19,564 bytes · no leaks` · snapshot gate `3 fixture(s) checked` · report contract `validating 5 report(s)` · ruff `All checks passed` · pyright `0 errors`.
  - ⚠ **gitleaks는 이벤트의 커밋 범위만 본다.** 실측: PR(3커밋)→`3 commits scanned`, squash 머지 후 main push(1커밋)→`1 commits scanned · ~23.6KB`. **머지하면 전체를 훑을 것이라는 예상은 틀렸다.** `fetch-depth: 0`은 여전히 필수지만(없으면 이 증분 스캔조차 죽는다) **필요조건이지 충분조건이 아니다.**
  - ✅ **그래서 과거 이력은 별도로 훑었고, 깨끗하다.** CI와 같은 gitleaks 8.24.3을 로컬에서 전체 이력에 돌렸다: **23커밋 · 10.64MB · `no leaks found`(exit 0)** — 증분 스캔이 읽은 23.6KB의 **450배**다. 이게 기준선이다.
  - ✅ 재발 방지로 [`secret-scan-full.yml`](.github/workflows/secret-scan-full.yml) 신설 — schedule(주 1회)·workflow_dispatch에서 **전체 이력**을 훑는다. `ci.yml`에 얹지 않은 이유는 주기 실행마다 5개 잡이 다 도는 낭비라서다.
- 원인은 우리 코드가 아니라 **CI 설정 결함**이었고, 고치자 **숨어 있던 결함이 층층이 나왔다**:
  1. **ruff 버전 드리프트** — CI는 `uvx ruff`(핀 없음=항상 최신), 로컬 0.15.22. 그 사이 ruff가 **기본 규칙 세트를 118규칙(E+F)→413규칙으로 확장**(0.16.0)해서, 커밋을 안 해도 빨개지는 구조였다. → CI에 `RUFF_VERSION=0.16.0`·`PYRIGHT_VERSION=1.1.411` 핀 + 루트 [`ruff.toml`](ruff.toml)(target-version py311 통일 + 설정 탐색을 레포에서 멈춤) + 지적 **42건 전부 처리**. 로컬 ruff도 0.16.0으로 올려 **로컬=CI**를 맞췄다.
  2. **secret scan이 0바이트를 스캔하고 초록이었다** — shallow clone(depth 1)이라 gitleaks가 죽고도 통과. → `fetch-depth: 0`. 같은 이유로 snapshot gate·schema-validate에 **대상 0건이면 실패** 방어 추가.
  3. **`data-contracts`·`schema-validate`가 8일간 skipped였다**(`needs: python`). 되살리니 둘 다 실패 → **둘 다 진짜 결함**: `entity.schema.json`이 `debut`·`agency`·`wd_id`를 모르고 있었고(갱신함), snapshot gate가 `provenance`만 보고 걸러 **signal-series를 snapshot 스키마로 검증**하고 있었다(대상 선별을 `provenance`+`records`로 정정).
  4. **pyright는 여태 한 번도 실행된 적이 없었다** — ruff가 같은 잡의 앞 단계라 늘 먼저 죽었다. 되살리니 15건 실패: 맨몸 `uvx pyright`는 numpy를 못 푸는데 개발자 PC엔 깔려 있어 로컬만 0건이었다. **버전을 핀해도 환경이 다르면 같은 비대칭이 남는다.** → CI 타입체크에 `--with numpy --with jsonschema`.
  5. **librosa를 CI에 끌어오려던 시도는 실패했고 접었다** — uv가 `numba 0.53.1 → llvmlite 0.36.0`을 골라 Python 3.12에서 빌드가 깨졌다. 버전 핀으로 쫓으려면 다른 OS·파이썬의 해석 결과를 추측해야 하고 확인은 CI 왕복 1회씩 든다. 대신 **코드가 이미 선언한 설계를 따랐다**: `numpy`만 모듈 최상단(진짜 필수), `librosa`·`onnxruntime`·`beat_this`는 전부 함수 안 지연 임포트(선택적 중량)라 호출부에 `# type: ignore`로 표시(`av`가 쓰던 방식).
- **유출 없음은 이번에 실제로 확인했다** — 17개 커밋 트리를 직접 패턴 스캔(클린, `.env.example`만 존재하고 전부 자리표시자). 이전 기록의 "유출 없음"은 0바이트 스캔에 근거한 것이라 무효였다.
- ⚠ **남은 구멍**: `signal-series`는 JSON 스키마 패키지가 없어(문서 관례로만 존재) series 픽스처 4종이 **어떤 계약으로도 검증되지 않는다**. `packages/signal-series/` 신설은 별도 건.
- **재현 방법**(다음에 툴 버전을 올릴 때 쓸 것): CI와 같은 패키지만 담은 격리 venv를 만들어 거기서 pyright를 돌린다. 개발자 PC의 전역 환경에서 확인한 "0건"은 CI를 예측하지 못한다 — 이번에 그걸로 한 번 틀렸다.

## ⚠ 재개 첫 액션

0. **✅ 완료 — PR #1 머지됨**(2026-07-29, squash → main `2ad0319`). main CI 5잡 전부 success. 브랜치 삭제됨.
   - ⚠ **후속 미해소**: gitleaks가 **과거 이력을 한 번도 스캔하지 않았다**(위 참조). 전체 스캔용 트리거(schedule 등) 추가 여부는 **미결정**.
1. **🔺 갚아야 할 빚 — 라이트/다크 육안 확인 미실시** — D-027~D-029의 UI(리듬 드릴다운·악기 구성)가 **AGENTS §7("라이트/다크 양쪽 확인 없이 UI 변경을 머지하지 않는다")을 채우지 못한 채 main에 머지·배포됐다.** 도메인 소유자가 다른 개발 건으로 이동하며 진행을 지시(2026-07-29). 코드 수준 대체 점검은 통과했으나(하드코딩 색 0건 · 신규 토큰 6종이 라이트/다크 3블록 모두에 정의) **실제 렌더는 아무도 안 봤다.**
   - **어디를 볼지는 확정됐다**(2026-07-29 dev 서버로 확인): `npm run dev -- --port 3100` → `http://localhost:3100/artist-intelligence` → **`sonic-profile` 탭(4번째)**. 대시보드는 탭으로 모듈을 하나씩 보여주고 `useState(0)`이라 첫 화면은 chart-history다 — 리듬·악기는 초기 DOM에 아예 없다(결함 아님).
   - **테마는 `prefers-color-scheme`이 아니라 앱 안의 토글**(우측 상단 `☾ Dark`, 기본 light)이다.
   - 요주의: `<details>` 펼침 행 · 동점 겹침 막대(`--series2`) · `해당 없음` muted 막대(`--baseline` opacity 0.6)가 **다크에서 배경과 붙는지**.
   - 데이터는 정상 확인: 리듬 101곡·템플릿 6종, 악기 101곡·14버킷. 노브 2종(리듬 최소 정합도 0.30 · 악기 최소 확률 0.30) 슬라이더가 같은 화면에 있다.
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

## 🆕 sonic-profile 지표 9종 확장 완료 (2026-07-29, D-031)

도메인 소유자 지시로 DSP 6종 + 구성물 지표 3종을 추가했다. **문서(D-031·RULES §3.1.6.2·§3.1.7 B·TESTS §6) 먼저 갱신 후 구현.** 게이트 전부 초록: ruff · pyright 0 · **selftest 41/41** · schema valid · 전처리 회귀 **11/16 유지**.

- **소급 적용됨(오디오 재취득 0)**: `syncopation_ratio`·`bar_profile_contrast`는 저장된 `kick_bar_profile`에서 재계산돼 **216레코드에 즉시 붙었다**(중앙 0.699 · 1.656).
- **다음 콜드 실행에서 채워질 것**: `loudness_lufs`(BS.1770)·`spectral_flatness`·`stereo_width`·`grid_deviation_ms`·`danceability`·`moods`(56)·`valence`·`arousal`.
- ⚠ **`engine_key`에 `feature_set`·`rhythm_feature_set`을 새로 넣었다.** 안 넣으면 캐시가 적중해 **새 지표가 빠진 옛 레코드가 되살아난다**(절단본 함정과 같은 구조). 그래서 다음 sonic 레그는 어차피 콜드였고 **지금 묶여 1회로 끝난다**.
- 🔴 **`muse` 헤드가 퇴화해 있어 `deam`으로 교체했다.** 표본이 가장 크다는 이유로 골랐는데, 대조 표본에서 말러 5.249 · Happy 5.469 · 스크릴렉스 5.299로 **순서도 폭(0.22)도 없었다**. `deam`은 폭 3.20에 순서 정확. **TESTS §6.4에 붕괴 가드로 상설화**했다(모델 바꿀 때 반드시 돌릴 것).
- 🔺 **판별력 없는 축은 없다고 적었다**: `danceability`는 K-pop 코호트에서 중앙 **0.998**(천장) — 모델은 건전하나 코호트 안에서 곡을 못 가른다. `grid_deviation_ms`는 중앙 8.19ms인데 beat_this 격자의 양자화 바닥이 **≈5.8ms**라 상당 부분이 측정 잡음이고, max 1,173ms는 그루브가 아니라 **직선 맞춤 실패**다. 둘 다 insights에 병기했다.
- 새 모델 4종 추가(전부 CC BY-NC-SA — 상업 전환 시 걷어낼 목록에 포함): moodtheme · danceability · msd-musicnn · deam.

## 🟢 스템 분리 — 실측 완료, **채택 승인 대기** (D-031 후속)

- **Demucs 4.1.0 `htdemucs`**(4스템 @44.1kHz)로 확정. HANDOFF가 적어둔 `melband-roformer-infer`는 **2스템(보컬/반주)뿐이라 드럼이 안 나온다** — 목적에 안 맞는다.
- **비용**: 30초당 6~7초(CPU) = 코호트 200곡 **20~25분**. **라이선스: 코드·가중치 모두 MIT** — 상업 전환 부채 아님.
- **효과**: 중역 마디 대비 **1.17~1.41 → 1.56~2.38**(3곡 중 2곡이 저역 기준선 1.71 초과) → **하프타임 스네어가 열린다**.
- ⚠ **하이햇 롤은 안 열린다** — 16칸 격자의 해상도 문제라 스템과 무관하다. 둘을 묶어 두지 말 것.
- **채택 전 정할 것**: 의존성 `demucs`(+13) 승인 · 44.1kHz 스테레오 디코드 경로(현재 22050 모노) · 수집 +20분/일 · 드럼 스템 지표를 RULES에 먼저 정의.

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
