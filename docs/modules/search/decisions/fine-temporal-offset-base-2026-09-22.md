# Fine `at_offset_ms`의 기준 — 잘라낸 clip의 0초 확정 (이슈 #132 회신)

> 결정일 2026-09-22 · 근거 [이슈 #132](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/132)(유소연, 월요일 Real E2E 실패 보고)
> **Producer/Owner:** 서어진(`search`) · **범위:** search 내부 구현과 프롬프트. 계약 문서 본문은 여기서 고치지 않는다 — §5 참조

## 1. 보고된 것

대표 영상 `20260620_141956_EVT_1.avi`에서 `verify_visual_with_stream_context()`가 2회 연속
`ProviderPayloadError("Fine temporal offset outside candidate window")`로 죽었다. coarse는
성공했고 fine API 호출도 성공했으며, 응답 검증에서만 실패했다.

## 2. 원인 — 하나의 뿌리에서 나온 결함 3개

Fine은 candidate span에 앞뒤 `fine_padding_sec`(기본 4초)을 붙여 잘라낸 clip을 모델에게
준다. padding 도입 시점에 **"Fine input의 시작"과 "candidate span의 시작"이 갈라졌는데**,
검증 코드는 둘이 같던 시절의 가정을 그대로 들고 있었다.

| | 결함 | 증상 |
| --- | --- | --- |
| C1 | 검증 범위가 padding 없는 span | 여유분 구간에서 정확히 짚으면 항상 거절 — **보고된 실패** |
| C2 | `span.representative_ms`와 ms 단위 완전 일치 요구 | C1을 고치면 바로 다음 줄에서 실패. 실호출에서는 성립 불가 |
| C3 | 방출값이 원본 절대 시각 | 계약 §7("Fine input 시작점 기준 상대 시간")과 불일치 |
| C4 | 프롬프트가 offset 기준을 말하지 않음 | 모델이 절대초로 답하면 `outside prepared clip`으로 거절 |

C2가 왜 지금까지 안 보였나: mock fixture는 `representative_ms`를 `span.start_ms +
at_offset_ms`로 **만들어 넣었다**(`scenario_happy_001`: 300000+12480=312480). 파생식이
성립하도록 데이터를 구성했으므로 통과했고, 실제 두 모델의 응답을 비교하는 경로는
Real E2E가 처음이었다. C1이 먼저 raise해서 아직 드러나지 않았을 뿐이다.

## 3. 결정

**`at_offset_ms`의 기준은 Fine input, 즉 잘라낸 clip의 0초다.** 계약
`contract-visual-evidence.md` §7과 `adr-visual-evidence.md`의 문자 그대로다. 모델이 답한
값을 rebase 없이 그대로 싣는다.

검증은 두 가지만 남긴다.

- `0 <= at_offset_ms <= clip_duration_ms` — 모델은 자기가 본 clip 안을 답해야 한다.
  padding 구간이 곧 유효 범위가 된다.
- `origin_start_ms + at_offset_ms <= source_duration_ms` — 방출하지 않는 내부 sanity.
  준비 단계(ffmpeg/probe)가 원본 밖 clip을 만든 경우를 잡는다.

지운 것:

- **candidate span 범위 검사.** padding은 경계에서 시작하는 사건을 보라고 붙인 것이다.
  거기서 짚은 답을 거절하면 padding을 준 이유가 사라진다. clip 범위 검사가 이미 상한이다.
- **representative 일치 검사.** `representative_ms`는 coarse가 본 대략적 시점이고
  `at_offset_ms`는 fine이 본 시점이다. 서로 다른 호출의 서로 다른 관찰이 ms까지 같기를
  요구하는 것은 파생식을 검증 조건으로 오용한 것이다.

프롬프트는 `fine-p2` → `fine-p3`으로 올려 기준을 못박았다(C4). 지시 의미가 달라진
프롬프트를 같은 version으로 두면 eval이 version으로 묶는 비교가 섞인다.

## 4. 이슈 질문에 대한 답

- **검증 범위를 padded 구간으로 바꿔야 하나?** 그렇다. 그게 모델이 실제로 본 것이다.
- **coarse의 span 계산을 넓혀야 하나?** 아니다. span은 coarse 후보 창이라는 의미가 이미
  확정돼 있고(`candidate-span-semantics-2026-09-10.md`), 검증 편의를 위해 창을 넓히면
  그 의미가 흐려진다. padding은 fine의 입력 사정이지 후보 창의 폭이 아니다.
- **의도된 동작(부정확을 드러내려는 것)인가?** 아니다. 이 검사는 fine의 정확도를 재지
  않는다. padding 안에서 정확히 짚을수록 더 잘 거절한다.
- **다른 영상에서도 재현되나?** 구조적 결함이므로 입력과 무관하게 재현된다 — fine이
  padding 구간의 시각을 답하면(C1), 또는 coarse와 다른 시각을 답하면(C2) 항상 실패한다.

## 5. 미결 — 여기서 채우지 않는다

1. **fine이 짚은 정밀 시각을 원본 시각으로 복원할 수단이 없다.** clip 상대 기준을 택한
   결과이고, clip의 시작점을 실을 필드가 `VisualEvidence`에 없다. `at_offset_ms`는 사실상
   진단값이며 신고 `occurred_at`의 정밀도는 계속 coarse의 `representative_ms`에 묶인다.
2. **`representative_ms`를 fine이 정밀화할 것인가.** 1번의 실질적 해법 후보지만
   `CandidateEvent`는 coarse(`CANDIDATE_SEARCH`)의 산출물이고, 이를 search가 덮어쓸지는
   계약 변경이라 단독으로 정하지 않는다.
3. **`contract-analysis-run-candidate-event.md` §4-1의 `representative_ms = span.start_ms
   + fine.at_offset_ms`.** 이 식은 **padding이 0일 때만** 성립한다. 문장이 있는 문서는
   case·eval이 쓰는 매칭 규칙이므로 이슈 #132로 통보하고 수정 주체는 그쪽에 맡긴다.
4. **`fine_padding_sec = 4.0`의 근거.** 실험 요약(`experiments/coarse-fine-probe-summary-2026-09-12.md`)과
   baseline 권고는 2.0인데 코드 기본값은 4.0이고, 값을 바꿨다고 적은 결정 문서가 없다.
   이번 변경으로 padding 폭이 곧 유효 검증 범위가 되므로 값의 의미가 커졌다 — 값 자체는
   비용·품질 실험 사안이라 여기서 정하지 않는다.

## 6. 확인

`tests/search` 320건, 저장소 전체 1029건 PASS(13 skip은 `DAESINGO_RECORDING_VIDEO`
미설정). `scripts/check_boundaries.py`·`scripts/check_contract_fixtures.py` PASS.
Real E2E 재실행으로 실제 통과를 확인하는 것은 별도다 — 이 문서는 코드 수준까지만 말한다.
