# eval/experiments

재현 가능한 실험 기록을 둔다. 입력/설정/결과/실패/다음 learning을 남긴다.

한 실행 = 파일 하나, 이름은 `YYYY-MM-DD-<impl>-<목적>.md`. 형식은 `../experiment-guide.md`의 「Experiment Note Template」을 따른다. 수치의 원본은 `eval/predictions/`·`eval/results/`의 JSON이고, 여기에는 읽는 법과 해석을 적는다.

| 날짜 | 기록 | impl | manifest · GT | 역할 |
| --- | --- | --- | --- | --- |
| 2026-09-28 | [Gemini Coarse 베이스라인](2026-09-28-gemini-coarse-p3-baseline.md) | `search:gemini-coarse-p3` | `b_youtube` m3 · g3 | baseline |
| 2026-09-28 | [readout 번호판 인식 베이스라인](2026-09-28-readout-paddle-crop-baseline.md) | `readout:paddle-crop` | `private_aihub172_plate` m1 · ap1 (비공개) | baseline |
| 2026-09-28 | [readout 트랙① 차량 검출 지속성](2026-09-28-readout-yolo11n-track1-baseline.md) | `readout-exp:yolo11n` (제품 코드 아님) | `private_aihub172_track1` m1 · at1 (비공개) | baseline |
| 2026-10-28 | [Search 시점별 전체 경로 평가](2026-10-28-search-points-pipeline.md) | `search:s1-flash-1x` · `s2-flash-slow` · `s3-argon-gore` | `b_youtube_m4` m4 · g4 · `ctier2` · `ctier3` g1 | 시점 비교 (개발 중 반복 측정) |
| 2026-10-28 | [OCR 시점별 평가](2026-10-28-ocr-points.md) | `readout:paddle-crop` (O1 · O2 · O4 가중치) | `private_aihub172_plate_m2` m2 · ap2 (비공개) | 시점 비교 (개발 중 반복 측정) |
| 2026-10-30 | [AI-Hub 선별 영상 유형 평가와 블박 삽입 진단](2026-10-30-aihub-best100-video-and-mixed.md) | `search:s3-argon-gore` Coarse · Fine | `a_aihub_best100_val` bm1 · bg1 / `aihub_mixed_100_v1` mv1 | 새 양성 영상의 유형 적중 · 합성 탐색 개발 진단 (8쌍 파일럿 포함) |
| 2026-10-31 | [AIHub 영상·블박 삽입 S1/S2/S3 비교](2026-10-31-aihub-video-search-points.md) | `search:s1-flash-1x` · `s2-flash-slow` · `s3-argon-gore` | `a_aihub_best100_all` 400 · 중복 제거 Validation 117 · `aihub_mixed_100_v1` 100쌍 | 같은 입력의 유형 적중·삽입 구간 탐색·정상 대조 오탐 비교 |
