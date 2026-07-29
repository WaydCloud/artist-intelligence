# genre-impulse · RULES (기준 원장)

> 미시 판단의 기준은 임의가 아니다 — `정의 · 도메인 근거 · 하중여부 · 테스트 · 한계` ([`../../AGENTS.md`](../../AGENTS.md) §2.1).
> 임계값은 도메인 소유자(A&R) 소유이며 CLI로 노출한다. 코드에 은닉 금지.

## §1. 불변식

- **무단정**: 출력 어디에도 "뜬다/차트인한다/도입하라" 단정을 넣지 않는다. 형식은 항상 *"임펄스 X의 검출 규칙에 매치 — 참고: 과거 사례 리드타임·모드·한계"*.
- **커버리지 정직**: 검출 규칙이 없는 임펄스는 숨기지 않고 사유와 함께 표면화한다(축 공백·스템 잠금·미실측). 규칙 n/원장 전체를 KPI로 상시 노출.
- **원장 인용 규율**: 임펄스 레코드 인용 시 확실성 6등급(D-033 보완⑥)을 병기하고, **중간 미만 등급의 사실은 리포트 표면에 올리지 않는다**(원장에는 남는다).
- **결정성**: 같은 입력 → 같은 산출(`generatedAt` 제외). 백분위는 당일 코호트 내 순위로 계산(외부 상태 없음).

## §2. 검출 규칙 원장

검출 규칙 = 임펄스의 사운드 서명을 sonic-profile 축의 **코호트 내 백분위 조합**으로 표현한 것. 규칙은 **사전 등록 → 정답지 실측 검증 → 원장 등재**의 순서로만 추가된다(결과 보고 규칙을 만들지 않는다).

### §2.1 `hyperpop-texture` (v1 유일 규칙)

- **정의**: 당일 차트 코호트에서 `organic_ratio` 백분위 ≤ **P_low** 이고, (`spectral_flatness` ≥ **P_high** 또는 `over_unity_ratio` ≥ **P_high**)인 트랙.
- **도메인 근거**: A2.1 실측(2026-07-30, CASEBOOK §A2.1) — 정답지 Savage(organic P2.2·flatness P87.9·over_unity P80.2)·Whiplash(organic P17.6·over_unity P100·attack P96.7)가 이 조합에서 코호트 극단에 위치. '쇠맛' 계보에서 가장 일관된 축은 organic_ratio↓(5곡 중 3곡 하위 20%). 사전 등록 축 중 brightness는 판별력 없음이 실측돼 **규칙에서 제외**했다.
- **하중여부**: **하중받는 기준** — 매치 여부가 A&R의 후속 검토(요소 차용 후보 청취)를 바꾼다.
- **임계값** (관습값, 도메인 소유자 재조정):
  | 이름 | 기본값 | CLI |
  |---|---|---|
  | P_low (하위 백분위) | 20 | `--low-pct` |
  | P_high (상위 백분위) | 80 | `--high-pct` |
- **테스트**: TESTS §3 (정답지 트랙을 코호트에 섞으면 매치, 임계를 극단으로 올리면 매치 0).
- **한계**: ① 비교 모집단이 당일 코호트라 **코호트 구성에 상대적** — 코호트 전체가 하이퍼팝화되면 규칙이 둔감해진다(분포 중앙값 추이를 함께 보라) ② 30초 프리뷰 발췌 ③ 정답지 표본 5곡(계보)·검증 1케이스 — 새 사례가 반증하면 규칙 버전을 올린다 ④ 보컬 처리 축 부재로 하이퍼팝 시그니처의 절반(피치 시프트 보컬)은 못 본다 — **축 정의는 완료**(sonic-profile RULES §3.8.4 `vocal_tuning_hardness`·`vocal_pitch_shift_proxy`), 구현·채택 게이트(TESTS §7.2.2) 대기.

### §2.2 규칙 미확정 임펄스 (v1 기준 9건)

| 임펄스 | 사유 | 해제 조건 |
|---|---|---|
| drill | A2.1 실측: 사전 등록 5축 전부 중앙 — 리듬 축 공백 | 슬라이딩 808 축(**정의 완료**: sonic-profile RULES §3.8.3 `bass_glide_ratio`) 구현 + TESTS §7.2.2 채택 게이트 통과 |
| jersey-club | 킥 5연타는 rhythm_match 후보이나 하프타임 스네어·하이햇 롤 잠금 | 하프타임 스네어 축(**정의 완료**: sonic-profile RULES §3.8.2 `halftime_snare_ratio`) 구현 + 게이트 통과. ⚠ **하이햇 롤은 이걸로 안 열린다** — 16칸 격자 해상도 문제라 스템과 무관(별개 변경) |
| ukg-dnb / moombahton-tropical / reggaeton-dembow / citypop / njs / easy-listening / amapiano | 원형↔한국 서명 비교(A2 본편) 미완 — 규칙 후보 미도출 | A2 본편 분석 후 사전 등록·검증 |

## §3. 데이터 계약

- **임펄스 원장**: `data/research/genre-impulse/impulse.schema.json` 준수 레코드만 로드. 위반 레코드는 스킵하고 insights에 보고(조용한 무시 금지).
- **sonic 스냅샷**: sonic-profile `fetch` 산출(`records[].features`). `organic_ratio`는 스냅샷에 없고 저장 라벨에서 재계산된다(derived) — 재구현하지 않고 sonic-profile의 `derived.derive_all`을 **import해 재사용**한다(AGENTS §1 중복 방지). ⚠ 이는 D-007(모듈 간 코드 import 금지, 데이터 계약만)의 **문서화된 한시 예외**다: 공유 프리미티브는 "먼저 만든 쪽이 packages/에 두고 다른 쪽이 참조"가 정본 경로(sonic-profile SPEC §5.1)이며, 파생 계산의 `packages/` 승격은 구조 변경이라 별도 승인 후 이 예외를 해소한다. 실행 시 `PYTHONPATH`에 두 모듈 src가 필요함을 CLI 도움말에 명시.
- **report.json**: 공유 report-schema 무변경 준수.

## §4. 차트 데이터 규약

- 매치 트랙 bar: `label = "아티스트 - 곡명"`, value = 규칙 주축(organic_ratio) 백분위. 워치리스트 트랙은 라벨에 `★` 접두.
- 커버리지 표는 bar가 아니라 insights 라인 규약으로 렌더(신규 차트 타입 추가 금지 — 스키마 무변경 원칙).
- tunable 뷰: `view=impulse-rules`, 슬라이더 2개(P_low·P_high) — 재계산은 저장된 백분위에서 파생(오디오 재접근 없음).
