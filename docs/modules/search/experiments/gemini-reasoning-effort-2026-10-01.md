# 추론 강도(reasoning_effort) low · medium · high: Coarse→Fine 7클립

실행일: 2026-10-01. 회차별 후보 구간(원본 초)·Fine 판정·토큰·provider 지연, 원인 분석 실행의 Fine 판정 요약(대상 연결·primitive 상태·시각)은 [구조화 결과](./gemini-reasoning-effort-2026-10-01-results.json)에 기록했다. 관찰 문장 원문과 영상·API 키는 저장소에 두지 않았다. 실행 스크립트: `scripts/gemini_coarse_fine_slowdown_trace.py --transport video --conditions 0.5:0.25 --profiles p3 --reasoning medium,high --repeats 3`.

## 질문

Search의 모든 실험과 운영은 `reasoning_effort=low`였다(`config.py` 도입 이후 값이 바뀐 적이 없고, 결과 JSON 48건 모두 `low`). Coarse·Fine의 추론 강도는 [3주 설계](../../../superpowers/plans/2026-09-19-recording-job-execution-three-week-design.md) D3에서 "실험 후 결정"으로 남아 있다. **추론 강도를 올리면 운영 v3 구조에서 위반 검출이 늘어나는가.**

## 방법

- 구조는 [최종 구조 제안](../decisions/search-final-structure-2026-10-01.md)과 같다. Coarse는 360p·원본 2 fps를 0.5x로 늘린 영상이고, Fine은 후보 ± 4초를 원본 4 fps에서 0.25x로 늘린 영상이다. 프롬프트는 p3에 배속 안내를 붙였고 재시도는 0이다. 준비는 운영 `MediaPreparer`가 한다.
- medium·high를 7클립 × 3회 돌렸다. low는 같은 날 [운영 경로 검증](./search-v3-production-verify-2026-10-01.md)의 3회를 재인용한다. 판정 기준도 같다. 위반 클립은 정답 구간과 겹친 후보의 Fine이 `OBSERVED`면 HIT로 센다.
- **호출 방식 차이:** medium·high는 실험 invoker(`SlowVideoInvoker`)가 스트리밍으로 호출했다(아래 프록시 제약). low는 운영 `GeminiProvider`의 non-streaming 호출이다. 같은 실행 안에 low 대조를 다시 돌리지는 않았다.
- **원인 분석 실행:** 놓친 이유를 보려고 Fine 응답 전체를 저장하게 고쳐 위반 4클립을 low로 1회 더 돌렸다(스트리밍). 이 회차는 low 검출률에 포함한다.
- 정답 구간: `141927` 4–10초, `YT_0003` 10–13초, `YT_0002` 11–14초. `youtube_clip_01`은 2026-10-01 사용자 수정으로 **0–2초**다(이전 2–5초). 0–2초로 다시 채점해도 10회 모두 판정이 같다.

## 프록시 제약: non-streaming 출력 상한 2,000토큰

- medium·high를 non-streaming으로 부르면 Fine이 `completion_tokens=1986`에서 잘려 `LengthFinishReasonError`가 났다(`141927` 4–10초 Fine, 4호출 모두).
- `max_tokens=16384`를 주면 400 `exceeds the 2000-token ceiling this proxy holds a NON-STREAMING reply to ... Send stream=true`가 돌아온다.
- 스트리밍(`max_tokens=16384`)이면 끝까지 답한다. 같은 Fine 호출에서 medium은 출력 3,011토큰(그중 reasoning 2,041)·19.4초, high는 출력 6,460토큰(reasoning 5,488)·31.3초였다.
- 프록시는 `reasoning_tokens` 개수만 돌려주고 사고 내용은 주지 않는다.
- 운영 `provider.py`는 non-streaming이므로, 지금 설정만 medium·high로 바꾸면 긴 응답이 실패한다.

## 결과

| 추론 | 위반 검출 | 확률 | 위반 없음 정답 | 회차 평균 토큰 | Fine provider 지연 p50 | 7클립 wall |
| --- | --- | --- | --- | --- | --- | --- |
| low | 2·1·1/4 + 분석 실행 2/4 → **6/16** | 38% (95% 약 18–61%) | 9/9 | 55,179 | 약 5초 | 기록 없음 |
| medium | 1·1·2/4 → **4/12** | 33% (약 14–61%) | 9/9 | 94,772 (1.7배) | 약 14초 | 평균 285초 |
| high | 0·1·2/4 → **3/12** | 25% (약 9–53%) | 9/9 | 168,431 (3.1배) | 약 30–45초 | 평균 589초 |

토큰 증가분은 거의 전부 출력(사고) 토큰이다. 입력은 세 강도 모두 회차당 약 4.4–4.7만이다.

| 위반 클립 | low | medium | high | 합계 |
| --- | --- | --- | --- | --- |
| `YT_0002` 중앙선 | 4/4 | 3/3 | 2/3 | 9/10 |
| `youtube_clip_01` 실선 | 2/4 | 1/3 | 1/3 | 4/10 |
| `141927` 실선(먼 회색 SUV) | 0/4 | 0/3 | 0/3 | 0/10 |
| `YT_0003` 실선(터널 원거리) | 0/4 | 0/3 | 0/3 | 0/10 |

`141927` Coarse 후보는 low에서 0–4초(정답 앞), medium·high에서 9–17.5초(정답 뒤)였다. 정답과 겹친 회차(9–12.5초, 10–12.75초, 10–13초)도 Fine이 모두 기각했다.

## 원인 분석 (low 1회, Fine 응답)

- **`YT_0003`:** Coarse가 4–7초(score 0.95)와 3–5초(0.8)를 골랐다. Fine은 두 후보 모두 `OBSERVED`로 답했다. 근거는 "검은색 세단이 4.75–5.5초에 흰색 실선을 넘어 차로 변경"이고, primitive는 PRESENT 0.95–0.98, `uncertainties`는 `NONE`이다. 같은 구간 1 fps 프레임을 직접 보면 검은색 세단은 4–7초에 촬영 차량을 오른쪽 뒤에서 추월해 오른쪽 차로를 따라 앞으로 나간다. 8–12초에는 소실점 근처의 후미등 몇 픽셀로만 보인다. 정답지는 5–10초를 정상 주행으로 확정했다. 그래서 가까운 추월 장면의 원근 이동을 차로 변경으로 본 것으로 해석한다(**가설**). 다만 Fine이 넘었다고 한 시각 4.75–5.5초 가운데 4–5초는 정답지가 직접 다루지 않는다. 1x 실행(9/26·9/29)에서도 Coarse는 3–7초를 골랐으므로 배속 환산 문제는 아니다. 이 실패는 위반 클립 안의 정답 밖 `OBSERVED`라서, 운영에서는 시각과 근거가 틀린 신고 자료가 된다.
- **`141927`:** Coarse는 0–2.25초(score 0.35)를 골랐고, 관찰은 "가까운 검은색 SUV가 백색 점선에서 차로 변경"이었다. Fine은 대상 `NOT_FOUND`이고, 두 SUV 모두 차로를 유지한다고 보고 lateral_movement·solid_line_crossing을 ABSENT 0.95로 답했다. 위반 차량인 먼 회색 SUV는 Coarse와 Fine 어디에도 나오지 않는다. medium·high의 10–17.5초 후보는 같은 SUV의 14–18초 점선 변경(합법) 쪽일 수 있다. 응답을 저장하지 않아 미확인이다.
- **`youtube_clip_01`:** 이번 회차는 HIT였다. 흰색 세단이 1.9초에 실선을 밟고 2.6초에 진입을 마친다고 답했고, 이는 새 정답 0–2초와 맞는다. 이전 MISS 회차들(같은 1–3초 후보에서 Fine 기각)은 응답을 저장하지 않아 기각 근거를 알 수 없다.
- **`YT_0002`:** HIT. 방향지시등 → 조향 → 앞바퀴가 황색 복선을 넘음 → 차체 진입 순서로 기술했다.

## 해석

- **추론 강도를 올려도 검출이 늘지 않았다.** low 38%, medium 33%, high 25%이고 95% 범위가 크게 겹친다. 좋아졌다는 근거는 없다. 오탐은 세 강도 모두 0이다.
- **못 푸는 두 클립은 강도와 무관하게 0/10이다.** 잡히는 클립은 위반 차량이 가깝고 크며, 놓치는 클립은 멀고 작다. 사고를 늘려도 그 차량을 보지 못하는 문제(`PRIMITIVE_FAILURE`·원거리 해상도 후보)는 풀리지 않는다는 해석과 맞는다.
- **비용:** medium은 토큰 1.7배·Fine 지연 약 3배, high는 토큰 3.1배·Fine 지연 6–9배다. 운영에서 쓰려면 provider를 스트리밍으로 바꿔야 한다.

## 한계

- 강도당 3회(low는 4회), 위반 4클립이다. 반복 정책은 [#158](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/158) 답변 대기다.
- low와 medium·high는 호출 경로(운영 provider non-streaming 대 실험 invoker 스트리밍)가 다르다. 영상 준비·프롬프트·배속·padding은 같다.
- 원인 분석은 low 1회 응답만 봤다. medium·high 회차와 low 운영 검증 회차는 Fine 응답을 저장하지 않았다.
- 이 기록은 운영 `reasoning_effort=low`와 `provider.py`를 바꾸지 않는다. D3의 결정은 이 기록 밖이다.
- 토큰 사용량: 파이프라인 medium·high 789,612, 원인 분석 37,431, 중단한 Fine 고정 구간 실행(non-streaming, 7호출) 26,692, 스트리밍 probe 14,057. **합계 867,792.**
