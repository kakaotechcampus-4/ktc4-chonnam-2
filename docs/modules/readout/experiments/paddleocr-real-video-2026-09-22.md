# PaddleOCR 실제 영상 기준선 — 실험·결정 기록 (2026-09-22)

## 목적

실제 블랙박스 프레임에서 대상 차량 영역을 crop·확대했을 때 PaddleOCR가 번호판과 overlay를 어떤 계약 결과로 내는지 확인했다. 이 문서는 재실행용 원본 영상이나 개인 로컬 경로를 싣지 않고, 팀이 검토할 수 있는 관찰·결정·미결만 보존한다.

## 관찰과 측정 기록

| 항목 | 기록 |
| --- | --- |
| 입력 프레임 | `20260810_183258_EVT_1.avi`, 10.013초 |
| 사람 검토 전체 번호판 GT | `36수3105` |
| OCR 반환 | `36 3105`, confidence `0.933` |
| 첫 target-crop OCR 시간 | `15.995s` |
| 대상 차량 bbox | `[535, 575, 350, 275]` (`xywh`) |
| 수동 전체 번호판 bbox | `[618, 682, 105, 39]` (`xywh`) |
| OCR 텍스트 줄 bbox | `[627, 693, 80, 21]` (`xywh`) |
| 회귀 테스트 | 2026-09-23: `69 passed, 34 subtests passed` |

- 전체 화면 OCR은 번호판 후보를 만들지 못했다.
- 같은 프레임의 대상 차량 bbox를 crop하고 3배 확대하면 OCR 후보가 검출됐다.
- `36 3105`는 일부 관찰값으로 보존하되 `NEEDS_REVIEW`·`abstained=true`로 처리한다. 자동 확정값이 아니다.
- 황색 2줄 번호판의 하단 줄 `바5215`는 `PARTIAL_PLATE_READ`로 분류해 `NEEDS_REVIEW`·`abstained=true`가 되도록 수정·회귀 테스트했다. 텍스트 한 줄 bbox는 `best_frame`으로 발행하지 않는다.

## 좌표와 이미지 원칙

- 입력 target bbox는 대상 **차량**의 원본 `FrameRef` 픽셀 좌표 `[x,y,w,h]`다.
- `best_frame.plate_bbox_xywh`는 사용자가 확대 이미지에서 판단할 수 있도록 같은 원본 프레임의 **전체 번호판** bbox여야 한다.
- 텍스트 한 줄 bbox, 특히 2줄 번호판의 하단 줄 bbox를 전체 번호판 bbox로 표시하지 않는다.
- Case는 `best_frame.frame_ref + best_frame.plate_bbox_xywh`로 `PLATE_IMAGE` 생성을 발주한다. 따라서 이 bbox의 의미는 UI 편의가 아니라 계약 입력이다.

## 현재 한계와 후속

현재 PaddleOCR detector는 줄 단위 bbox를 반환한다. 2줄 번호판의 전체 bbox를 안정적으로 산출하는 detector/병합 규칙은 이번 기준선 범위에 없다. 그 경로가 준비되기 전에는 하단 줄 bbox를 전체 번호판 bbox로 승격하지 않는다. 다음 실험은 수동 전체 번호판 GT가 있는 여러 프레임에서 후보 detector/2줄 병합 규칙의 bbox 정확도를 측정한 뒤에만 구현한다.

또한 `?`는 현 계약에서 프레임 간 합의가 깨진 문자 위치를 표시하는 표기다. 단일 결과에서 형식으로 누락 위치를 추론한 부분 판독까지 `?`로 표현하려면, `PARTIAL_PLATE_READ`와 해당 위치의 의미를 계약·taxonomy에 별도로 등재해야 한다.

## 검증

```text
python -m pytest tests/readout/test_public_functions.py tests/readout/test_target_crop.py tests/readout/test_recording_frame_source.py -q
```

PR #138에서 대상 crop 좌표 복원, frame 불일치 hint의 전체 화면 fallback 금지, 숫자만 읽힌 대상 crop의 보류 동작을 자동 테스트한다.
