# HANDOFF — 다음 행선지

> **이 파일은 쌓이지 않는다.** 항상 "지금 어디서 재개할지"만 가리킨다(매 핸드오프마다 덮어씀).
> 과거 기록은 [`Handoffs/`](Handoffs/), 결정 이유는 [`docs/DECISIONS.md`](docs/DECISIONS.md).
> 새 세션은 **이 파일 먼저** → `CLAUDE.md` → 관련 모듈 순으로 읽고 이어서 작업한다.

## 현재 위치 (세션 로테이션 인계점, 2026-07-28)

- 프로젝트: `C:\Projects\artist-intelligence`.
- **바닥 전제(D-006)**: **책임소재 불변식**(판단=책임질 인간·도구=증거에서 종료) + **기준 원장**(엔지니어=형식/도메인 소유자=값). 정본 `DOMAIN.md §0`·`AGENTS.md §2.1·§5`. **모든 신규 모듈 구속.**
- **모듈 5종**(핵심 흐름 `모듈 CLI → 스키마 유효 report.json → 대시보드` 전체 관통):
  1. **chart-history v5** — 차트 **5렌즈**(Kworb Spotify 50 + Apple RSS 49 + Kworb YouTube 49 + **Kworb Shazam 42**(D-020 발견 신호) + 멜론 세션-보조) · 수평 병렬 리포트 · 통합 진입 지도 · 렌즈 온셋 · `_resolve_date` 날짜 폴백 · **`tracks` 명령**(트랙 목록을 데이터로 전달, D-007).
  2. **fandom-pulse v3.1** — IG 해시태그 화력·참여·모멘텀·사운드 + 이중 귀속 + `tag_aliases` 은어 태그(51태그).
  3. **signal-bridge v2** — 3소스 조인·분류 + **원인분석 레이어**(D-021: `posts`·`social_days`·`censored` 전 표면 부착, 표본×검열 교차표, `판정 가능 선행` KPI, `--min-posts`, 튜너 `min_posts`/`exclude_censored`).
  4. **yt-pulse v1** — 워치리스트 공식 채널 velocity·신작.
  5. **sonic-profile v1** ⭐신규 — Apple 30초 프리뷰 · **오디오 무보관** · librosa 투명 DSP 7지표 · Apple 차트 100곡 코호트 + 워치리스트 · 트랙 캐시 · 분포 뷰(위치 heatmap / 추이 line / 코호트 비교).
- **공유 계약**: `snapshot-schema` · `signal-series` · `report-schema`(무변경) + PII 게이트 + `packages/entity-master`.
- 로컬: Python 3.14.5 · Node 24 · **Windows(win32/AMD64)**. `librosa`·`av`(PyAV)·`jsonschema`·`ruff`·`pyright`. Docker Desktop/WSL2 있음(Essentia 컨테이너 경로 열려 있음).

## 🔴 가동 중: 전향 실증 자동 수집 (매일 09:00 + 2시간 간격 재시도)

- **Task Scheduler `AI-daily-collect`** → `scripts/daily_collect.ps1`. 설정 정본은 **[`scripts/register_task.ps1`](scripts/register_task.ps1)**(멱등).
- **7개 레그**: spotify · apple · youtube · shazam(무료 차트) → social(유료 $3/일) → yt → **sonic**(프리뷰, 무보관).
- **재개 가능**(D-018): `data/live/state/run_<date>.json`. 완주일 재실행 = 0.9초 no-op · 부분 실패는 실패 타겟만 · **유료 태그·프리뷰는 재결제/재다운로드 없음**.
- **관전 포인트**: `판정 가능 선행`(현재 1팀 = izna) · 렌즈 온셋 · **sonic 분포 추이**(현재 점 1개 — 축적 필요) · D-015 순환.
- **가드**: PAUSE 파일 · `experiment_end=2026-08-19` · `AI_DRYRUN=1`. 중단: `schtasks /Delete /TN "AI-daily-collect" /F`.

## ⚠ 최우선: 미커밋 (재개 첫 액션 후보)

**이 세션 산출물 전부가 워킹 트리에만 있다** — D-018~D-023 문서 · `modules/sonic-profile/`(신규 모듈 전체) · `scripts/register_task.ps1` · 브리지/차트 코드 변경. 사용자에게 두 번 물었으나 커밋 지시가 없었다. **`output/report.json`·`apps/dashboard/data/reports.json`은 스케줄러가 매일 덮어쓰므로** 커밋 범위를 정할 때 코드/문서와 분리할지 판단할 것.

## ✅ 2026-07-29 완료 — sonic-profile v2 (장르 · 악기 · 리듬)

조사 정본은 [`docs/INVESTIGATION-audio-engine.md`](docs/INVESTIGATION-audio-engine.md)(3부), 결정은 **D-024·D-025·D-026**.

- **장르·악기**(D-026): Essentia 모델을 **ONNX로 직접 구동** — TF도 Docker도 없이 Windows/py3.14 네이티브, 24MB, 곡당 0.01초. 스타일 400 + 악기 40 + 장르 87. **108곡 전건 성공**.
- **리듬**(D-025): beat_this 다운비트 → 마디 16분 킥 프로파일 → 명명 템플릿 정합. four-on-floor 37 · backbeat 23 · trap-synco 20 · tresillo 22 · dembow 6.
- **템포 수복**(D-024): 격자 양자화 발견·교체. 서로 다른 값 **18개 → 95개**.
- 게이트 그린: ruff · pyright 0 · **selftest 18/18** · 5모듈 schema valid · 대시보드 렌더.
- 신규 의존성: `torch`(CPU) · `beat-this`(MIT) · `onnxruntime`. 모델은 런타임 페치 → `data/models/`(gitignore).

### ⚠ 이 축에서 반드시 이어서 할 것

1. **사람 라벨 50~100곡** — 장르·악기 **정확도가 미측정**이다. 지금은 리포트에 `정확도 미측정`을 병기하고 단독 근거 사용을 금지하고 있다. 이걸 재야 원장이 완성된다(RULES §3.1.7).
2. **스템 분리** — **트랩·저지클럽 판별이 아직 불가**하다(하이햇 롤·하프타임 스네어). 중역 대비 1.22가 원인이며, 악기 태깅 정확도도 같이 오른다. `melband-roformer-infer`가 cp314에서 해석됨(비용·체크포인트 라이선스 미검증).
3. **다운비트 실음악 검증** — 합성 픽스처는 다운비트를 과소평가한다. 정답 채보가 있는 코퍼스(AI Hub 등) 필요. 그전까지 `beats_per_bar`는 집계 전용.
4. **상업 전환 시** — 태거 가중치가 CC BY-NC-SA라 **먼저 걷어내야 한다**(RULES §3.4). 비상업 확인은 2026-07-29 도메인 소유자.

## 참고 — 종료된 조사 (재조사 불필요)

MERT·MuQ·CLaMP 3 = 라이선스 배제 · CLAP 제로샷 태깅 = 붕괴(24/26 동일 라벨) · AST 악기 = 실패 · AudioSet에 저지클럽·뭄바톤 라벨 없음. 상세는 INVESTIGATION 1~3부.

## 이전 목표 (달성) — "더욱 넓고 깊고 획기적이게 오디오를 분석할 도구를 찾자"

sonic-profile v1은 **의도적으로 좁게** 시작했다(정의가 곧 설명인 DSP 7지표). 다음은 그 천장을 넘는 작업이다. 아래는 **이 세션에서 실측 검증한 사실**과 **미검증 후보**를 구분해 둔 것.

### 검증된 제약 (재조사 불필요)

- **Essentia**: PyPI 휠이 macOS·manylinux뿐 — **Windows 설치 불가**. 단 Docker/WSL2가 있으니 **컨테이너 경유는 열려 있다**(AcousticBrainz와 값 호환이라는 이점도 있음). 인프라 한 겹 추가의 값은 별도 판단.
- **madmom**: `numpy<1.20` 요구로 **Python ≤3.9 고착**(CPJKU 자신들의 `beat_this` 이슈 #9에서 확인). 현 환경(3.14)에선 사실상 불가.
- **Demucs**: 저장소 **아카이브됨**(마지막 커밋 2023-11-16). 현 SOTA는 **BS-RoFormer / Mel-Band RoFormer**(ByteDance, MVSEP 리더보드 상위 독점).
- **AcousticBrainz**: CC0 덤프 **756만 레코딩**이 남아 있으나 **2022년 수집 중단** → 2024~26 신인은 없다. **과거 기준선 전용**.
- **한국 저작권법에 TDM 면책 조항 없음**(개정안 계류). YouTube ToS는 다운로드 명시 금지. → 오디오 취득 경로는 프리뷰(회색) 또는 라이선스(백색)뿐.

### 유망 후보 (미검증 — 다음 세션에서 확인할 것)

| 후보 | 무엇을 여는가 | 확인할 것 |
|---|---|---|
| **beat_this** (ISMIR 2024, CPJKU) | madmom 후계 비트/다운비트 — 마디·박 단위 분석 | Python 3.14 설치 가능성 |
| **Mel-Band RoFormer** 계열 | **스템 분리** → 드럼/베이스만으로 순수 리듬 지표, 보컬 제외 저역 측정 | 추론 비용·30초 발췌에서의 이득 |
| **MERT** (`m-a-p/MERT-v1-330M`) | 음악 SSL 임베딩 → **유사도·클러스터링**(차트 곡과의 거리) | Windows/PyTorch 설치, 30초 입력 적합성 |
| **CLAP** (LAION/MS) | 자연어 제로샷 태깅("어두운 신스 팝") | 태그 신뢰도, 원장에 올릴 근거를 댈 수 있는가 |
| **allin1 / 구조 분석** | 인트로/벌스/훅 경계 | **30초로는 불가** — 전곡 라이선스 선행 필요 |
| MuQ · CLaMP 3 | 최신 음악 표현 모델 | 실재·성숙도 미확인 |

### 이 방향의 진짜 병목 (도구보다 먼저)

1. **30초 발췌 천장**. 곡 구조·전곡 다이내믹 아크·드롭 타이밍은 원리적으로 불가(SPEC §6 범위 밖). "넓고 깊게"의 상당 부분이 **전곡 오디오를 전제**한다 → **Apple/유통사 라이선스 문의가 실질적 잠금 해제**(멜론 화이트리스트 문의와 같은 경로). 도구 조사보다 이게 먼저일 수 있다.
2. **블랙박스 금지선**. 사전학습 점수(danceability·mood)는 **학습 근거를 원장에 못 올리면 채택 불가**(AGENTS §2.1·§5, D-019 근거). 임베딩(MERT/CLAP)은 *지표*가 아니라 *유사도*로 쓰면 이 선을 넘지 않는다 — **어떤 형식으로 원장에 올릴지 먼저 정할 것**.
3. **고정 코호트 부재**(D-022·D-023 한계). 코호트가 매일 바뀌어 "소리가 변한 것"과 "차트 구성이 바뀐 것"이 분리되지 않는다. 지표를 늘리기 전에 **이 설계를 먼저** 잡는 편이 낫다 — 안 그러면 새 지표도 같은 이유로 트렌드를 못 낸다.

### 그 외 대기 목록

- **멜론 복구**: 삭제 원인(D-018 ⑦)은 고쳤다. 대화형 세션에서 `/mcp` 재연결 → 4콜 → `convert-melon`이면 4번째 렌즈 복귀. 화이트리스트 회신은 여전히 대기.
- **`min_posts` 기본 20**은 내가 정한 관습값 — A&R가 결과 보기 **전에** 정할 사안(§2.1).
- **yt-pulse v2**(레이블 채널 영상 레지스트리·댓글 밀도) · **댄스 모듈 v1**(문서만 존재, sonic-profile과 온셋 추출 공유 예정) · 케이스 스터디 · Vercel 배포 · 써클차트 제휴.

## 로컬 실행 메모

```bash
# ── 전체 daily 1회 (재개 가능·멱등, 완주일이면 no-op)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\daily_collect.ps1
# 태스크 등록/갱신 · 설정 미리보기
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_task.ps1 [-WhatIf]

# ── sonic-profile
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile selftest            # 합성 신호, 네트워크 0
PYTHONPATH=modules/chart-history/src python -m chart_history tracks \
  --store data/live/chart/apple/kr --top 100 -o data/live/sonic/cohort.json
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile fetch \
  --watchlist packages/entity-master/watchlist.json --cohort data/live/sonic/cohort.json \
  -o data/live/sonic/<date>.json                                                 # 오디오 미저장
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile analyze data/live/sonic \
  --watchlist packages/entity-master/watchlist.json -o modules/sonic-profile/output/

# ── 브리지(원인분석 레이어)
PYTHONPATH=modules/signal-bridge/src python -m signal_bridge analyze \
  --social data/live/social_series.json --chart data/live/chart_series.json \
  --youtube data/live/yt_series.json --theta-rank 200 --focus-social --min-posts 20 \
  --watchlist packages/entity-master/watchlist.json -o modules/signal-bridge/output/

# ── 상태·게이트
python scripts/bridge_summary.py · Get-ChildItem data\live\state    # 날짜별 done 여부
python -m ruff check modules/ scripts/ · python -m pyright modules/<m>
node apps/dashboard/scripts/collect-reports.mjs
cd apps/dashboard && npm run dev -- --port 3100    # 3000은 다른 프로젝트가 점유 중
```
