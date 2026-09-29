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
- [p4-retired-2026-09-25/conditions.md](p4-retired-2026-09-25/conditions.md) — 종료한 p4의 구현 계획, 두 회차 조건·보고서·결과, 원문 프롬프트 보존
