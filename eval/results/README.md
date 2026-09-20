# eval/results

scorer 집계 결과 JSON. **git으로 추적**한다. 실험 기록 방법은 `docs/modules/eval/experiment-guide.md`.

## 파일명

```
{run_id}.{gt_version}.{scorer_version}-{cost_scorer_version}.json
```

**숫자를 만든 버전을 전부 이름에 싣는다.** 이름이 `{run_id}.{gt_version}.json`
이던 동안 `s2 → s3` 개정에서 s2 결과가 통째로 사라졌다 — 정답지가 같으면
파일명이 같았기 때문이다. 정답지가 같아도 채점기가 다르면 다른 숫자이고,
다른 숫자는 다른 파일이어야 비교할 수 있다.

`eval.score` 는 **같은 이름이 이미 있으면 쓰지 않고 rc 3 으로 멈춘다**
(예측과 같은 규율). 채점 프로세스가 바뀌면 이름이 달라져 나란히 남고,
안 바뀌었는데 이름이 같다면 같은 숫자를 다시 쓰는 것이라 덮어쓸 이유가 없다.

`-c1` 이 붙은 파일은 속도 집계가 들어오기 전(`cost` `c1`) 결과다. 지우지
않는다 — 그때의 숫자가 그때의 채점기로 나온 기록이다.

| 파일 | impl | manifest · stage |
| --- | --- | --- |
| `demo_correct.g3.s3-c1.json` | `fake:always_correct` | `b_youtube` · `candidate` |
| `demo_correct_cls.g1.cl1-c1.json` | `fake:always_correct` | `a_aihub` · `classification` |
| `demo_wrong.g3.s3-c1.json` | `fake:always_wrong` | `b_youtube` · `candidate` |
| `demo_wrong_cls.g1.cl1-c1.json` | `fake:always_wrong` | `a_aihub` · `classification` |
| `demo_correct_abmix.ag1.cl1-c1.json` | `fake:always_correct` | `ab_mixed` · `classification` (5×5 전부 채워짐) |
| `demo_wrong_abmix.ag1.cl1-c1.json` | `fake:always_wrong` | `ab_mixed` · `classification` |
| `mock_e2e.mp1.s3-c1.json` | `mock_pack:contracts` | `mock_pack` · `candidate` |
| `mock_plate.mp1.p1-c1.json` | `mock_pack:contracts` | `mock_pack` · `plate` |

`demo_*` 는 치트 구현 두 개(`fake:always_correct`/`fake:always_wrong`)의 대조로 지표 계산 자체가 오류를 잡는지 확인한다. `mock_*` 는 팀 Mock Pack 이 파이프라인을 끝까지 통과하는지 확인하는 배관 테스트다 — 정답지가 채점 대상 fixture 에서 파생돼 순환적이므로(`coverage` 참조) 숫자를 성능으로 읽지 않는다.
