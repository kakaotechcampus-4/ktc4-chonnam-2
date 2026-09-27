# 2026-09-15 실행 환경

이 폴더의 수치를 만든 환경을 기록한 것이다. 실행은 팀 레포 코드가 아니라 **그때 따로 짠
스크립트**로 했고(`scripts/`), 환경은 특정 PC에만 있었다. 그 PC를 잃기 전에 남기는 기록이다.

## 먼저 알아야 할 것 — 남아 있던 환경은 못 쓴다. 다시 깔면 된다 (2026-09-19 확인)

`C:\tmp\paddle-ocr`에 풀려 있던 패키지 더미는 **CPython 3.12 전용 바이너리**다
(`pydantic_core/_pydantic_core.cp312-win_amd64.pyd`, `_cffi_backend.cp312-win_amd64.pyd`,
`ujson.cp312-win_amd64.pyd`). venv가 아니라 `sys.path.insert`로 경로에 꽂은 더미라
인터프리터가 바뀌면 그대로는 못 쓴다. **아래 정보는 「다시 깔아서 재현하는 법」이지
「남아 있는 환경을 쓰는 법」이 아니다.**

**다만 재설치 경로는 실제로 동작한다.** 2026-09-19에 다른 PC에서 아래로 복원했고 같은
버전 조합이 나왔다 — 이 문서가 한때 「재현되지 않는다」로 적었던 것은 특정 PC에 3.12가
없다는 사실을 환경 자체의 성질로 잘못 옮긴 것이다.

```bash
uv venv --python 3.12 <경로>
uv pip install --python <경로>/Scripts/python.exe \
    "paddlepaddle==3.3.1" "paddleocr==3.7.0" "opencv-contrib-python==4.10.0.84"
```

복원 결과 `python 3.12.13` · `paddlepaddle 3.3.1` · `paddleocr 3.7.0` · `cv2 4.10.0`.
모델 가중치는 첫 실행에서 `~/.paddlex/official_models/`로 자동 내려받는다
(`PP-OCRv5_mobile_det` · `korean_PP-OCRv5_mobile_rec`).

> **재현이 「같은 수치」를 보장하지는 않는다.** 위는 버전 조합을 되살리는 방법이고,
> 이 폴더의 수치는 그때의 입력·프레임 선택·필터까지 같아야 재현된다. 실제 판독 경로가
> 무엇이었는지는 아래 「전처리」 절을 봐야 한다.

## 인터프리터

| 항목 | 값 |
| --- | --- |
| Python | 3.12 (x86-64, Windows) — 정확한 patch 버전은 기록이 남지 않았다 |
| 가상환경 | **없다.** venv가 아니라 `sys.path.insert(0, r'C:\tmp\paddle-ocr')`로 패키지 더미를 경로에 꽂았다 |
| 패키지 위치 | `C:\tmp\paddle-ocr` (2026-09-15 23:09 생성) · `C:\tmp\ocr-tools` (opencv-python-headless 5.0.0.93 단독) |

`ocr_test_extract.py`만 `C:\tmp\ocr-tools`를 쓰고 나머지는 `C:\tmp\paddle-ocr`를 쓴다.
두 경로에 opencv가 각각 따로 들어 있다(4.10.0.84 / 5.0.0.93).

## 핵심 패키지

| 패키지 | 버전 |
| --- | --- |
| `paddleocr` | 3.7.0 |
| `paddlepaddle` | 3.3.1 (CPU) |
| `paddlex` | 3.7.2 |
| `numpy` | 2.3.5 |
| `opencv-contrib-python` | 4.10.0.84 |
| `opencv-python-headless` | 5.0.0.93 (`C:\tmp\ocr-tools` 쪽) |
| `pillow` | 12.3.0 |
| `shapely` | 2.1.2 |
| `pyclipper` | 1.4.0 |

전체 70개는 `requirements-frozen.txt`에 있다. `pip freeze` 출력이 아니라 `dist-info`
디렉터리 이름에서 복원한 것이라, 그 목록에 `python_bidi`가 0.4.2와 0.6.11 두 벌로
들어가 있다 — 실제로 어느 쪽이 import됐는지는 확정할 수 없다.

## 모델

| 역할 | 모델 이름 |
| --- | --- |
| detection | `PP-OCRv5_mobile_det` |
| recognition | `korean_PP-OCRv5_mobile_rec` |

캐시 위치는 `~/.paddlex/official_models/`다. 두 모델 모두 PaddleOCR이 자동 다운로드한
공식 가중치이고, **fine-tuning 하지 않은 그대로**다.

공통 초기화 옵션 (`paddle_batch.py` · `paddle_probe.py`):

```python
PaddleOCR(
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
    enable_mkldnn=False,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)
```

500장 평가는 detection을 거치지 않고 `TextRecognition(model_name='korean_PP-OCRv5_mobile_rec',
enable_mkldnn=False)`를 직접 쓴다. `use_doc_unwarping` · `use_textline_orientation`이 전부
꺼져 있다는 점이 중요하다 — **2줄·세로형 번호판에 rectification이 걸리지 않았다.**

## 입력 데이터 — 레포에 없다

| 입력 | 경로 | 쓰인 곳 |
| --- | --- | --- |
| 블랙박스 AVI 3개 | `~/Downloads/20260806_061434_EVT_1.avi` 외 2개 | video-pilot |
| AI Hub 172 번호판 OCR | `~/Downloads/자동차 차종-연식-번호판 인식용 영상/` | dataset-500 |

스크립트에 이 절대경로가 하드코딩돼 있다. 다른 곳에서 돌리려면 경로를 고쳐야 한다.
500장 표본은 `random.Random(20260915)`로 고정돼 있어 같은 라벨 집합이면 같은 표본이 나온다.

## 실행 순서

```
# video-pilot
python scripts/video-pilot/ocr_test_extract.py    # AVI 메타 + 대표 프레임 24장/영상 + contact sheet
python scripts/video-pilot/paddle_probe.py        # 단일 프레임 동작 확인
python scripts/video-pilot/paddle_batch.py        # 영상별 5프레임 OCR -> paddle_results.json
python scripts/video-pilot/make_plate_crops.py    # 번호판 후보 crop 비교 이미지

# dataset-500
python scripts/dataset-500/probe_recognition.py   # 10장 사전 점검
python scripts/dataset-500/evaluate_500.py        # 500장 평가 -> paddleocr_500_{results,summary}.json
python scripts/dataset-500/build_report.py        # threshold·종횡비 분석 -> OCR_BASELINE_REPORT
```

`dataset_profile.py`는 이 흐름과 별개로 데이터셋 구조·중복·split 교집합을 조사한 것이다
(결과: `DATASET_BRIEFING_2026-09-15.md`).

## 산출물 원본 위치

`~/Documents/카테캠/` 아래이고 레포에 없다. 인덱스는 같은 폴더의 `OCR_RESULTS_INDEX.md`다.
2026-09-18에 `~/OneDrive/카테캠-backup-2026-09-18/`로 사본을 떴다(35MB · 93개 파일).

이 폴더의 두 tagging JSON에 박힌 `source_sha256`은 2026-09-18 재검증에서 원본과 일치했다.

| 파일 | sha256 |
| --- | --- |
| `ocr-test/paddle_results.json` | `9fc4e253...ca98c1f8` |
| `ocr-dataset-eval/paddleocr_500_results.json` | `bacdce64...6240a48fb` |

## 전처리 — 아무것도 하지 않았다 (2026-09-19 추가)

수치를 「PaddleOCR 성능」이 아니라 **「원본 프레임 무보정 1-pass · mobile 모델」 성능**으로
읽어야 하는 이유다. 스크립트에서 확인한 그대로다.

| | video-pilot | dataset-500 |
| --- | --- | --- |
| 투입 | 원본 **1920×1080 전체 프레임** | 정답 crop 파일 그대로 |
| crop | 없음 | (입력이 이미 crop) |
| 확대·대비·샤프닝 | 없음 | 없음 |
| 다중 프레임 | 없음 — 5장 각각 독립 1회 | 해당 없음 |
| 호출 | `PaddleOCR.predict` (det+rec) | `TextRecognition.predict` (rec 단독) |

`use_doc_orientation_classify` · `use_doc_unwarping` · `use_textline_orientation` **셋 다 `False`**.
`make_plate_crops.py`의 600×180 확대는 사람이 보라고 만든 contact sheet이고 OCR 경로가 아니다.

video-pilot은 후보를 `digits >= 3` · `w/h >= 2.2` · `y1 < 1020` 휴리스틱으로 골랐다.
**판독 로직이 아니라 스크립트 필터**이므로 이 조건에 걸려 빠진 후보가 있다.

### det이 입력을 절반으로 줄인다

`PP-OCRv5_mobile_det`의 `inference.yml`은 `DetResizeForTest: resize_long: 960`이다.
**1920×1080을 통째로 넣으면 긴 변이 960으로, 정확히 0.5배 축소된다.**

| | 원본 좌표 | det이 실제로 본 크기 |
| --- | ---: | ---: |
| 2줄 번호판 아랫줄 | 35px | **17.5px** |
| 같은 번호판 윗줄 | 약 20px | **10px** |

`api.py`의 `MIN_PLATE_PX_HEIGHT = 20`은 **원본 좌표 기준**이다. 모델이 보는 크기와 다르므로
이 임계값을 검출 성능과 직접 견주지 않는다.

## 이 환경이 수치에 남긴 제약

기준선 해석에 직접 걸리는 것만 적는다.

1. **rectification·방향보정이 전부 꺼져 있다.** 종횡비별 결과(wide 25.0% / medium 1.3% /
   tall 0%)의 상당 부분이 이 설정에서 온다. 모델 자체의 상한이 아니다.
2. **500장은 recognition 단독**이라 detection 성능이 섞이지 않은 대신, 1줄 recognizer에
   2줄·지역명 번호판을 그대로 넣었다. 지역명 152장 Exact 0은 모델 실패라기보다 **방법상
   그 값이 나올 수 없는 구성**이다.
3. **범용 한국어 recognizer**다. 번호판 전용 학습이 없다.
