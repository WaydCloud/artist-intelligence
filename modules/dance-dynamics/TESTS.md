# dance-dynamics · TESTS (수용조건 · 완료조건)

> 이 조건들이 통과해야 "완료"다. CI 스모크가 이 중 핵심을 자동 검증한다([`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml)).

## 픽스처

- `tests/fixtures/sample.mp4` — 안무 포인트가 분명한 **짧은(≤30초)** 클립.
- `tests/fixtures/sample.wav` — 위 영상의 음악 (음악 의존 지표 테스트용).
- `tests/fixtures/sample_far.mp4` — 같은 안무를 **카메라 거리만 다르게** 찍은 클립 (정규화 검증용).

## 스모크 (핵심 흐름)

```bash
python -m dance_dynamics analyze tests/fixtures/sample.mp4 -o output/
# → output/report.json 이 생성되고 report-schema 를 통과해야 한다.
```

## 수용조건

- [ ] **A. 핵심 흐름**: 유효 영상 입력 → `output/report.json` 생성 + 스키마 유효.
- [ ] **B. 값 범위 불변식** (RULES §3):
  - 다이내믹 레인지 ∈ `[0, 1]`
  - 액센트–온셋 정합도 ∈ `[0, 100]`
  - 음악–움직임 상관 ∈ `[−1, 1]`
- [ ] **C. 필수 지표 존재**: `metrics`에 다이내믹 레인지·정합도·상관 포함 (음악 없으면 D 적용).
- [ ] **D. 음악 없음 graceful**: `sample.mp4`만(음악 없이) 입력 → 음악 의존 지표 생략 + `insights`에 "음악 트랙 없음" 명시. 크래시 금지.
- [ ] **E. 정규화 검증**: `sample.mp4` vs `sample_far.mp4`의 **다이내믹 레인지 차이 < 0.1**. (카메라 거리에 불변)
- [ ] **F. 결정성**: 같은 입력 2회 실행 → 동일 지표(시드 고정).
- [ ] **G. 윤리**: 리포트에 "실력 총점/합격" 류 문구 없음. 2D 한계 명시 포함.

## 실패 시 → [`../../WORKFLOW.md`](../../WORKFLOW.md) 리커버리

우회 금지. 원인 격리 → 최소 수정 → 재현 픽스처 추가.
