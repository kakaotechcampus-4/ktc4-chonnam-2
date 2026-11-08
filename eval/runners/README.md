# eval/runners

dataset과 구현 이름표(`--impl`)를 받아 구현을 호출하고 **immutable prediction**을 만든다. 이름표는 `registry.py`가 소유한다.

| 이름표 | 파일 | 무엇을 하나 |
| --- | --- | --- |
| `fake:always_correct` · `fake:always_wrong` | `impls/fake_always_*.py` | GT를 그대로 / 전부 틀리게 내는 치트. 지표 계산 검증용 |
| `mock_pack:contracts` | `impls/mock_pack.py` | 팀 공용 Mock Pack 산출물을 읽어 배관 연결 확인 |
| `search:gemini-coarse-p3` | `impls/search_gemini.py` | 제품 Search의 공개 `search_candidates`로 Coarse 후보만 |
| `search:s1-flash-1x` · `search:s2-flash-slow` · `search:s3-argon-gore` | `impls/search_pipeline.py` | 시점별 설정으로 Coarse → Fine 전체 경로(S1~S3) |
| `readout:paddle-crop` | `impls/readout_paddle.py` | readout 공개 `read_plate`로 번호판 crop 판독 |
| `readout-exp:yolo11n` | `impls/yolo_persistence.py` | readout 실험 설정(YOLO11n)의 차량 검출 지속성. 제품 코드 아님 |

실제 모델 runner는 제품 모듈의 공개 함수를 부르는 것이 원칙이지만, `search_pipeline.py`는 시점별 설정을 바꿔 끼우려고 Search의 설정·프롬프트·provider 모듈을 직접 import한다(파일 docstring 참조).
