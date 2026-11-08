# eval/predictions

runner 출력. 한 번 만든 prediction은 바꾸지 않는다 — GT/metric이 바뀌면 scorer만 다시 돈다.

- 커밋하는 것: 치트·mock 대조(`demo_*` · `mock_*`)와 실제 모델 실행(`gemini_coarse_p3_*` · `search_s*`)의 prediction.
- 커밋하지 않는 것: AI-Hub 실험 원본(`aihub_*.json`). 너무 커서(PR #496에서 13만 줄) `.gitignore`로 제외하고, 원본은 공유 드라이브 zip에 둔다. 채점 결과는 `eval/results/`에 있다.
- 실제 번호판 문자열이 들어가는 `private_*` manifest의 prediction은 레포가 아니라 `DAESINGO_EVAL_PRIVATE_ROOT` 아래에 둔다(`eval/paths.py`).
