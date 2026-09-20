# HANDOFF · 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 🧭 다음 행선지 (재개점)

# 🔵 **페이지가 50일치를 따라잡았다. sonic 코호트는 오늘 09:00부터 다시 찬다** (2026-09-21)

> 📄 이전 세션 이력 = [`Handoffs/2026-08-02-runner-full-leg-and-canon-corpus.md`](Handoffs/2026-08-02-runner-full-leg-and-canon-corpus.md) · 이번 결정 = [`docs/DECISIONS.md`](docs/DECISIONS.md) **D-061**
> PR [#21](https://github.com/WaydCloud/artist-intelligence/pull/21) **머지됨**(`6c1552c`) · 배포 **완료** → https://artist-intelligence-mocha.vercel.app
> 공개 페이지가 `2026-09-20` 데이터로 선다. 다른 컴퓨터에서도 같은 데이터를 본다.

## VERIFY: GREEN · E2E: 미검증 (사용자가 아직 눌러보지 않았다)

| 게이트 | 결과 |
|---|---|
| `ruff@0.16.0 check modules scripts` | All checks passed |
| `pyright@1.1.411 modules` | 0 errors, 0 warnings |
| `validate_report_data.py --selftest` | 90/90 |
| `validate_report_data.py` | **CLEAN 6/6** (세션 시작 시점 FAILED 1/6) |
| `validate_coverage.py --selftest` | **11/11** (신규) |
| `validate_coverage.py data/live/sonic` | **RED 16일** (설계대로. 09-05~09-20 장애 구간을 잡는다) |
| report-schema (6개) | 전부 valid |
| `sonic_profile selftest` · `genre_impulse selftest` | all passed · 17 passed |
| dashboard `lint` · `typecheck` | 통과 |
| `smoke:tabs` | **12/12 PASS** (라이트 · 다크) |

🔴 **E2E가 남았다.** `npm run dev -- --port 3100` 으로 띄워 6탭을 직접 눌러보는 단계는 하지 않았다. §5 항목 8대로 **다음 세션이 새 작업보다 먼저** 한다.

## 이번 세션에 닫힌 것

**1. 3층이 1층을 따라잡았다.** 커밋된 리포트는 `2026-08-01`, 로컬 수집은 `09-20`까지 와 있었다. daily는 50일간 정상으로 돌았고 1층은 쌓였는데 **리포트를 다시 만들어 커밋하는 사람이 없었다.**

| 모듈 | 무엇이 들어왔나 |
|---|---|
| chart-history | 191 스냅샷 · 51시장 · 07-17~09-20 |
| **fandom-pulse** | **30게시물 1태그 → 5,175게시물 12태그** (01-21~08-17) |
| yt-pulse | 3,235 영상 레코드 |
| signal-bridge | 차트 65일 × 11,191팀 · 두 신호 다 있는 팀 230 |
| sonic-profile | 관측 3,280곡 · 미해석 2,753곡 |
| genre-impulse | 코호트 8곡 · 매치 1건 (아래 장애 구간) |

- ✅ **fandom `analyze` 레그를 daily에 넣었다.** `signals`만 돌고 `report`는 2026-07-30 이후 한 번도 안 만들어지던 구조였다. 3층이 1층을 **같은 실행에서** 따라가야 멈춘 것이 보인다.

**2. 계약 게이트가 빨갛던 것을 고쳤다.** sonic 추론이 없는 차트(`age-hist`)를 가리키고 있었다. 최신 코호트에 발매일이 없으면 그 차트는 안 만들어지는데 추론은 조건 없이 나갔다. 질문(R1)에만 걸려 있던 앵커 규율을 추론에도 걸었다.

**3. 팬덤 문구 셋이 데이터를 앞질렀다.** 제목이 태그 12종을 `#` 하나 뒤에 이어붙였고(`#babymonster,cortis,...`), 부제가 08-17까지의 표본에 `수집 2026-07-19`라고 적었고(병합본이 **첫** 스냅샷의 `fetched_at`을 물려받는다), "해시태그 하나뿐이다"가 12종인 채로 남아 있었다. D-060의 36~38번과 **정확히 같은 자리**다.

## 🔴 이번 세션의 결함 둘 · **둘 다 "모듈은 정상 종료했다"**

### 39. Apple KR 스토어프런트가 16일간 죽어 있었는데 아무 데서도 빨개지지 않았다

2026-09-05부터 iTunes `search`가 `country=KR`에만 결과 0을 돌려줬다. 차트 코호트는 그 하나에만 의존했다.

```
09-03  해석  66/108      09-05  해석   8/111
09-04  해석  65/109      ...    09-20 까지 8 고정
```

- **실패가 빨간 X가 아니라 작아진 표본으로 나타났다.** CLI는 exit 0, 스키마 유효, CI 초록. 리포트가 `미해석 103곡`이라고 정직하게 적고 있었지만 **그 숫자를 읽는 게이트가 없었다.**
- 고침은 D-061. `lookup` 엔드포인트는 KR에서 멀쩡하다는 것도 같이 쟀다(그래서 `lookup_preview`는 안 건드렸다).
- ✅ **게이트를 만들었다**: `scripts/validate_coverage.py`. 판정 둘을 함께 쓴다.
  - **하락** 앞 7일 해석률 중앙값 대비 50% 이상 하락. 기준선이 어제 하나뿐이면 깨진 날이 깨진 날과 비교돼 둘째 날부터 조용해진다.
  - **바닥** 절대 해석률 30% 미만. 하락 규칙만 두면 창이 깨진 날로 차는 순간 조용해진다. 실측으로 **끊김 17일 중 4일만** 잡았다. 바닥이 나머지를 들고 간다.
  - 🔑 **바닥 30%는 고른 값이 아니라 읽은 값이다.** 정상 39일은 54.1% 밑으로 간 적이 없고 장애 16일은 전부 7.2%였다. 그 사이는 55일간 관측 0이다.
  - 실측: 정상 39일 조용 · 장애 **16일 전부 검출** · 오탐 0. CI는 `--selftest`(1층이 없다), 러너는 실측 판정.

### 40. 워치리스트 출처가 8월부터 날마다 apple↔deezer로 뒤집히고 있었다

39번을 재다가 나왔고 **더 오래됐고 더 넓다.** `candidates()`가 apple·deezer 후보를 합쳐 돌려주고 호출부는 먼저 디코드되는 것을 쓴다. 그래서 그날 어느 쪽이 답했느냐가 **어떤 녹음을 재는가**를 정했다.

| act | apple 중앙값 | deezer 중앙값 | 차이 |
|---|---|---|---|
| CORTIS | 0.5740 (8일) | 0.2960 (46일) | **48.4%** |
| BABYMONSTER | 0.6921 (12일) | 0.4556 (43일) | **34.2%** |
| izna | 0.6670 (11일) | 0.4836 (44일) | **27.5%** |
| KATSEYE | 0.4990 (14일) | 0.6350 (41일) | **27.3%** |

- ⚠ **고치지 않았다.** 신뢰도 라인이 출처 혼재를 말하게 하는 것까지만 했다. 어떤 녹음을 정본으로 삼을지는 **측정 모집단을 정하는 판단**이라 도메인 몫이다(`AGENTS.md` §2.1). 선택지 셋은 D-061에 적었다.
- 🔺 **배운 것**: 값이 그럴듯하면 출처가 바뀐 것을 아무도 못 본다. 지표 옆에 **그 값이 어디서 왔는지**가 없으면 시계열의 계단은 언제나 음악 이야기로 읽힌다.

## 다음 세션이 할 일 (순서대로)

1. 🔴 **E2E.** dev 띄우고 6탭을 눌러본다. 특히 팬덤 탭(표본이 172배가 됐다)과 sonic 신뢰도 라인의 출처 표기.
2. 🔴 **오늘 09:00 수집 뒤 리포트를 다시 만든다.** 폴백이 실제 daily에서 도는지 확인하는 자리다. 기대값: 차트 코호트 해석 8 → 80대, `preview_market`에 US·GB가 찍힘.
   ```bash
   PYTHONPATH=modules/sonic-profile/src python -m sonic_profile analyze data/live/sonic --watchlist packages/entity-master/watchlist.json -o modules/sonic-profile/output/
   PYTHONPATH="modules/genre-impulse/src;modules/sonic-profile/src" python -m genre_impulse analyze --sonic data/live/sonic --watchlist packages/entity-master/watchlist.json -o modules/genre-impulse/output/
   node apps/dashboard/scripts/collect-reports.mjs && python scripts/validate_report_data.py
   ```
0. 🔴 **오늘(09-21) 09:00 수집이 끝났으면 한 명령으로 페이지를 갱신한다.** 배포된 페이지의 sonic 코호트가 아직 8곡이다.
   ```powershell
   .\scripts\refresh_and_deploy.ps1          # 재생성 + 게이트 + 커밋 + push + 빌드 + 배포
   .\scripts\refresh_and_deploy.ps1 -NoDeploy  # 커밋까지만
   ```
3. **결함 40의 값 판정**을 받는다(D-061 선택지 ㉠㉡㉢). **이것만 남은 미결 판단이다.**
4. 커버리지 게이트의 **바닥값을 다른 스토어에도 쓸지** 본다. 지금 30%는 `data/live/sonic` 55일에서 읽은 값이고, 코호트 성격(시장·상위 N)이 바뀌면 다시 읽어야 한다.
5. push·PR은 **아직 안 했다.** 올릴지는 별도 승인.

## 갈래 ② 정답지 코퍼스 · 그대로 멈춰 있다

[`docs/DRAFT-answer-sheet-corpus.md`](docs/DRAFT-answer-sheet-corpus.md) · 10케이스 중 3종 수집(`jersey-club` · `ukg-dnb` · `drill`). 남은 7종과 `drill` 둘째 출처는 2026-08-02 이후 진척 없다. 이전 핸드오프의 갈래 ② 절을 그대로 이어받는다.

## 이번 세션의 미결 판단 하나

🔴 **결함 40(출처 혼재)의 값은 안 정했다.** 화면이 그 사실을 말하게 하는 것까지만 했다.
어떤 녹음을 정본으로 삼을지는 측정 모집단을 정하는 판단이라 `AGENTS.md` §2.1대로 도메인 소유자 몫이다.

| 선택지 | 무엇 | 대가 |
|---|---|---|
| ㉠ | act마다 정본 `track_id`를 고정하고 `lookup_preview`로 같은 녹음을 다시 잰다 | 신곡이 나왔을 때 갱신 규칙이 따로 필요하다 |
| ㉡ | apple을 절대 우선으로 두고 deezer는 apple이 전무할 때만 쓴다 | apple이 못 잡는 날은 결측이 는다 |
| ㉢ | 현행 유지 + 출처를 화면에 싣는다 (지금 상태) | 시계열의 계단이 남는다. 읽는 사람이 출처 라인을 봐야 한다 |

## 🔴 배포에서 나온 것 (결함 41 · 42)

**41. 공개 페이지의 링크가 전부 404였다.** `out/`을 그대로 올리면 `artist-intelligence.html`이 `/artist-intelligence`로 열리지 않는데, 페이지 자신의 링크가 `href="/artist-intelligence"`다. 홈에서 **무엇을 눌러도 404**였고, 첫 배포 직후 실측으로 잡았다.
- 고침: `apps/dashboard/public/vercel.json`에 `cleanUrls`. `public/`은 빌드가 `out/`으로 복사하므로 배포 루트에서 읽히고 저장소에 남는다.
- 배포 후 실측: `/` · `/artist-intelligence` · `/labs` · `/utilities` 전부 200.
- 🔺 **빌드가 통과한 것과 올라간 것이 동작하는 것은 다르다.** `smoke:tabs` 12/12는 dev 서버에서 돈 것이고, 정적 호스트의 라우팅은 거기 없다.

**42. 배포 중 `out`이라는 프로젝트가 실수로 하나 생겼다.** `vercel deploy`가 `out/.vercel/project.json`을 덮어써서 새 프로젝트를 만들었다(`prj_nbXYj9Y7delQzrGL41oVgeaBuCW1` · `out-gamma-teal.vercel.app`).
- ⚠ **지우지 않았다.** 프로젝트 삭제는 비가역이고 사용자 계정이라 판단을 받는다. 내용은 이번 정적 빌드 1건뿐이다.
- 재발 방지: `refresh_and_deploy.ps1`이 배포 직전에 링크를 매번 복원한다.

## 손대지 않은 것 (알고 남긴 것)

- **1층 과거 스냅샷.** 09-05~09-20의 미해석 구간은 **장애가 있었다는 증거 그 자체**다. 덮어쓰지 않는다.
- **`data/live/social_merged.json`의 `provenance.note`.** 스냅샷 스키마가 `additionalProperties: false`라 `validate_snapshot.py`가 INVALID를 낸다. CI는 픽스처만 검사해서 빨개지지 않는다. **범위 밖이라 안 고쳤다.**
- **`data/live/sonic/2026-09-21.json`.** 지금 쓰면 09:00 정기 실행이 "이미 받음"으로 sonic 레그를 건너뛰어 **어제 차트 코호트로 오늘을 잰다.**
- **Vercel `out` 프로젝트**(결함 42). 지울지는 사용자 판단.
