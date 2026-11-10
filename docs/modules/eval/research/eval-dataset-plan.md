# 평가 데이터셋 3-tier 구성 계획 — 원문과 현행 대조

> **이 문서가 하는 일.** 평가 데이터셋을 A/B/C 3-tier로 나눈 계획 **원문을 보존**하고, 이후 실제로 만들어진 것과 §8에서 대조한다.
> **결정 문서가 아니다.** 현행 manifest·정답지의 authoritative source는 `eval/manifests/`다.
> **Owner:** 김대원(`eval`) · 대조 갱신 2026-09-12
> **대상 지표:** `eval_metrics_revision_v1.md` §6-2 주지표 13개

---

## 1. 원문 — 왜 3-tier인가

지표 13개를 **하나의 데이터셋으로 다 잴 수 없다.** 소스마다 살아남는 정보가 다르기 때문이다.

| 잃는 정보 | 어디서 잃는가 |
| --- | --- |
| 메타데이터 (creation_time, GPS) | 유튜브 업로드 시 재인코딩으로 소실 |
| 번호판 원본 | 업로드 영상 상당수가 모자이크·블러 처리 |
| 실서비스 유형 분포 | AI-Hub는 위반만 모아둔 데이터라 정상 주행 비율이 없음 |

| Tier | 소스 | 담당 지표 | 원문 기준 확보 상태 |
| --- | --- | --- | --- |
| **A. 이미지** | AI-Hub 71555 | `recall_macro` · `precision_macro` · `confusion_matrix` · `target_correct` | 확보 완료 |
| **B. 영상** | 유튜브 1시간 영상 → 1분 클립 | `recall@1` · `recall@3` · `timestamp_error` · `fp_per_clip` · `final_event_recall@3` · `cost_per_clip` · `latency_per_clip` | **이 문서의 범위** |
| **C. 원본** | 팀원 SD카드 실제 블랙박스 | `time_accuracy` · `unknown_rate` · `exact_plate_accuracy` · `wrong_accept_rate` · `abstention_recall` | 정철원 실측 대기 |

**C는 대체 불가능하다.** 메타데이터와 모자이크 없는 번호판은 원본에만 있다. 다만 **양은 적어도 된다** — 시각·번호판 지표는 수십 클립이면 신뢰구간이 잡히고, 대량이 필요한 건 `fp_per_clip`(B의 몫)이다.

**A tier는 다른 모듈을 기다리지 않고 지금 돌릴 수 있는 유일한 tier다.** B·C가 늦어져도 A로 분류 성능은 계속 측정한다.

## 2. 원문 — B tier 소스 선정 기준

### 2-1. 왜 「사고 모음」 영상을 쓰면 안 되는가

블랙박스 사고 모음 채널은 위반 밀도가 비정상적으로 높다. 실서비스는 수십 클립 중 1건 있을까 말까인데 편집된 모음집은 몇 클립에 1건씩 나온다. **`fp_per_clip`이 실제보다 좋게 나온다** — 오탐을 셀 정상 클립 자체가 부족하기 때문이다.

또한 편집 영상에는 컷 전환·자막·슬로우모션·반복 재생이 섞인다. 1분으로 자르면 한 클립 안에 서로 다른 장면이 들어가 입력 형태가 실서비스와 달라진다.

### 2-2. 선정 조건

```
[필수]
· 무편집 연속 주행 영상 (Long drive / POV driving / 4K drive 계열)
· 컷 전환·자막·BGM·슬로우모션 없음
· 최소 720p, 프레임 드롭 없음
· 대시캠 시점 (차량 내부 전방)
· 국내 도로 우선 — 신호체계·중앙선·차선 규칙이 다르면 라벨 기준이 흔들린다

[제외]
· 사고·위반 모음집
· 리액션·해설이 얹힌 영상
· 화면 분할, PIP, 지도 오버레이가 큰 영상
· 야간·악천후만 모아둔 영상 (조건 편향)
```

### 2-3. 조건 다양성

한 채널·한 시간대에서만 모으면 조건이 편향된다. 최소한 주간/야간, 맑음/우천, 도심/교외·고속을 섞는다.

> AI-Hub 71555의 `condition`(weather / daynight / roadType) 필드와 같은 축을 쓰면 A tier와 조건별 성능을 교차 비교할 수 있다.

## 3. 원문 — 클립 분할 규칙

### 3-1. 1분, 겹침 없음, 연속

```
1시간 영상 → 60개 클립 (겹침 0초)
```

**겹치지 않는 이유:** 블랙박스는 실제로 연속 분할 저장한다. 사용자가 올리는 파일은 겹치지 않는다. 평가셋만 겹치게 만들면 평가 입력과 실서비스 입력의 형태가 달라진다.

| 지표 | 겹칠 때 |
| --- | --- |
| `recall@1` / `@3` | 같은 사건이 두 클립에 걸쳐 한쪽만 찾아도 다른 쪽이 miss로 계산됨 |
| `fp_per_clip` | 표본이 독립이 아니라 오탐 1건이 두 번 세어짐. 클립 수는 늘어도 신뢰구간은 안 좁아짐 |
| `timestamp_error` | 같은 사건의 onset이 클립마다 달라져 정답 정의가 또 필요해짐 |
| `cost_per_clip` | 같은 영상량에 클립이 늘어 원가가 부풀려짐 |

**경계에 걸린 사건은 버리지 않는다.** 실서비스에서 실제로 일어나는 현상이므로 제거할 잡음이 아니라 측정할 대상이다. 라벨로 분리해 처리한다(§4).

### 3-2. 분할 누수 방지

```
group_key = source_video_id
```

같은 1시간 영상에서 나온 60개 클립은 **전부 같은 split에 들어간다.** dev와 locked에 쪼개져 들어가면 같은 도로·같은 차량·같은 조명이 양쪽에 섞여 locked test의 의미가 사라진다.

### 3-3. 클립 메타 (자동 생성)

| 필드 | 내용 |
| --- | --- |
| `clip_id` | 고유 ID |
| `source_video_id` | 원본 영상 ID — **split의 group_key** |
| `clip_index` | 원본 내 순번 (0~59) |
| `start_offset` | 원본 기준 시작 시각 (초) |
| `source_url` | 출처 URL |
| `license` | 라이선스 표기 |
| `condition` | 주야 / 날씨 / 도로유형 |

## 4. 원문 — 라벨링 기준

### 4-2. 경계 사건 — 왜 별도 분류가 필요한가

```
클립 07 [0초 ─────────────── 60초]  클립 08 [0초 ─────
                        ▲빨간불              ▲정지선통과
                        (58초)               (2초)
```

- **클립 07** — 빨간불만 있고 **선을 넘는 장면이 없다.** 이 클립만 보면 위반이 아니다. 모델이 「위반 없음」이라 하면 **맞은 것**인데, 분류 없이 두면 miss로 계산돼 recall이 부당하게 낮아진다.
- **클립 08** — 선을 넘는 장면은 있는데 **빨간불이었는지 안 보인다.** 모델이 「신호위반」이라 하면 **근거 없이 추측한 것**이다. 정확도상으로는 정답처럼 보이지만 실제로는 위험한 행동이다.

즉 두 케이스는 **정답/오답으로 셀 수 없어서** 따로 빼둬야 한다.

### 4-3. 라벨링 범위

「위반 있는 것만 라벨링」으로 진행하되 **전체 클립을 보고 나서 위반 있는 것에 표시를 남기는 방식**이어야 한다. 빠르게 훑어 눈에 띄는 것만 잡으면 `fp_per_clip`의 분모가 무너진다.

## 5. 원문 — 제작 절차

```
① 소스 선정        §2 기준으로 영상 목록 확정, 라이선스 근거 기록
        ↓
② 다운로드         yt-dlp — 원본 화질 유지
        ↓
③ 분할             ffmpeg segment — 60초, 겹침 없음, 재인코딩 최소화
                   (키프레임 정렬 여부 확인 — 잘못 자르면 첫 프레임이 깨진다)
        ↓
④ 메타 생성        §3-3 필드 자동 생성 → manifest
        ↓
⑤ 라벨링           ④ 이전에 라벨링 규칙서 고정 필수 (§4)
        ↓
⑥ split            group_key = source_video_id 로 dev / locked 분리
        ↓
⑦ 잠금             locked는 별도 경로에 격리. 여는 조건·주체를 기록
```

**③ 주의:** ffmpeg의 `-c copy` segment는 키프레임 단위로만 자른다. 정확히 60초로 안 잘릴 수 있으므로 `start_offset`은 **의도한 값이 아니라 실제 잘린 값**을 기록해야 `timestamp_error` 계산이 어긋나지 않는다.

## 7. 원문 — 요약

```
A. 이미지 (AI-Hub 71555)  → 분류 4종 지표      지금 실행 가능
B. 영상   (유튜브 1분 클립) → 탐색·오탐·비용 7종  이 문서의 계획
C. 원본   (SD카드)         → 번호판·시각 5종     실측 대기

B tier 핵심 규칙
  · 무편집 연속 주행 영상만 사용 (사고 모음집 금지)
  · 1분, 겹침 없음, 연속 분할
  · group_key = source_video_id
  · 경계 사건은 버리지 않고 라벨로 분리
  · 라벨링 규칙서를 고정한 뒤 착수
```

---

## 8. 현행 대조 (2026-09-12)

### 8-1. Tier별 현재 상태

| Tier | 원문 | 현재 |
| --- | --- | --- |
| A | 확보 완료 | **구현됨** — 종별 층화 표본 120 시퀀스(종당 30, seed `20260906`), 정답지 `g1`, 채점기 `eval/scorers/classification.py`. 상세는 `aihub-71555-survey.md` §7 |
| B | 계획 | **부분 구현** — 클립 55개(`clips.json`, 규칙 `c1`), 사건 5건(`events.json`), 정답지 `g1` 55항목. 아래 8-2 |
| C | 실측 대기 | **변동 없음** — `eval/scorers/plate.py`가 전 지표 `null` + `NO_C_TIER_DATA`를 반환한다 |

### 8-2. B tier — 실제로 만들어진 것

- **클립 55개**, 전부 `source_video_id: YT_0001` 한 편에서 나왔고 `split`은 전부 `DEV`다.
- **사건 5건** — `SIGNAL` 2 · `SOLID_LINE_LANE_CHANGE` 3. 밀도는 **클립 11개당 1건**으로, 계획 당시 예상한 「600클립에 10건 이하」보다 높다. 다만 source video가 1편이라 조건 다양성(§2-3)과 group 분리(§3-2)는 **아직 검증되지 않았다** — 그룹이 하나뿐이라 누수가 생길 수 없는 상태일 뿐이다.
- **`review_status` 문제의식은 해결됐다.** 필드 이름으로는 안 들어갔고, 정답지 `meta.coverage`에 `clips_reviewed: 55` · `negatives_confirmed: true`로 들어갔다. 55개 전부 사람이 보고 확인했다는 뜻이라 `fp_per_clip`의 분모가 성립한다.
- **경계 사건은 §4-2의 ② 「별도 분류」로 결정됐다.** 정답지 target에 `scoring` 필드가 있고 현재 `INCLUDED` 4건 · `BOUNDARY_EXCLUDED` 1건이다. 채점기는 `BOUNDARY_EXCLUDED`를 분모에서 빼고 그 사실을 `coverage`에 적는다. 원문의 `completeness`라는 이름은 채택되지 않았다.
- **사건 라벨 필드**는 `events.json`에 `t_onset_sec`·`t_start_sec`·`t_end_sec`·`target_vehicle`·`plate_status`·`plate_text`·`plate_partial_text`·`plate_vehicle_type`·`label_status`·`labeler`·`labeled_at`·`evidence_note`로 확정됐다. 5건 모두 `label_status: CONFIRMED`, `labeler: daewon`.

### 8-3. 지표 이름이 바뀐 것

| 원문 | 현행 |
| --- | --- |
| `recall@1` · `recall@3` | `recall_at` (K = 1, 3, 10) |
| `timestamp_error` (candidate 단계) | **2026-09-10 계약 정정** — coarse localization은 `\|representative_ms − gt_onset_ms\|` point error이고 span IoU는 1차 매처에서 폐기됐다(`contract-analysis-run-candidate-event.md` Consumer—`eval`) |
| `cost_per_clip` | `cost_per_source_video_hour` — 분모는 **중복 제거한 사건 timeline 길이**다(전후방 2개 소스를 합산하지 않는다). 비용 집계 정본 키는 `UsageRecord.case_id`(`usage-record/v1.2`) |
| `target_correct` | `target_correctness` (A tier) |

### 8-5. 그대로 유효한 것

무편집 연속 주행 영상만 사용 · 1분 겹침 없는 분할 · `group_key = source_video_id` · 경계 사건 보존 · C tier 대체 불가 · A tier를 다른 모듈과 무관하게 먼저 돌린다 — 전부 현행 구조가 따르고 있다.

## 10. 관련 문서

- `docs/modules/eval/research/aihub-71555-survey.md` — A tier 소스 사전조사
- `docs/modules/eval/research/ground-truth-schema.md` — A tier 정답지 스키마
- `docs/modules/eval/research/blackbox-storage-survey.md` — 1분 분할 규칙의 근거(제조사 저장 방식)
- `docs/modules/eval/harness-v1-design.md` — tier별 지표 개폐와 결측 처리
- `eval/manifests/b_youtube/` · `eval/datasets/README.md` — 현행 B tier manifest와 재현 방법
