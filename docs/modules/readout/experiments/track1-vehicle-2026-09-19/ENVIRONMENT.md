# 실행 환경 — 트랙 ① 대상차량 검출 (2026-09-19)

`ocr-baseline-2026-09-15/ENVIRONMENT.md`와 같은 규칙이다. **이 파일 없이는 수치를 믿지 않는다.**

## 기계

| 항목 | 값 |
| --- | --- |
| OS | Windows 11 Home 26200 |
| 가속기 | **없음. CPU 추론이다** (`torch.cuda.is_available()` → `False`) |

## 파이썬 환경

**PaddleOCR 환경(`D:\paddle-env`)이 아니다.** 그쪽에는 `ultralytics`도 `torch`도 없다.
검출은 `~/Documents/카테캠/readout_plate_detection/.venv`에서 돌렸다.

| 항목 | 값 |
| --- | --- |
| 경로 | `C:\Users\tlsdb\Documents\카테캠\readout_plate_detection\.venv` |
| Python | 3.12.14 |

```text
ultralytics==8.4.133
ultralytics-thop==2.1.6
torch==2.13.0+cpu
torchvision==0.28.0+cpu
numpy==2.3.5
pillow==12.3.0
opencv-contrib-python==4.10.0.84
opencv-python==5.0.0.93
```

> ⚠️ **opencv가 두 개 깔려 있다.** `import cv2`가 보고하는 버전은 `4.10.0`이므로
> `opencv-contrib-python` 쪽이 이겼다. 재현할 때 `opencv-python==5.0.0.93`만 깔면
> 다른 디코더를 쓰게 된다. 이 충돌은 이 실험에서 해소하지 않았다.

> ⚠️ 콘솔 기본 인코딩이 cp949라 한글 출력이 깨진다. 전부
> `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`을 붙여 돌렸다. 깨진 출력을 보고 라벨명을
> 추측한 것이 9/18 정정 2건의 원인이었다.

## 모델

| 항목 | 값 |
| --- | --- |
| 가중치 | `yolo11n.pt` (Ultralytics COCO 사전학습, `assets` release `v8.4.0`) |
| sha256 (앞 24자) | `0ebbc80d4a7680d14987a577` |
| 크기 | 5,613,764 B |
| 파인튜닝 | **없음.** 내려받은 그대로 |
| 쓴 클래스 | COCO `2 car` · `3 motorcycle` · `5 bus` · `7 truck` |
| conf | 0.25 |
| imgsz | 640 (Ultralytics 기본 letterbox) |
| 매칭 IoU | 0.50 |

**이 가중치는 레포에 넣지 않았다.** 5.4MB 바이너리이고 위 URL에서 받으면 같은 파일이다.

## 데이터

| 항목 | 값 |
| --- | --- |
| 데이터셋 | AI Hub 「교통법규 위반 상황 데이터」 (`71555`) · 01-1.정식개방데이터 · Validation |
| 위치 | `D:\228.교통법규 위반 상황 데이터\01-1.정식개방데이터\Validation\` |
| 원천 | `01.원천데이터\VS.zip` · 55,207,757,510 B (51.42 GiB) · 이미지 224,859장 |
| 라벨 | `02.라벨링데이터\VL.zip` · 258,538,680 B · JSON 224,859건 |
| `VL.zip` sha256 | `e756504865772b1e2c2c1799345794b3b486541ccd4c958636d4c4f8b1285c61` |
| `VS.zip` sha256 | `237086e5393e312f628cf0cb4afc5bcf49d1b587a2ac2cd18488c0818fd04df0` |
| 표본 seed | `20260919` |

**압축을 풀지 않았다.** `zipfile`로 zip에서 직접 읽었다 — D: 여유가 92GB뿐이라
51GB를 풀 수 없고, 필요한 것은 표본 1,600장뿐이다.

## 재현 절차

```bash
python scripts/aihub71555_labels.py probe            # 스키마 확인이 먼저다
python scripts/aihub71555_labels.py stats            # 전수 분포 (약 3.5분)
python scripts/aihub71555_labels.py sample --n 1600 --seed 20260919 \
    --out docs/modules/readout/experiments/track1-vehicle-2026-09-19/sample-manifest.json
python scripts/aihub71555_detect.py --selfcheck      # IoU·매칭 자체 점검
python scripts/aihub71555_detect.py \
    --manifest .../sample-manifest.json --model yolo11n.pt --out .../detections.json     # 진행 로그는 stderr
python scripts/aihub71555_report.py --detections .../detections.json > .../RESULTS.md

python scripts/aihub71555_associate.py --selfcheck        # 선택 규칙 자체 점검
python scripts/aihub71555_associate.py --detections .../detections.json > .../ASSOCIATION.md  # 재실행 없이 다시 접는다
```

`ROOT` 경로는 `scripts/aihub71555_labels.py` 상단에 하드코딩돼 있다. 다른 기계에서는
그 줄을 고친다.
