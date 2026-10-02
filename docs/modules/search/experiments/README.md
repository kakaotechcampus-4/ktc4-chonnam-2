# search/experiments

재현 가능한 실험 기록을 둔다. 입력/설정/결과/실패/다음 learning을 남긴다. AI 원문과 원본 영상은 저장소에 두지 않는다.

- [coarse-fine-probe-summary-2026-09-12.md](coarse-fine-probe-summary-2026-09-12.md) — 약 39분 주행 영상 Coarse·Fine 탐침 총정리
- [decision-trace-guide.md](decision-trace-guide.md) — 로컬 진단 실행과 전체 관찰 출력 형식
- [7영상 진단 실행 결과 JSON](decision-trace-seven-video-2026-09-26-results.json) — p3·진단 형식 각 1회의 수치·상태·해시
- [프록시 경유 영상 샘플링](gemini-proxy-video-sampling-2026-09-28.md) — 로컬 fps·해상도와 관계없이 1 fps·low로 처리되고 파라미터로 바꿀 수 없음 ([JSON](gemini-proxy-video-sampling-2026-09-28-results.json))
- [이미지 프레임 probe](gemini-image-frame-probe-2026-09-28.md) — image_url은 수용되고 프레임당 1,100토큰(해상도 무관)·fps 제어 가능하나 해상도 노브는 없음 ([JSON](gemini-image-frame-probe-2026-09-28-results.json))
- [Fine 이미지 정확도](gemini-fine-image-accuracy-2026-09-28.md) — 정답 구간을 줘도 fps 1/2/4로 실선 판별 정확도가 오르지 않음 ([JSON](gemini-fine-image-accuracy-2026-09-28-results.json))
- [Coarse→Fine 이미지 트레이스](gemini-coarse-fine-image-trace-2026-09-28.md) — 실제 구조를 이미지(coarse 2fps/fine 4fps)로; 검출 2→4, 비용 약 30배, 141927 여전히 놓침 ([JSON](gemini-coarse-fine-image-trace-2026-09-28-results.json))
- [느린 영상 토큰 probe](gemini-video-slowdown-token-probe-2026-09-29.md) — 영상을 늘리면 토큰 = 재생 길이 × 66, 0.5x·0.25x로 원본 2·4 fps를 영상 단가로 넣음 ([JSON](gemini-video-slowdown-token-probe-2026-09-29-results.json))
- [Coarse→Fine 느린 영상 트레이스](gemini-coarse-fine-slowdown-trace-2026-09-29.md) — 이미지와 같은 프레임 밀도(coarse 0.5x/fine 0.25x)를 영상으로; 위반 2/4·2/4, 토큰은 이미지의 약 1/15 ([JSON](gemini-coarse-fine-slowdown-trace-2026-09-29-results.json))
- [Coarse→Fine handoff 트레이스](gemini-handoff-trace-2026-09-29.md) — diagnostic-v1 대조로 handoff를 이미지·느린 영상(coarse 2/fine 4 fps) 각 2회; 효과 구분 안 됨, 음성 끌림 0, p3 대비 개선 없음 ([이미지 JSON](gemini-handoff-image-trace-2026-09-29-results.json) · [느린 영상 JSON](gemini-handoff-slowdown-trace-2026-09-29-results.json))
- [Fine 고정 구간·불확실성 규칙](gemini-fine-window-uncertain-2026-10-01.md) — 정답 구간을 Fine에 직접 줘 diagnostic-v1 대 uncertain-v1 각 3회; 판정 차이 0, YT_0003은 대상을 맞게 잡고도 원거리 횡이동을 못 봄, 141927은 가까운 다른 SUV를 대상으로 잡음 ([JSON](gemini-fine-window-uncertain-2026-10-01-results.json))
- [Fine crop × 대상 힌트](gemini-fine-crop-hint-2026-10-01.md) — 원본 해상도 crop·target_hint 각각·함께 3회; 대상 연결은 고쳐지나 위반 2구간 검출 0/24, 점선 오탐 0; 141927을 4–10초로 넓혀도, 느린 영상+crop으로 보내도 0/3 ([JSON](gemini-fine-crop-hint-2026-10-01-results.json))
- [Coarse recall 프롬프트 변형](gemini-coarse-recall-prompt-2026-10-01.md) — Coarse만 느린 영상으로 p3·subject-v1·multi-v1 각 3회; recall 6/12로 동일, 141927은 위반 SUV를 찾지만 시각이 늦음 ([JSON](gemini-coarse-recall-prompt-2026-10-01-results.json))
- [느린 영상 시각 환산 검증](gemini-slow-video-time-probe-2026-10-01.md) — 프레임 대응(API 없음)과 빨간 사각형 probe; 변환·모델 응답 모두 0.5초 이내, Coarse 시각 오차는 환산 문제가 아님 ([JSON](gemini-slow-video-time-probe-2026-10-01-results.json))
- [프록시 인라인 요청 크기 한도](gemini-proxy-size-probe-2026-10-01.md) — 10초 영상을 10–61 MiB로 키워 1회씩; 요청 81 MiB까지 성공, 토큰 불변·응답 시간만 증가 ([JSON](gemini-proxy-size-probe-2026-10-01-results.json))
- [운영 경로 검증 v3](search-v3-production-verify-2026-10-01.md) — GeminiProvider 그대로 7클립 3회; 위반 2/4·1/4·1/4, 오탐 0, 회차 평균 5.5만 토큰, 영상 밖 후보 1건(#181) ([JSON](search-v3-production-verify-2026-10-01-results.json))
- [p4-retired-2026-09-25/conditions.md](p4-retired-2026-09-25/conditions.md) — 종료한 p4의 구현 계획, 두 회차 조건·보고서·결과, 원문 프롬프트 보존
