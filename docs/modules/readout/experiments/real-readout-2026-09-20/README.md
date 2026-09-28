# [readout] 실제 영상으로 계약 객체를 만든 첫 실행 (2026-09-20)

> 작성 신유민(`readout` Owner) · Real Data E2E(W6)

**앞의 두 실험과 다른 점은 「무엇이 계약을 통과했는가」다.**

| 폴더 | 무엇을 넣었나 | 공개 함수를 통과했나 |
| --- | --- | --- |
| `merge-evidence-2026-09-14/` | fixture | ✅ (계약 준수 증빙) |
| `ocr-baseline-2026-09-15/` · `track1-vehicle-2026-09-19/` | 실제 픽셀 | ❌ provider 단독 측정 |
| **이 폴더** | **실제 픽셀** | **✅** |

그래서 여기 있는 JSON은 측정 요약이 아니라 **`read_plate`·`read_overlay_time`이 그대로
돌려준 `ReadoutRun`·`PlateReadout`·`OverlayTimeReadout`**이다. Evidence는 이것을 그대로
받으면 된다.

**수치가 아니라 경로를 보이는 실행이다.** 영상 3개로 성능을 말하지 않는다.

## 결과

| 영상 | `PlateReadout` | `OverlayTimeReadout` |
| --- | --- | --- |
| `20260806_192353` 정지·정면·백색 1줄 | `23두4874` · `OK` · 3프레임 만장일치 (conf 0.923~0.991) | `2026-08-06T19:23:54+09:00` · `OK` · 검증 3종 통과 |
| `20260810_175721` 정지·근거리·황색 2줄 | `바5215` · `OK` · conf 0.992~0.999 | `2026-08-10T17:57:27+09:00` · `OK` · 검증 3종 통과 |
| `20260806_061434` 주행·원거리·횡방향 | `null` · `UNKNOWN` · 검출 0 | `null` · `UNKNOWN` (아래 ③) |

세 번째가 **보류(`abstained=true`)가 아니라 「알 수 없음」으로 떨어지는 것**이 설계대로다.
읽어낸 글자가 없으면 보류할 관찰값 자체가 없다(`api.py` `read_plate`).

두 번째는 **`ocr-baseline-2026-09-15` §①의 황색 2줄 문제가 계약 경로로 그대로 재현된 것**이다.
아랫줄만 읽고 `abstained=false` · `status=OK`로 확정된다. 처리 방침은 ADR-EVIDENCE-006이
소유한다 — readout은 관찰값을 보존하고 evidence가 사용자 확인 상태를 붙인다.

`target_association.status`가 전부 `LOW_CONFIDENCE`인 것은 `target_hint` 없이 돌렸기
때문이다. 근거는 `track1-vehicle-2026-09-19` §2 — 검출 결과만으로 고르면 최고 57.7%이고
틀릴 때 26~33%가 정상 차량이다.

## 이 실행에서 나온 것 3건

### ① PR #81이 없으면 overlay 시각이 하나도 안 나온다

같은 영상을 #81 적용 전후로 돌린 결과다. **#81은 2026-09-20 merge됐고, 이 폴더의 JSON은
merge 이후 상태에서 뽑았다.** 기록으로 남긴다.

| | #81 이전 | #81 이후 |
| --- | --- | --- |
| `observation.value` · `status` | `null` · `UNKNOWN` | `2026-08-10T17:57:27+09:00` · `OK` |
| `format_ok` · `monotonic_ok` · `duration_match_ok` | `false` · `null` · `null` | `true` · `true` · `true` |

**PR #81의 evidence 리뷰 질문에 대한 실측 답이기도 하다** — 실제 실행에서 sample 3건이
잡히고 두 validation이 `null`이 아닌 값으로 판정된다. offset 6.0/10.0/14.0초가 시각
27/31/35초에 대응해 `duration_match_ok`가 실제로 검증됐다. 따라서 evidence의
`_valid_overlay()`는 현재 구현 그대로 통과한다.

### ② overlay 줄이 번호판 후보로 올라왔다 — 구현 결함, 고쳤다

`20260806_061434`는 번호판이 검출되지 않는데, 화면 하단 overlay
(`2026/08/06 06:14:34 13.80 X:+0.062 ...`)가 「숫자 3개 이상 + 가로세로비 2.2」 필터를
통과해 번호판 후보로 올라왔다.

이 영상은 프레임마다 시각이 달라 `FRAME_DISAGREEMENT`로 보류됐지만, **시각이 같았다면
overlay 문자열이 `status=OK`로 확정된다.** 한글 포함·timestamp 제외 조건을 걸어 막았고
(`paddle_provider.py` `HANGUL`), 실측 문자열을 그대로 selfcheck에 넣어 뒀다.

**fixture로는 나올 수 없는 결함이다** — fixture의 provider 출력에는 overlay 줄이 번호판
후보로 섞여 들어오지 않는다.

### ③ [미결] OCR이 날짜와 시각 사이 공백을 빠뜨리면 overlay 전체가 `UNKNOWN`이 된다

`20260806_061434`의 3프레임 중 2프레임은 정상으로 읽혔다.

```
 6.007s  '2026/08/06 06:14:34 13.80 ×:+0.062 ...'  -> 2026-08-06T06:14:34+09:00
10.012s  '2026/08/06 06:14:39 13.80 ×:+0.008 ...'  -> 2026-08-06T06:14:39+09:00
14.017s  '2026/08/0606:14:43 13.80 ×:+0.094 ...'   -> null      ← 공백이 없다
```

`api.py`의 `OVERLAY_TIME_IN_TEXT`가 날짜와 시각 사이 구분자를 필수로 요구해 세 번째가
`null`이 되고, 부분 실패는 전체 `ocr_failed`로 접히므로(`_interpret_overlay`)
**2/3이 읽혔는데 overlay 전체가 `UNKNOWN`이 된다.**

구분자를 optional로 바꾸면 한 글자지만, 그러면 `2026/08/0606:14:43`을 유효한 시각으로
인정하는 것이 된다. **값을 정하지 않는다** — PR #81 리뷰에서 PM이 요청한 「overlay 표기 형식
다양성 실측」의 첫 사례이므로 그 후속에서 함께 정한다.

## 다시 돌리려면

```bash
PYTHONPATH=src D:/paddle-env/Scripts/python.exe scripts/run_readout_real.py \
    --clip ~/Downloads/20260810_175721_EVT_1.avi \
    --out docs/modules/readout/experiments/real-readout-2026-09-20
```

픽셀·PaddleOCR 없이 판정부만 검사하려면 `--selfcheck`.

**환경은 `ocr-baseline-2026-09-15/ENVIRONMENT.md`와 같다** — 그 문서의 복원 절차로 깐
`D:\paddle-env`에서 돌렸다. `paddleocr 3.7.0` · `paddlepaddle 3.3.1`(CPU) ·
`opencv 4.10.0` · Python 3.12.13. 모델은 `PP-OCRv5_mobile_det` ·
`korean_PP-OCRv5_mobile_rec`(첫 실행에서 자동 다운로드).

**프레임 선택은 영상 길이의 30% · 50% · 70% 3점이다.** 2점 이상이어야 하는 이유는
`LocalVideoFrameSource.__init__` docstring에 있다(값이 `null`로 남으면 evidence가 overlay를
최종 시각으로 쓰지 않는다).

### 원본 영상 — 레포에 없다

| 파일 | sha256 |
| --- | --- |
| `20260806_061434_EVT_1.avi` | `43f34c1b199385a655c994d8db02204bae7a566a23a6ca9bc400a3551c16b632` |
| `20260806_192353_EVT_1.avi` | `4111ccf483eb941d59678fcc76a542985b6ab83732c3325404156e0dcf84633f` |
| `20260810_175721_EVT_1.avi` | `6806006897fc2ce1e4a4797c27f0ed256c786615f6096232d5bca710da6adc35` |

`ocr-baseline-2026-09-15`가 쓴 것과 같은 영상 3개다(각 25,804,800 B).

## 알려진 단순화 — 각 JSON의 `known_simplifications`에도 있다

1. **`frame_ref`가 임시값이다.** `FrameRef` 발급은 `recording` 소유인데
   (`contract-plate-overlay-readout.md` §「`frame_ref` 형식」) 실제 영상을 `MediaStream`으로
   등록하는 경로가 아직 없다. `read_frame()`으로 조회되지 않는다.
2. **`tz_offset`을 `+09:00`으로 고정했다.** 정식 출처는 clip의 source 메타데이터다.
3. **`target_hint` 없이 실행했다.** `search`의 실제 후보와 잇기 전 단계다.

1번은 `.frames(clip_ref)`만 구현한 공급자를 `PaddleOcrProvider`에 넘기면 교체된다 —
provider 본체는 바뀌지 않는다.
