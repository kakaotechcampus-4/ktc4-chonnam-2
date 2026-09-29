# [readout] 한국 번호판 한글 자리는 어떻게 읽나 — 선행연구·공개 모델 조사와 실측 확인 (2026-09-28)

> 작성 신유민(`readout` Owner) · **조사 결과이지 결정이 아니다**(`docs/README.md` — 「Research는 근거이지 결정이 아니다」).
> 실측 근거: `../experiments/plate-ocr-ablation-2026-09-27/` §3-② · §3-⑤

## 한 줄

**번호판 한글을 안정적으로 읽은 사례는 전부 번호판 전용으로 학습한 모델이었다. 우리 블랙박스 영상에서도
전용 모델은 한글을 읽었다 — 대신 못 읽는 번호판에도 번호를 지어내서, 프레임 간 일치 조건 없이는 쓸 수 없다.**

---

## 1. 목적 — 왜 조사했나

readout은 PaddleOCR 3.7 `korean_PP-OCRv5_mobile_rec`로 번호판을 읽는다. 사람이 읽은 실제 블랙박스 번호판
13개로 재 보니 **숫자는 대체로 맞는데 한글 한 글자(용도 기호)가 빠지거나 숫자로 바뀌었다.** 틀린 9개 중 7개다.

처음에는 해상도 탓으로 봤다(첫 사례에서 한글이 8px였다). 그런데 번호판을 더 모으자 **높이 63px(`200허11**`
→ `200011**`), 112px(`125호11**` → `125011**`)에서도 같은 자리가 틀렸다.** 확대·다중 프레임 합성·기울기
보정·대비·7프레임 투표 어느 것으로도 돌아오지 않았고, EasyOCR 범용 모델도 같았다.

즉 **입력을 다듬는 방향은 끝났고, 인식기 쪽에서 답을 찾아야 한다.** 이 조사는 「남들은 한국 번호판 한글을
어떻게 읽게 했나」를 확인해 다음 실험의 방향을 정하려는 것이다.

## 2. 질문

1. 연구·업계는 한글 자리를 어떻게 안정적으로 읽었나
2. 학습 없이 바로 평가할 수 있는 한국 번호판 인식기가 있나 — 라이선스는
3. PaddleOCR을 번호판에 미세조정한 선례와 효과는
4. 2줄 번호판(영업용 구형, 윗줄 지역명)은 어떻게 다뤘나

**제약.** 생성형 초해상도는 쓰지 않는다(없는 획을 만들어 낸다). readout은 값을 지어내지 않는다. CPU 노트북,
Feature Freeze(10/11)까지 2주.

## 3. 찾은 것

**검증 범위.** 출처 페이지는 조사 중 직접 열어 실재를 확인했다. 수치는 **원문이 적은 그대로**이고 조건을 같이
적는다. 어떤 방법도 재현하지 않았다. 본문을 열지 못한 것은 「미확인」으로 표시했다.

### ① 한글 자리를 읽게 한 방법

| 방법 | 출처 | 원문 수치 | 조건 |
| --- | --- | --- | --- |
| 번호판 전체를 CRNN(7 conv + LSTM) + CTC로 | Sensors 2021, 21(12):4140 | 인식 99.5% · end-to-end 98.94% | 합성 50만 + 실사 1.05만 장(128×64)으로 학습, KarPlate로 평가. 코드 비공개 |
| 글자를 나눈 뒤 한 글자씩 분류 (숫자 10 + 한글 40 + 지역명 17 = 67종) | 같은 논문 | end-to-end 98.9% | 글자 이미지 21.65만 장(32×32) |
| 합성 데이터만으로 학습 | 전자공학회논문지 2020, 57(1) | 번호판 85% · 글자 94% (후처리 후 88% · 96%) | 합성 150만, 실사 1,000장으로 시험 |
| 합성 데이터만으로 학습 (폰트 맞춤) | 방송공학회논문지 2020, 25(5) | 글자 79.06% | 합성 150만. 2006년 이전 지역명 번호판 제외 |
| PaddleOCR을 번호판에 미세조정 | PaddleOCR 공식 튜토리얼 (중국 CCPD) | 사전학습 0% → 후처리 90.97% → 미세조정 94.54% | 학습 5,769장, lr 0.0005. 0%는 「·」 한 글자를 더 내서였다 |
| 번호판 전용 STR | AI Hub 172 데이터셋 소개 | 번호판 OCR 99.75% | CRAFT + 4-stage STR. 부천 CCTV·주유소·주차장 — 블랙박스와 도메인이 다르다 |
| 범용 한국어 모델 + 정규식 필터 | CodeProject.AI 토론 #313 | 약 50% 실패 (작성자 서술) | 설정만으로는 부족하다는 반례 |

**읽는 법.**
- **99%대는 전부 번호판 전용 학습이다.** 범용 OCR의 설정만 바꿔 한글을 푼 사례는 찾지 못했다.
- **합성만으로는 79~88%에 그친다.** 「합성으로 사전학습 → 실데이터로 미세조정」이 사실상 표준이다.
- **PaddleOCR 미세조정은 선례가 있다**(0% → 94.54%). 다만 한국 번호판으로 한 수치는 찾지 못했다.
- KarPlate 원 논문(IEEE Access 2020, 9003211)은 존재만 확인했다 — 수치 미확인.

### ② 학습 없이 평가할 수 있는 모델

| 모델 | 무엇 | 라이선스 · 주의 |
| --- | --- | --- |
| **gyupro/EasyKoreanLpDetector** | EasyOCR 인식기를 AI Hub 172 약 8만 장으로 재학습(README 서술). 원 저자도 구형 번호판에 약하다고 적었다 | **명시 없음** → 평가만. **로컬에 이미 있어 §4에서 실측했다** |
| noahzhy/KR_LPR_Jax (tinyLPR, 86KB) | `서울12가1234`까지 출력. 99.12% — 시험셋 불명 | **GPL-3.0** — 제품에 넣으면 소스 공개 의무 |
| NinV/Korean-License-Plate-Recognition (LPRNet) | 가중치 제공, 수치 없음 | 가중치가 **KarPlate(학술·비상업 전용)**로 학습됨 |
| GilhanPark/Korean_license_plate_recognition (YOLOv4 + LPRNet) | 68종, 가중치 제공 | 코드 MIT, 가중치는 KarPlate 기반(비상업) |
| kwon-evan/LPRNet (STN + LPRNet) | 번호판당 약 5ms | Apache-2.0. 학습 데이터 불명 |
| qjadud1994/Korean-license-plate-Generator | 합성 번호판 생성기 — 황색·녹색, 2줄 지역명 지원 | MIT |

**제품에 바로 넣을 수 있는 것은 없다.** 전부 GPL이거나, 비상업 데이터로 학습됐거나, 라이선스가 없다.

### ③ 2줄 번호판

규칙 기반이었다 — 번호판 안 글자 수로 1줄/2줄을 판별해 분할 비율을 바꾸고(Sensors 2021), 윗줄 지역명은
**17개 중 하나를 고르는 닫힌 분류**로 처리한다. 우리 실험에서 위·아래를 나눠 읽는 것만으로는 윗줄이 안
읽혔으므로(실험 §3-②), 분할 뒤 **지역명 전용 분류**가 빠진 조각이다.

### ④ 찾지 못한 것

경찰 단속카메라·주차관제 업체, 네이버·카카오 기술블로그에서 한글 인식 방법을 공개한 자료. 한국 번호판으로
PaddleOCR을 미세조정한 수치.

## 4. 우리 데이터로 확인한 것

조사의 핵심 주장(「한글은 전용 학습으로 풀린다」)을 가장 싸게 확인하려고, 로컬에 있던 EasyKoreanLpDetector
인식기를 같은 13개 정답에 돌렸다. 전체 표는 실험 §3-⑤.

| 규칙 | 맞게 읽음 (13 중) | 틀린 값 확정 (27 중) |
| --- | ---: | ---: |
| PaddleOCR (현재) | 4 | 0 |
| 전용 인식기 1장 | **7** | **9** |
| **전용 인식기, 1장 = 7프레임 투표일 때만** | **5** | **0** |

- **주장은 맞았다.** PaddleOCR이 숫자로 바꾸던 `36수` · `200허` · `125호`를 한글까지 맞게 읽었다.
- **조사가 말하지 않은 것이 나왔다 — 전용 모델은 지어낸다.** 사람이 「안 보임」으로 적은 번호판에도 형식에 맞는
  번호를 냈고, 확신도 0.995짜리 오답도 있었다. 무엇을 보든 번호판 모양의 답을 내도록 학습됐기 때문이다.
- **프레임 간 일치가 그것을 거른다.** 지어낸 번호는 프레임마다 다르게 지어내므로, 여러 프레임이 같은 답을 낼
  때만 확정하면 틀린 확정이 0이 된다.

## 5. 결론

1. **한글 자리는 번호판 전용 학습으로 푼다.** 전처리·범용 모델·설정 조정으로는 안 된다 — 조사와 실측이 같은
   곳을 가리킨다.
2. **전용 모델에는 프레임 간 일치 조건이 필수다.** 범용 모델에서는 번호판 형식 검사가 안전장치였지만(27항목
   오답 확정 0), 전용 모델은 형식을 늘 맞추므로 **형식 검사가 안전장치가 되지 못한다.**
3. **바로 가져다 쓸 수 있는 모델은 없다**(라이선스). 가장 현실적인 경로는 **PaddleOCR 미세조정** — 공개된
   `korean_PP-OCRv5_mobile_rec` 사전학습 가중치에서 시작하고 선례(CCPD 5,769장 → 94.54%)가 있다.

## 6. 하고 싶은 말 — 원칙과 주의

- **형식 검사는 판독을 보류하는 데만 쓴다.** 「허」를 「0」으로 읽는 모델에게 한글 중 하나를 억지로 고르게
  하면(정규식 강제·자리 마스킹) 그것이 곧 값을 지어내는 것이다. 한글 자리 후보를 보여 주더라도 확정값이
  아니라 「사용자 확인용 후보」여야 한다.
- **「더 많이 맞힌다」보다 「틀린 것을 확정하지 않는다」가 먼저다.** 전용 모델 1장은 가장 많이 맞혔지만(7개)
  오답 확정도 가장 많았다(9개). 신고 자료에서 틀린 번호판은 다른 사람을 신고하는 일이다.
- **AI Hub 172는 내국인만 신청할 수 있고, 상업적 이용 조건은 확인하지 못했다.** 미세조정 데이터로 쓰기 전에
  약관을 확인해야 한다.
- **AI Hub의 99.75%는 CCTV·주차장 도메인이다.** 블랙박스(움직임·각도·거리)로 옮기면 떨어진다 — 평가는 반드시
  AI Hub와 겹치지 않는 실제 블랙박스 crop으로 한다.

## 7. 다음 — 권장 순서

| 순서 | 할 일 | 비용 | 이유 |
| --- | --- | --- | --- |
| 1 | 번호판 형식 검사를 제품 판독 경로에 넣는다 | 작음 | 지금 인식기(PaddleOCR)에서 오답 확정 0의 근거가 두 번 나왔다 |
| 2 | 추적 검증 — 추적한 프레임마다 번호판을 다시 검출 | 작음 | 프레임 간 일치 조건의 전제다. 지금은 추적이 튀면 일치가 깨진다(실험 §3-④) |
| 3 | PaddleOCR CTC 확률 들여다보기 — 한글 자리에 한글 확률이 조금이라도 실리나 | 0.5일 | 0에 가깝다면 디코딩 조정으로는 안 되고 미세조정만 남는다는 것을 확정한다 |
| 4 | PaddleOCR 미세조정 (AI Hub 172 일부 + 합성 생성기로 드문 기호·2줄 보충) | 1주 · **CPU 학습 시간 미확인** | 결론 3. **파인튜닝 게이트** — 대상 차량 association 안정이 아직 남았다 |
| 5 | 2줄 윗줄 지역명 17종 닫힌 분류 | 2일 | §3-③의 빠진 조각 |

## 출처

- Sensors 2021 — https://pmc.ncbi.nlm.nih.gov/articles/PMC8233874/
- 전자공학회논문지 2020 — https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002552953
- 방송공학회논문지 2020 — https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn=JAKO202029757728565&dbt=NART
- PaddleOCR 번호판 튜토리얼(CCPD) — https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.7/applications/%E8%BD%BB%E9%87%8F%E7%BA%A7%E8%BD%A6%E7%89%8C%E8%AF%86%E5%88%AB.md
- PaddleOCR 인식 모듈(사전학습 가중치) — http://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html
- `korean_PP-OCRv5_mobile_rec` — https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec
- PaddleOCR 토론 #14367 — https://github.com/PaddlePaddle/PaddleOCR/discussions/14367
- CodeProject.AI 토론 #313 — https://github.com/codeproject/CodeProject.AI-Server/discussions/313
- AI Hub 172 — https://www.aihub.or.kr/aihubdata/data/view.do?dataSetSn=172
- KR_LPR_Jax — https://github.com/noahzhy/KR_LPR_Jax
- EasyKoreanLpDetector — https://github.com/gyupro/EasyKoreanLpDetector
- NinV LPR — https://github.com/NinV/Korean-License-Plate-Recognition
- GilhanPark LPR — https://github.com/GilhanPark/Korean_license_plate_recognition
- kwon-evan LPRNet — https://github.com/kwon-evan/LPRNet
- 번호판 생성기 — https://github.com/qjadud1994/Korean-license-plate-Generator
- KarPlate(비상업, 현재 다운로드 불가) — https://oi.readthedocs.io/en/latest/computer_vision/alpr/dataset/kr_dataset.html
- KarPlate 원 논문(본문 미확인) — https://ieeexplore.ieee.org/document/9003211/
