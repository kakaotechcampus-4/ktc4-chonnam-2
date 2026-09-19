# eval/results

scorer 집계 결과 JSON. **git으로 추적**한다. 실험 기록 방법은 `docs/modules/eval/experiment-guide.md`.

| 파일 | impl | manifest · stage |
| --- | --- | --- |
| `demo_correct.g3.json` | `fake:always_correct` | `b_youtube` · `candidate` |
| `demo_correct_cls.g1.json` | `fake:always_correct` | `a_aihub` · `classification` |
| `demo_wrong.g3.json` | `fake:always_wrong` | `b_youtube` · `candidate` |
| `demo_wrong_cls.g1.json` | `fake:always_wrong` | `a_aihub` · `classification` |
| `demo_correct_abmix.ag1.json` | `fake:always_correct` | `ab_mixed` · `classification` (5×5 전부 채워짐) |
| `demo_wrong_abmix.ag1.json` | `fake:always_wrong` | `ab_mixed` · `classification` |
| `mock_e2e.mp1.json` | `mock_pack:contracts` | `mock_pack` · `candidate` |
| `mock_plate.mp1.json` | `mock_pack:contracts` | `mock_pack` · `plate` |

`demo_*` 는 치트 구현 두 개(`fake:always_correct`/`fake:always_wrong`)의 대조로 지표 계산 자체가 오류를 잡는지 확인한다. `mock_*` 는 팀 Mock Pack 이 파이프라인을 끝까지 통과하는지 확인하는 배관 테스트다 — 정답지가 채점 대상 fixture 에서 파생돼 순환적이므로(`coverage` 참조) 숫자를 성능으로 읽지 않는다.
