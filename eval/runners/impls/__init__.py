"""runner가 부르는 구현 모음. 이름표 → 파일 대응은 `eval/runners/registry.py`와 `eval/runners/README.md`.

`fake_always_*`는 GT 를 직접 읽는 치트(지표 계산 검증용)이고, `mock_pack`은 계약 fixture 연결 확인용이다.
`search_*` · `readout_*` · `yolo_persistence`는 실제 모델을 부르는 실행기다.
"""
