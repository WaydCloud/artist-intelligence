# sonic-profile · TESTS (값 무결성 검증)

> [`RULES.md`](RULES.md) §3 원장의 각 항목은 여기서 검증된다. **네트워크 없이 도는 것**이 스모크의 조건.
> 결정 근거: [`../../docs/DECISIONS.md`](../../docs/DECISIONS.md) D-019.

## 1. 픽스처 전략 — 합성 신호 (저작물 미사용)

원본 오디오를 저장하지 않는 것이 이 모듈의 불변식이므로(RULES §1), **픽스처도 음원이 아니다.** numpy로 생성한 **합성 신호**를 쓴다 — 정답을 우리가 알고 있다는 점에서 오히려 검증에 유리하다.

| 픽스처 | 생성 | 검증하는 것 |
|---|---|---|
| `click_120bpm` | 120 BPM 간격 클릭 트레인 | tempo_bpm이 120(±허용오차), pulse_clarity 높음 |
| `click_90bpm` | 90 BPM 클릭 | **옥타브 오류 회귀 방지**(180·45로 튀지 않는가) |
| `noise_white` | 백색잡음 | pulse_clarity 낮음, tempo 신뢰도 플래그 off |
| `sine_50hz` + `sine_4khz` | 저역/고역 정현파 | low_end_ratio가 각각 ~1.0 / ~0.0, brightness 단조 증가 |
| `silence` | 무음 | **미해석 처리**(0으로 채우지 않음) |
| `too_short` | 1초 | 길이 미달 → 미해석 |

## 2. 필수 통과 항목

- **결정성**: 같은 입력 → 같은 출력. 동일 픽스처를 2회 분석해 **비트 단위로 동일**해야 한다(난수·시각 의존 금지).
- **미해석 규약**: 무음·과단축·디코드 실패가 `0`이 아니라 **결측**으로 나오는가. 결측이 집계 평균을 끌어내리지 않는가(결측 ≠ 0, §0).
- **스키마**: `sonic-profile validate output/report.json` 통과.
- **관측 0 케이스**: 입력이 비어도 크래시하지 않고 유효 report + "관측 없음" insight를 내는가.
- **한계 문구 전파**: report의 `insights`에 RULES §3.1의 "곡 간 단일 비교 금지"와 커버리지가 **실제로 들어 있는가**(문자열 존재 검사). 한계 병기는 선택이 아니라 §5 준수 요건이므로 테스트한다.
- **무보관**: `fetch` 실행 후 임시 디렉터리에 오디오 파일이 **남아 있지 않은가**. 예외 발생 경로에서도 삭제되는가(실패 주입 테스트).

## 3. `crest_factor_db` 검증 — **통과 (2026-07-28)** → 활성화

**질문**: Apple 프리뷰에 라우드니스 정규화가 걸려 있는가? 걸려 있다면 crest factor는 마스터링이 아니라 Apple의 처리 파이프라인을 측정하게 된다.

**설계**: 압축 강도가 뚜렷이 다를 것으로 예상되는 10곡(현대 EDM/K-pop/힙합 vs 클래식·재즈·1960~70년대 녹음·앰비언트)의 프리뷰 RMS·peak를 비교. 정규화가 걸려 있으면 RMS가 좁게 뭉친다. 판정 기준은 **결과를 보기 전에** 고정: 스프레드 < 2dB → 정규화 의심(비활성 유지) · ≥ 6dB → 정규화 없음(활성 가능).

**결과**: RMS 범위 **−24.50 ~ −5.05 dB (스프레드 19.46 dB, σ 6.34)** — 기준을 크게 넘겼다. 순서도 마스터링 이론과 일치한다.

| 표본 | RMS | crest |
|---|---|---|
| 현대 K-pop (CORTIS - REDRED) | −5.05 dB | 8.23 dB |
| 현대 힙합 (Kendrick Lamar) | −5.81 dB | 9.35 dB |
| 현대 EDM (David Guetta) | −7.73 dB | 11.02 dB |
| 1960s 팝 (The Beatles) | −11.64 dB | 13.97 dB |
| 1970s 록 (Pink Floyd) | −14.47 dB | 14.82 dB |
| 재즈 (Bill Evans Trio) | −17.14 dB | 16.12 dB |
| 클래식 피아노 (Debussy) | −20.10 dB | 17.52 dB |
| 클래식 관현악 (Mahler) | −24.50 dB | 14.79 dB |

**판정**: 프리뷰는 **정규화되지 않으며** 마스터링 압축을 실제로 반영한다 → 지표 활성, RULES §3 표와 D-019에 반영. 상태 문자열이 `validated-2026-07-28`로 바뀌었고 selftest가 회귀 가드로 이를 검사한다.

**이 검증의 한계**: US 스토어프론트 · n=10 · 단일 시점. Apple이 정책을 바꾸면 무효가 되므로 **재검증 가능하도록 스크립트 설계를 위 문단에 남긴다.**

## 3.1 검증 로그 (2026-07-28, v1 관통)

- **selftest 10/10 PASS** (합성 신호·네트워크 0): tempo 120→117.45 · 90→89.1(옥타브 오류 회귀 없음) · 펄스 명료도 클릭 0.8826 > 잡음 0.0894 · 50Hz 저역비 1.0 / 4kHz 0.0 · 밝기 53.1 < 4051.3 · 무음·1초 입력 미해석 · 결정성 · crest 미검증 표기.
- **라이브 관통**: 워치리스트 11팀 → **8팀 해석**(izna 107.67BPM · KATSEYE 152.0 · Hearts2Hearts 129.2 · RESCENE 112.35 · CORTIS 152.0 · KEYVEATZ 129.2 · BABYMONSTER/MEOVV 117.45), 3팀 미해석(KiiiKiii·ILLIT·KISS OF LIFE — Apple m4a만 존재, PyAV 미설치).
- **별칭 검증 작동**: `KISS OF LIFE` → Sade 오매칭이 차단되어 미해석 처리됨(RULES §1).
- **무보관 검증**: `fetch` 후 임시 디렉터리에 `sonic_*` 잔존 **0건**.
- **게이트**: ruff · pyright 0 errors · `analyze` schema valid · 대시보드 5번째 탭 렌더(한계 문구 3종 출력 확인).

## 4. 태거 전처리 회귀 검증 (RULES §3.3) — **이 수치가 떨어지면 전처리가 깨진 것이다**

장르·악기 모델은 Essentia와 **동일한 mel**을 먹어야 한다. 어긋나면 예외가 아니라 **그럴듯한 오답**이 나오므로 일반 테스트로는 안 잡힌다. 그래서 **정답을 아는 신호**를 회귀 가드로 쓴다.

**가드**: Apple KR 차트 코호트에서 `Pop---K-pop`이 400개 스타일 중 **상위 5위 안에 드는 곡의 비율**.

| 전처리 | K-pop 중앙순위 | 평균 확률 | 상위5 진입 |
|---|---|---|---|
| mel `type=magnitude` (틀림) | 150위 | 0.0008 | 0/12 |
| **mel `type=power` (정답)** | **1위** | **0.4943** | **11/16** |

- **기준선 11/16**(2026-07-29, 코호트 앞 16곡). 이보다 크게 떨어지면 전처리 회귀를 의심한다.
- 판정 기준은 결과를 보기 전에 정했다: *"K-pop 차트 곡인데 K-pop 라벨이 상위에 없으면 전처리가 틀린 것"*.
- 격자 탐색으로 확인한 민감 파라미터: `power`(결정적) · 필터뱅크 `norm=slaney`(결정적) · `center`(경미) · 스펙트럼 스케일(경미).

**한계**: 이건 *전처리 동일성* 가드이지 *분류 정확도* 측정이 아니다. 정확도는 사람 라벨 50~100곡으로 별도 측정해야 하며(RULES §3.1.7), 그전까지 리포트는 `정확도 미측정`을 병기한다.

## 5. 리듬 패턴 검증 (RULES §3.1.5)

selftest가 **모델 없이**(네트워크 0) 순수 함수를 검증한다.

| 검증 | 방법 | 기대 |
|---|---|---|
| 템포 적합이 양자화를 씻는가 | 0.02초 격자에 붙인 128·143BPM 비트 시각 | 적합 오차 < 0.2%, `median(diff)`보다 정확 (실측: 128.00 vs 130.43) |
| 마디 프로파일 정규화 | 합성 정박 킥 | 합 = 1 |
| 패턴 정합 | 합성 정박 킥 | `four-on-floor`가 최고 정합 |
| 결정성 | 같은 프로파일 2회 | 동일 |
| 미해석 규약 | 비트 < 4 · 다운비트 < 3 | `RhythmUnavailable`(0으로 채우지 않음) |

> **픽스처 함정(실측)**: 임펄스 프레임을 `int()`로 잘라 넣으면 0.5초가 0.4993초가 되어 칸 경계에서 **앞 칸으로 밀린다**(4번 → 3번). 그 상태에서는 정박 킥이 `dembow`로 잡힌다. 격자 정렬 픽스처는 반드시 **반올림**한다.

**아직 검증하지 못한 것**: 실음악에서의 **다운비트 정확도**. 합성 클릭에는 화성·베이스 단서가 없어 픽스처가 다운비트를 과소평가한다(합성 F 0.34~0.68). 정답 채보가 붙은 코퍼스(AI Hub 등)가 생기기 전까지 `beats_per_bar`는 **집계에만** 쓴다.

## 6. 재현 레시피

```bash
# 스모크(네트워크 0) — 합성 픽스처로 전 구간 관통
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile analyze \
  modules/sonic-profile/tests/fixtures/synthetic -o modules/sonic-profile/output/
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile validate \
  modules/sonic-profile/output/report.json

# 라이브 1회(워치리스트 대상, 오디오 무보관)
PYTHONPATH=modules/sonic-profile/src python -m sonic_profile fetch \
  --watchlist packages/entity-master/watchlist.json -o data/live/sonic/<date>.json

# 게이트
python -m ruff check modules/sonic-profile
python -m pyright modules/sonic-profile
```
