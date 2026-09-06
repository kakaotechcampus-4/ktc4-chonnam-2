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

## 지금 도는 것 (v1 harness)

설계 원문은 `docs/modules/eval/harness-v1-design.md`다. 여기에는 쓰는 법만 적는다.

```bash
# 1) 실행 → predictions/<run_id>.json  (immutable · 덮어쓰지 않는다)
python -m eval.run --impl fake:always_correct --manifest b_youtube --stage candidate --run-id demo_correct

# 2) 채점 → results/<run_id>.<gt_version>.json
python -m eval.score --prediction demo_correct
```

`--stage` 는 `candidate`(B tier · `b_youtube`) 와 `classification`(A tier · `a_aihub`) 두 가지다. `--impl` 이름표는 `runners/registry.py` 가 소유한다.

| 폴더 | 무엇이 들어 있나 |
| --- | --- |
| `predictions/` | impl 이 낸 **원문(`raw`) + 정규화 뷰(`normalized`) + `meta`**. GT나 지표 정의가 바뀌어도 다시 만들지 않는다 — scorer 만 다시 돈다 |
| `results/` | 지표 값. 낼 수 없는 지표는 `0` 이 아니라 `null` 이고, `coverage` 가 그 이유와 채점에서 제외한 것을 적는다 |

**지표 계산이 맞는지는 치트 구현 두 개의 점수 차이로 확인한다.** `fake:always_correct` 는 GT 를 그대로 되돌려주고 `fake:always_wrong` 은 유형·구간·bbox 를 전부 틀리게 낸다. 커밋된 `demo_correct*` / `demo_wrong*` 산출물이 그 대조다 — 만점과 0점이 함께 있지 않으면 그 지표는 검증되지 않은 것이다. runner 는 impl 에 `{"manifest", "stage"}` 만 넘긴다(§2-5). GT 는 치트 구현이 스스로 읽는다.

```bash
python -m pytest tests/eval/ -q
```

미디어가 없는 clone 에서도 전부 통과한다. B tier 클립 55개와 A tier 아카이브(`VL.zip`)가 필요한 테스트는 **실패가 아니라 skip** 이며, 무엇이 왜 건너뛰는지는 `datasets/README.md` 가 적어 둔다.
