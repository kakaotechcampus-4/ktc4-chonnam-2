# [readout] 한국 번호판 인식 선행연구 조사 — 인용 검증 (2026-09-20)

> **성격: 검증 기록이다. 결정이 아니다.** 조사 자체는 Owner가 LLM 딥리서치로 수행했고
> 원본은 개인 메모에 있어 팀이 열 수 없다. 그래서 **팀에 필요한 내용만 자립적으로**
> 옮기고, 인용이 실재하는지·수치가 맞는지를 따로 확인해 적는다.
>
> 이 조사가 제안한 파이프라인·ablation과 「파인튜닝 보류」는 **결정 영역**이라 여기 싣지 않는다.
>
> 작성 신유민(`readout` Owner) · 검증일 2026-09-20

---

## 1. 왜 검증했나

LLM 딥리서치 결과는 **인용이 그럴듯하게 지어지는 경우가 있다.** 이 조사는 논문 6편을
근거로 파이프라인 방향과 파인튜닝 시점을 제안했고, 그 제안이 계약·실험 순서에 영향을
준다. **근거가 실재하지 않으면 제안도 무효**이므로 먼저 확인했다.

확인 방법은 세 가지다 — 원문 직접 열람 · Crossref API(DOI 조회) · arXiv API(id 조회).

---

## 2. 인용 실재 확인 — 6편 전부 실재한다

| # | 논문 | 식별자 | 확인 방법 |
| --- | --- | --- | --- |
| 1 | A Comparative Study of OCR Architectures for Korean License Plate Recognition (Sensors, 2026) | `10.3390/s26041208` | **원문 직접 열람** |
| 2 | MF-LPR²: Multi-frame LP Image Restoration and Recognition using Optical Flow (CVIU, 2025) | `10.1016/j.cviu.2025.104361` · arXiv `2508.14797` | Crossref + arXiv |
| 3 | Eyes on the Target: Super-Resolution and LPR in Low-Quality Surveillance Videos (IEEE Access, 2017) | `10.1109/ACCESS.2017.2737418` | Crossref |
| 4 | Temporal Matching Prior Network for Vehicle LP Detection and Recognition in Videos (ETRI Journal, 2020) | `10.4218/etrij.2019-0245` | Crossref |
| 5 | Character Time-series Matching for Robust LPR (MAPR, 2022) | arXiv `2307.11336` | arXiv |
| 6 | End-to-End Trainable Network for Degraded LP Detection via Vehicle-Plate Relation Mining | arXiv `2010.14266` | arXiv |

1번은 서울과기대(Seungju Lee · Gooman Park) 2026-02-12 게재, 2번은 한국 연구진
(Kihyun Na 외 6인) CVIU Vol.256, 4번은 ETRI(Seok Bong Yoo · Mikyong Han)다.

> 조사가 「참고」로 든 *Robust Korean LPR Based on DNN*(PMC, 98.94%)은 **확인하지 않았다.**
> 합성 50만 장으로 학습한 결과라는 서술만 옮겨져 있고, 본 검증 범위 밖이다.

---

## 3. 수치 정정 3건 — 조사의 인용이 원문과 다르다

### ① MF-LPR² — 비교 기준선이 빠졌다

| | 조사가 적은 것 | 원문(초록) |
| --- | ---: | ---: |
| best single-frame | 16.18% | **14.04%** |
| **기존 multi-frame 최고** | **(누락)** | **82.55%** |
| MF-LPR² | 86.44% | 86.44% ✅ |

조사는 **14% → 86%**처럼 읽히게 썼지만, MF-LPR² 자신의 기여는 **82.55 → 86.44
(+3.9pt)**다. 나머지 68pt는 **「multi-frame이면 어떤 방법이든」**이 만든 것이다.

> **이 정정은 우리에게 유리한 쪽이다.** 특정 논문 구현을 재현할 필요가 없다는 뜻이다.
> single-frame 확정을 버리는 것만으로 대부분이 나온다.

데이터셋은 RLPR — **실제 dash cam** 저품질 시퀀스 200쌍이다(도메인 일치).
조사가 적은 「시퀀스당 31프레임」은 초록에 없어 **확인하지 못했다.**

### ② Sensors 2026 — 99.12% vs 24.18%는 ROI 품질 비교가 아니다

| | 조사가 적은 것 | 원문 |
| --- | --- | --- |
| CA 99.12% · CER 0.76% | "정적 AI-Hub crop" | `exp000` — **AI-HUB로 학습한** 모델 |
| CA 24.18% · CER 75.42% | "**같은 모델**이 추적 ROI에서 하락" | `exp002` — **UFPR-ALPR로 학습한** 모델 |

**서로 다른 학습 데이터 비교다.** 원문은 UFPR 저하를 "dataset-imposed performance
ceiling caused by extreme perspective distortion, small character sizes, and low
effective resolution"으로 귀속한다.

ROI 불안정성(jitter · drift · frozen region)이 지배적이라는 **논문의 주장 자체는 맞다** —
논문 기여 ①과 §4.7이 그것이다. **근거가 저 숫자 쌍이 아닐 뿐이다.**

### ③ 5프레임 시간 투표는 「선택적 후처리」다

§4.7에서 `N=5` character-position majority voting이 CA를 올리고 CER을 낮추는 것은
확인된다. 다만 원문은 이를 **optional post-processing**으로 규정하고, `(N-1)/2 = 2프레임`
지연이 발생한다고 명시한다. 「구조를 안 바꾸고 개선된다」는 서술은 맞지만 **공짜는 아니다.**

---

## 4. 조사가 놓친 것 — Sensors가 쓴 AI-Hub가 우리 데이터셋 ②다

원문 참고문헌 [26]이 `aihub.or.kr/.../view.do?dataSetSn=172`다.
**`datasets-inventory-2026-09-18.md` ②와 같은 데이터셋이다.**

| | 모델 | 같은 172 crop에서 |
| --- | --- | ---: |
| Sensors `exp000` | CNN + Attention-LSTM, **172로 학습** | CER **0.76%** |
| `ocr-baseline-2026-09-15` ② | `korean_PP-OCRv5_mobile_rec`, **pretrained 무보정** | CER **55.3%** |

조사는 우리 5.6%/55.3%를 놓고 「crop 확대·투시 보정·다중 프레임 정렬 없이 했으니 이
수치만으로 학습 필요성을 결론 낼 수 없다」고 썼다. **그런데 172의 번호판OCR crop은
중앙 256×123px 근접·정면 정적 이미지다** — 확대·투시보정을 적용할 여지가 거의 없고,
단일 이미지라 다중 프레임은 정의되지 않는다.

**즉 이 논거는 500장 실험에는 맞지 않는다.** 같은 데이터에서 학습 모델이 CER 0.76%를
내는 이상, 우리 55.3%는 전처리 부족보다 **pretrained가 한국 번호판을 학습하지 않았다는
것**에 더 가깝다.

> **다만 지표 축이 다르다.** 99.12%는 문자 단위 정확도(CA)이고 우리 5.6%는 번호판 전체
> 일치(Exact)다. 같은 축 비교는 CER 0.76% ↔ 55.3%다.

### 이것이 바꾸는 것

「파인튜닝을 지금 하지 않는다」는 결론은 **유지될 수 있다.** 다만 이유가 달라진다.

| | 조사의 논거 | 검증 후 |
| --- | --- | --- |
| 왜 지금 안 하나 | recognition 수치가 전처리 부족 탓이라 판단 불가 | **순서 문제다.** association이 57.7%인데 recognition을 고쳐도 그 위로 못 올라간다 |
| recognition은? | 전처리·합의로 해결 가능 시사 | **결국 학습이 필요할 수 있다.** 지금은 우선순위가 뒤일 뿐이다 |

이 구분이 없으면 ablation을 다 돌린 뒤 「recognition이 여전히 안 된다」에서 놀라게 된다.

---

## 5. 새로 제기되는 것 — PaddleOCR 수치가 레포 안에서 충돌한다

| 출처 | 표본 | 모델 | Exact | CER |
| --- | ---: | --- | ---: | ---: |
| `architecture-input-memo.md` §Recognition-only sanity | 15장 | `korean_PP-OCRv5_mobile_rec` | **53.3%** | **16.2%** |
| `ocr-baseline-2026-09-15` ② | 500장 | 같은 모델 | **5.6%** | **55.3%** |

**같은 모델, 같은 성격의 crop인데 결과가 반대다.** 그리고 53.3% 쪽은
`architecture-input-memo.md`에서 **`consensus`/`abstain` 계약 필수의 근거**로 쓰이고 있다.

15장 실험의 **이미지 출처·정규화 규칙·촬영 조건이 어디에도 기록돼 있지 않다.**
500장 쪽은 정규화가 `evaluate_500.py`의 `norm()`으로 고정돼 있다.

§4의 Sensors 비교를 기준으로 보면 **500장 쪽이 pretrained의 실제 실력에 가깝다.**

> **미결로 남긴다.** 15장 조건을 복원해 재측정하거나, 못 하면 53.3%를 근거 목록에서
> 내려야 한다. **지금 값으로 채우지 않는다.**

---

## 6. 검증 범위 밖

- **논문 본문 전체 검증이 아니다.** 1번만 원문을 열어 §4.7·Table 4 서술을 확인했고,
  나머지는 **실재와 서지정보만** 확인했다. 3·4·5·6번의 보고 수치는 검증하지 않았다
- **재현하지 않았다.** 어떤 논문의 방법도 우리 데이터로 돌려보지 않았다
- **파인튜닝 여부를 여기서 정하지 않는다**
