# eval/experiments

재현 가능한 실험 기록을 둔다. 입력/설정/결과/실패/다음 learning을 남긴다.

한 실행 = 파일 하나, 이름은 `YYYY-MM-DD-<impl>-<목적>.md`. 형식은 `../experiment-guide.md`의 「Experiment Note Template」을 따른다. 수치의 원본은 `eval/predictions/`·`eval/results/`의 JSON이고, 여기에는 읽는 법과 해석을 적는다.

| 날짜 | 기록 | impl | manifest · GT | 역할 |
| --- | --- | --- | --- | --- |
| 2026-09-28 | [Gemini Coarse 베이스라인](2026-09-28-gemini-coarse-p3-baseline.md) | `search:gemini-coarse-p3` | `b_youtube` m3 · g3 | baseline |
| 2026-09-28 | [readout 번호판 인식 베이스라인](2026-09-28-readout-paddle-crop-baseline.md) | `readout:paddle-crop` | `private_aihub172_plate` m1 · ap1 (비공개) | baseline |
