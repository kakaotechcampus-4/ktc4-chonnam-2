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

**`c1` 시절 결과는 남기지 못했다.** 그 개정에서 예측을 다시 만들었고
(`normalizer` `n1 → n2`), 그러면 옛 결과의 `prediction_ref.sha256` 이
맞지 않는다 — 검증되지 않는 숫자를 남기는 것은 남기지 않는 것보다 나쁘다.

**`cl1` 결과 4건은 남아 있다.** `by_condition` 철회(`cl1 → cl2`)는 예측을
건드리지 않아 지문이 그대로 맞는다. 규율이 실제로 작동한 첫 사례다 —
같은 예측·같은 정답지에 채점기만 다른 결과 두 벌이 나란히 있고, 무엇이
바뀌었는지 diff 로 볼 수 있다.

| run_id | impl | manifest · stage | 현행 세대 | 남아 있는 옛 세대 |
| --- | --- | --- | --- | --- |
| `demo_correct` | `fake:always_correct` | `b_youtube` · `candidate` | `g3.s5-c3` | `g3.s4-c2` · `g3.s4-c3` |
| `demo_wrong` | `fake:always_wrong` | `b_youtube` · `candidate` | `g3.s5-c3` | `g3.s4-c2` · `g3.s4-c3` |
| `demo_correct_cls` | `fake:always_correct` | `a_aihub` · `classification` | `g1.cl3-c3` | `g1.cl1-c2` · `g1.cl2-c2` · `g1.cl2-c3` |
| `demo_wrong_cls` | `fake:always_wrong` | `a_aihub` · `classification` | `g1.cl3-c3` | `g1.cl1-c2` · `g1.cl2-c2` · `g1.cl2-c3` |
| `demo_correct_abmix` | `fake:always_correct` | `ab_mixed` · `classification` (5×5 전부 채워짐) | `ag1.cl3-c3` | `ag1.cl1-c2` · `ag1.cl2-c2` · `ag1.cl2-c3` |
| `demo_wrong_abmix` | `fake:always_wrong` | `ab_mixed` · `classification` | `ag1.cl3-c3` | `ag1.cl1-c2` · `ag1.cl2-c2` · `ag1.cl2-c3` |
| `mock_e2e` | `mock_pack:contracts` | `mock_pack` · `candidate` | `mp1.s5-c3` | `mp1.s4-c2` · `mp1.s4-c3` |
| `mock_plate` | `mock_pack:contracts` | `mock_pack` · `plate` | `mp1.p2-c3` | `mp1.p2-c2` |

**옛 세대를 지우지 않는다.** 채점기가 바뀌면 이름이 달라져 나란히 남는다 —
같은 예측·같은 정답지에 채점기만 다른 결과를 diff 로 비교할 수 있다.

`demo_*` 는 치트 구현 두 개(`fake:always_correct`/`fake:always_wrong`)의 대조로 지표 계산 자체가 오류를 잡는지 확인한다. `mock_*` 는 팀 Mock Pack 이 파이프라인을 끝까지 통과하는지 확인하는 배관 테스트다 — 정답지가 채점 대상 fixture 에서 파생돼 순환적이므로(`coverage` 참조) 숫자를 성능으로 읽지 않는다.
