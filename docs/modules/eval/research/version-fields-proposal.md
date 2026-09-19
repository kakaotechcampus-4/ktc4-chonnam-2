# 예측·결과 파일 version field 제안(11-5 ④번 답안) — 원문과 구현 대조

> **이 문서가 하는 일.** 「결과 파일에 무엇을 박아야 두 실행을 비교할 수 있는가」에 대한 답안 **원문을 보존**하고, 실제 하니스가 쓰는 envelope과 §3에서 대조한다.
> **결정 문서가 아니다.** 현행 envelope의 authoritative source는 `eval/run.py`와 `eval/predictions/`·`eval/results/`의 실제 파일이다.
> **Owner:** 김대원(`eval`) · 대조 갱신 2026-09-12
> **배경:** `architecture-input-memo.md` §3-2(6) 「결과 파일의 필수 필드가 v3 규정보다 늘어난다」의 후속 답안이다.

---

## 1. 원문 — 스펙이 이미 못 박은 3개 (협상 불가)

v1.1 §12 규칙 4·5 + §3-7:

> **규칙 4** — 구현은 이름표(문자열)로 지정. `gemini-coarse@c7`
> **규칙 5** — 버전이 다르면 채점기가 비교를 **거부**한다
> **§3-7** — `results/`는 「impl 이름표 + `contract_version` 포함」이 소유 조건

여기에 §인터페이스2가 한 줄 더 얹는다 — *「Coarse/Fine이 내부에서 몇 후보를 유지할지는 `search` 구현 설정(impl/config 버전에 귀속)」*. 즉 **`impl` 이름표 하나가 프롬프트 + config를 통째로 대표해야 한다.** `@c7`이 프롬프트만 뜻하면 안 되고, config가 바뀌면 이름표도 바뀌어야 한다.

## 2. 원문 — 최소 8개

**예측 파일(`predictions/`) — 비싸다. 한 번 만들면 안 고친다.**

| 필드 | 근거 |
| --- | --- |
| `impl` | §12 규칙 4. 프롬프트 + config 통합 대표 |
| `contract_version` | §12 규칙 2, §3-7 |
| `runner_commit` | 예측을 만든 코드 (git hash) |
| `manifest_version` | §12 `manifest/`(버전 있음) |
| `processed_duration_sec` | §3 「환산 병기」의 유일한 근거값 |

**결과 파일(`results/`) — 싸다. 몇 번이든 다시 만든다.**

| 필드 | 근거 |
| --- | --- |
| `gt_version` | 정답지 몇 번째 판 |
| `scorer_version` | 지표 정의 몇 번째 판. **Recall@K의 K도 여기 귀속**(§인터페이스2) |
| `prediction_ref` | 어떤 예측을 채점했나. 경로 + sha256 |

---

## 3. 구현 대조 (2026-09-12)

현행 envelope(`eval/predictions/mock_e2e.json` · `eval/results/mock_e2e.mp0.json` 기준):

```jsonc
// predictions/*.json  meta
{ "run_id", "impl", "impl_version", "stage", "manifest", "manifest_version",
  "clip_rule_version", "normalizer_version", "code_commit", "created_at" }

// results/*.json  meta
{ "run_id", "impl", "stage", "manifest", "gt_version", "normalizer_version", "code_commit" }
```

| 제안 필드 | 현행 | 상태 |
| --- | --- | --- |
| `impl` | `impl` (+ `impl_version` 추가) | **반영** |
| `manifest_version` | `manifest_version` (+ `clip_rule_version` 추가) | **반영** |
| `runner_commit` | `code_commit` | **반영(개명)** |
| `gt_version` | `gt_version` (results) | **반영** |
| `contract_version` | 없음 | **누락** |
| `processed_duration_sec` | 없음 | **누락** |
| `scorer_version` | 없음 (`normalizer_version`만 있다) | **누락** |
| `prediction_ref` (경로 + sha256) | 없음 (`run_id`로만 간접 연결) | **누락** |

### 3-1. 누락 4건이 각각 무엇을 막는가

- **`contract_version`** — §3-7이 `results/`의 소유 조건으로 못 박은 값이다. 지금은 `analysis-run-candidate-event/v1.1`처럼 계약 판번호가 결과에 안 남아, **계약이 바뀐 전후의 결과를 구분할 수 없다.** 규칙 5(「버전이 다르면 비교를 거부한다」)를 코드로 강제할 근거 자체가 없는 상태다.
- **`processed_duration_sec`** — 시간당 환산치를 병기할 근거값이다. 없으면 `cost_per_source_video_hour`를 결과 파일만으로 재현할 수 없다. 계약 쪽에는 이미 있다(`AnalysisRun.usage_summary.processed_duration_ms` · `UsageRecord.processed_duration_sec`) — **envelope으로 끌어오지 않았을 뿐이다.**
- **`scorer_version`** — 지표 정의 판번호. 현재는 `normalizer_version`(정규화 층)만 있고 채점 정의 판번호가 없다. **2026-09-10에 coarse localization 규칙이 IoU에서 point error로 바뀌었는데, 그 전후 결과가 파일상 구분되지 않는다.** 누락 4건 중 실제로 가장 먼저 물릴 항목이다.
- **`prediction_ref`** — 어떤 예측을 채점했는지 경로 + sha256으로 묶는 값. 지금은 `run_id` 문자열이 같다는 것만으로 연결돼, 예측 파일을 덮어써도 결과가 그 사실을 모른다. 예측 불변성(§2 「한 번 만들면 안 고친다」)을 파일 자체가 증명하지 못한다.

### 3-2. 원문에 없었지만 추가된 것

- `impl_version` — impl 이름표와 별개로 impl 구현 판번호를 기록한다. 원문의 「`impl` 하나가 프롬프트 + config를 통째로 대표해야 한다」와 방향이 같다.
- `clip_rule_version` — 클립 분할 규칙 판번호(`c1`). B tier 분할 규칙이 바뀌면 같은 원본에서 다른 클립이 나오므로 필요하다.
- `created_at`, `stage`, `manifest`, `run_id`.

### 3-3. 아직 자리조차 없는 것

`architecture-input-memo.md` §3-2(6)이 함께 요구한 **`polarity_rule`**(분류 정답 판정 기준)과 **source(aihub/youtube) 구분**은 envelope에 없다. `polarity_rule`은 A tier 정답지가 폴더 기준 단일 `label`만 싣기로 해 아직 판정 분기 자체가 없기 때문이고(`ground-truth-schema.md` §2-3), source는 `manifest` 이름(`a_aihub`/`b_youtube`/`mock_pack`)으로 간접 식별된다.

---

## 4. 후속 (제 브랜치 작업)

1. `contract_version` · `processed_duration_sec`를 예측 envelope에, `scorer_version` · `prediction_ref`(경로 + sha256)를 결과 envelope에 추가한다.
2. `scorer_version`을 올리는 첫 계기는 이미 있다 — coarse localization의 IoU → point error 전환(2026-09-10).
3. 규칙 5(버전 다르면 비교 거부)를 `contract_version` 기준으로 코드에서 강제한다.

## 5. 관련 문서

- `architecture-input-memo.md` §3-2(6)·§10 — 이 제안의 출처와 현행 대조
- `ground-truth-schema.md` — `gt_version`이 가리키는 정답지 스키마
- `docs/architecture/module-architecture.md` §9 — 채점 구조와 비교 거부 규칙
- `eval/run.py` · `eval/predictions/` · `eval/results/` — 현행 envelope
