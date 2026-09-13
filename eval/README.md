# eval — Offline Evaluation Harness

**Owner:** 김대원 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈7 · §9 · **문서 작업공간:** `docs/modules/eval/` (`initial-evaluation-plan.md` · `experiment-guide.md`)

제품 런타임이 아닌 **개발용 패키지**다. 그래서 `src/daesingo/` 안이 아니라 루트에 독립으로 둔다 — Owner가 제품 코드와 분리해 혼자 굴릴 수 있어야 하고, `search`/`readout`은 eval의 존재를 몰라야 한다(§4-모듈7 ⑥).

## 구조 (§4-모듈7 ②)

| 폴더 | 들어오는 것 | 나가는 것 | git |
| --- | --- | --- | --- |
| `datasets/` | 원본 미디어·frame sequence (A/B/C tier) | — | **원본 미디어는 커밋하지 않는다** (`.gitignore`). README와 목록 파일만 |
| `manifests/` | 정답지(GT)·manifest 버전·초기 12개 테스트 케이스 | — | 커밋 |
| `runners/` | dataset + 구현 이름표(`--impl`) | **immutable prediction** | 커밋 (코드) |
| `predictions/` | runner 출력 | scorer 입력 | 커밋 (JSON). 유료 API 결과라 다시 만들지 않는다 |
| `scorers/` | prediction + GT version + metric version | metrics | 커밋 (코드) |
| `locked_test/` | 사전 고정 실제 장시간 영상 평가셋 목록 | 최종 성능 주장 | 개봉 규칙은 미결(§10-3) |
| `results/` | scorer 출력 | 집계 JSON | **커밋** — 「Eval result: JSON + git」(§10-2). MLflow는 보조 |

**Runner / Scorer를 분리한다**(§9-2). GT나 metric 정의가 바뀌어도 prediction을 다시 만들지 않는다.

## 호출 규칙

- `eval → { search, readout, recording }`의 **public capability만** 부른다 (§6-1). 프롬프트 파일·파서를 import하지 않는다.
- `case`·`evidence`·`web`을 모른다. 최종 source 선택 규칙은 `evidence`의 unit test가 검증한다 (§9-3).
- A tier(candidate 없는 frame sequence)는 `search.verify_visual(input_ref)`를 직접 부른다 (§4-모듈7 ④). `eval_mode` 분기를 만들지 않는다.
- 비용은 **runtime(source-video-hour) / eval(clip + processed_duration_sec)**을 섞지 않는다 (§4-모듈7 ⑤).

## 첫 산출물 (`docs/management/ownership.md` §3 김대원 ⑤)

`python -m eval.run --impl <이름표>` 한 줄로 도는 상태 → 정답지 10~20건 → 항상 정답/항상 오답 가짜 구현으로 지표 검증 → 4종별 점수 + Classification 지표.

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
