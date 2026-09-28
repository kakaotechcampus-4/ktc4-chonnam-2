# Search 실행 경로 지연 baseline (2026-09-28)

작성: 서어진 (`search`) · 요청: #72

> #72 timeout 결정에 쓸 **현재 제품 경로** 지연 실측이다. 9/12 탐침(`coarse-fine-probe-summary-2026-09-12.md`)은 Gemini 직접 호출·Files API·`gemini-3.7-flash` 조건이라 #95 이후 경로와 다르다.
> 이 문서는 숫자와 그 한계만 적는다. timeout 값은 `case` 소유다(`docs/modules/case/decisions/timeout-fallback.md`).

## 1. 결론 먼저

- **Coarse는 영상 길이에 비례하고, 대부분이 provider가 아니라 로컬 ffmpeg 전처리다.** 5분 클립에서 호출 바깥 시간(wall) 중앙값 47.6초 중 provider 응답은 13.8초, 나머지 약 32초가 원본 복사·360p/1fps 재인코딩이다.
- **Fine은 영상 길이와 무관하다.** 전체 29회 wall 중앙값 8.5초, p95 15.5초, 최대 33.4초(provider 응답 26.1초짜리 1회).
- **5분 클립은 인라인 상한에 가깝다.** 40분 원본을 5분씩 나눈 8개 중 최대 11.1 MB (상한 12 MiB의 88%). 구간에 따라 상한까지 5.7~8.2분이다(§3-2).
- **동시 발주해도 provider는 느려지지 않았고 429도 없었다. 병목은 로컬 ffmpeg다.** 8개 동시 실행 시 batch 전체는 순차 대비 1.3배 빨라졌을 뿐이고, 클립 하나의 wall은 59초 → 341초로 늘었다(§3-1).
- **`InvalidCoarseSpanError`가 Coarse 44회 중 10회(23%)** 났다. 같은 클립이 어떤 회차에선 성공하고 어떤 회차에선 실패해서 영상 내용보다 응답 편차로 보인다. 후보를 하나도 돌려주지 않는다(§5, #181).
- 재시도 최악 시간은 코드로 계산했다. 429·5xx에서만 최대 3번 재시도하며 대기 합계 35초, 전체는 `max_latency_sec`를 넘지 않는다(§6-1).

## 2. 조건

| 항목 | 값 |
| --- | --- |
| 경로 | `build_gemini_search_service()` — Case 실영상 E2E와 같은 경로 (Elice 프록시, OpenAI 호환 API, base64 인라인) |
| 코드 | `experiment/search-latency-baseline-72` (#180 `4b6e340` 위, 스크립트 (A) `dbe8dcd` · (B) `bdc52e9`) — #180은 실행 상한만 바꾸고 호출 경로는 develop과 같다 |
| 모델 | `gemini-3.8-flash`, `reasoning_effort=low` |
| 전처리 | Coarse 1fps·360p·무음 재인코딩 / Fine 2fps·720p·무음, 후보 span ± 4초 |
| 재시도 | `max_retries=3`, `retry_base_sec=5.0` |
| 실행 상한 | `max_latency_sec=600` (측정이 잘리지 않도록 넉넉히) |
| 입력 | 강변북로 원본(1080p·29.97fps·H.264, 약 4.1 Mbps)의 10:00 지점부터 `-c copy`로 자른 20초 / 1분 / 2분 / 5분 클립 |
| 규모 | (A) 5회 반복 × 4개 길이 Coarse, 후보 rank 상위 3개 Fine. 회차 안에서 길이를 번갈아 실행<br>(B) 동시성: 40분 원본을 0초부터 5분씩 나눈 8개 클립(마지막 247.9초)을 동시성 1·4·8로 Coarse만 각 1회 |
| 실행 환경 | 로컬 Windows 11, CPU 4코어, ffmpeg 9.0.1 |
| 실행 시각 | (A) 2026-09-28 04:42~ UTC (B) 같은 날 (A) 직후 |

원장: `latency-baseline-2026-09-28/run.jsonl` (A), `concurrency.jsonl` (B), `dry-run.jsonl` (20초 1회 사전 확인). 한 줄 = 호출 하나.
- `latency_ms`: provider 호출 1회(마지막으로 성공한 시도)의 시간 — ledger 값
- `wall_ms`: 호출 바깥에서 잰 시간 — 원본 복사·ffprobe·ffmpeg·재시도·backoff 포함

## 3. Coarse

| 클립 | 성공/시도 | wall p50 | wall p95 | wall 최대 | provider p50 | provider 최대 | 전처리 등 p50 | 전처리 결과 최대 | 입력 토큰 p50 | 후보 수 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20초 | 5/5 | 7.7초 | 8.2초 | 8.3초 | 4.5초 | 4.7초 | 3.1초 | 0.57 MB | 1,742 | 1~2 |
| 1분 | 5/5 | 15.8초 | 19.5초 | 20.2초 | 6.4초 | 8.8초 | 8.5초 | 1.53 MB | 4,382 | 1~2 |
| 2분 | 4/5 | 21.4초 | 25.6초 | 26.0초 | 8.8초 | 12.7초 | 12.5초 | 3.06 MB | 8,343 | 1~3 |
| 5분 | 4/5 | 47.6초 | 51.7초 | 52.3초 | 13.8초 | 20.8초 | 31.6초 | 9.29 MB | 20,223 | 1~3 |

(성공 행만 집계. p95는 표본 4~5개의 보간값이라 사실상 최대값에 가깝다.)

선형 근사(성공 18회):
- **wall ≈ 0.141 초/영상초 + 5.4초** → 5분 약 48초
- provider ≈ 0.035 초/영상초 + 4.2초 → 5분 약 15초

전처리 몫은 20초에서 provider의 0.7배, 1~2분에서 1.3~1.4배, 5분에서 2.3배로 길이에 따라 더 가파르게 는다. 이 몫은 **실행 머신의 CPU·디스크에 달려 있어** runtime 환경에서는 달라질 수 있다.

**같은 클립도 머신 부하에 따라 30% 흔들린다.** (A)의 5분 클립과 (B)의 `part_2`는 같은 구간(10:00~15:00)인데 wall이 47.6초(p50) vs 62.0초였다. provider는 9.3초로 오히려 빨랐고, 차이는 전처리다. 측정 중 같은 머신에서 다른 작업이 돌았을 수 있다.

### 3-1. 동시성 (B)

| 동시성 | 성공/시도 | 클립당 wall p50 | 클립당 wall 최대 | provider p50 | provider 최대 | 전처리 등 p50 | batch 전체 (8개) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7/8 | 59.3초 | 68.5초 | 13.9초 | 21.3초 | 45.2초 | 465초 |
| 4 | 4/8 | 203.0초 | 239.8초 | 11.4초 | 21.2초 | 191.6초 | 425초 (185 + 240) |
| 8 | 5/8 | 340.8초 | 351.3초 | 14.4초 | 32.2초 | 325.8초 | 351초 |

(wall·provider는 실패 행 포함 — 실패도 provider 응답까지는 받았다.)

- **provider 쪽 한계는 보이지 않았다.** 8개 동시에도 429·5xx 없이 응답했고 provider p50이 11~14초로 순차와 같다.
- **로컬 CPU가 한계다.** 한 프로세스 안에서 ffmpeg 8개가 4코어를 나눠 쓰니 클립 하나의 wall이 5.7배로 늘었다. batch 전체는 465초 → 351초로 1.3배 줄었을 뿐이다.
- 따라서 **"클립당 timeout"은 동시성과 독립이 아니다.** 같은 머신에서 동시에 돌리면 클립당 시간이 늘어난다. 동시성의 이득은 전처리가 다른 머신·코어로 나뉠 때만 난다.

### 3-2. 클립 최대 길이 (인라인 상한)

(B)의 5분 클립 8개의 전처리 결과는 7.7~11.1 MB, 영상 1초당 24.9~36.1 KiB였다. 인라인 상한 12 MiB까지 **5.7분(가장 복잡한 구간) ~ 8.2분**이다. 5분 단위면 이 원본에서는 들어가지만 여유는 12%까지 줄어든다. 더 복잡한 장면(도심·야간 노이즈)은 5분도 넘을 수 있다.

## 4. Fine

| 클립 | 호출 | wall p50 | wall p95 | wall 최대 | provider p50 | provider 최대 |
| --- | --- | --- | --- | --- | --- | --- |
| 20초 | 7 | 10.1초 | 13.9초 | 14.3초 | 4.7초 | 10.2초 |
| 1분 | 8 | 8.7초 | 25.4초 | 33.4초 | 5.7초 | 26.1초 |
| 2분 | 7 | 7.4초 | 14.9초 | 16.3초 | 4.4초 | 12.4초 |
| 5분 | 7 | 8.9초 | 10.7초 | 10.8초 | 4.9초 | 7.2초 |
| **전체** | **29** | **8.5초** | **15.5초** | **33.4초** | **4.9초** | **26.1초** |

- 결과는 29회 모두 `NOT_OBSERVED`. 정확도는 이 실험 범위가 아니다.
- 입력 토큰은 1,162~1,228로 거의 일정하다. 요청 구간이 후보 span ± 4초로 길이가 비슷하기 때문이다.
- 최대 33.4초는 provider 응답 자체가 26.1초였던 1회다(1분 클립 2회차 rank 1). 나머지 28회는 wall 16.3초 이하였다.
- Coarse 후보가 1~3개라 계획한 60회가 아니라 29회만 실행됐다.

## 5. 실패: `InvalidCoarseSpanError` 10/44

| 측정 | 발생 |
| --- | --- |
| (A) | 20회 중 2회 — 120초 4회차, 300초 2회차 |
| (B) 동시성 1 | 8회 중 1회 — `part_6` |
| (B) 동시성 4 | 8회 중 4회 — `part_1`·`part_5`·`part_6`·`part_7` |
| (B) 동시성 8 | 8회 중 3회 — `part_1`·`part_2`·`part_7` |

- 같은 클립이 회차마다 성공·실패가 갈린다(`part_2`는 동시성 1·4에서 성공, 8에서 실패). 동시성이 원인인지는 표본이 작아 말할 수 없다.
- provider 응답은 정상으로 받았고(ledger에 `latency_ms` 기록됨), 후보 span 검증에서 실패했다.
- 이 오류는 `AnalysisRun(FAILED)`로 기록되지 않고 **`search_candidates()`에서 예외로 올라간다.** 같은 응답의 다른 정상 후보도 함께 버려진다.
- 측정 스크립트는 오류 type만 남기고 span 값은 남기지 않아서, 클립 밖 시각이었는지 순서가 뒤집혔는지는 구분하지 못한다.
- timeout과 별개 문제라 여기서는 기록만 한다. 후속: #181.

## 6. 이 측정이 답하지 못하는 것

| 항목 | 이유 |
| --- | --- |
| 재시도 실측 | 동시성 8까지도 429·5xx가 나지 않아 재시도가 섞인 표본이 없다. 대신 §6-1에 코드 기준 최악값을 계산했다. |
| 동시성 9 이상 · 여러 프로세스 | 한 프로세스 안 thread 8개까지만 쟀다. Elice의 실제 rate limit 값은 모른다. |
| runtime 환경 | 전처리 몫은 로컬 4코어 기준이다. §3-1처럼 동시성에 따라 크게 변하므로 runtime 머신에서 다시 재야 한다. |
| 다른 영상 | 원본 1개(강변북로 주간 고속도로)에서 자른 구간이다. 야간·도심·저비트레이트 블랙박스 영상은 재지 않았다. |
| tail | 길이별 표본 4~5개, Fine 29개로는 p99를 말할 수 없다. |

### 6-1. 재시도 최악 시간 (코드 기준 계산)

`src/daesingo/search/retry.py` · `provider.py` · `config.py` 기준.

| 항목 | 값 |
| --- | --- |
| 재시도 대상 | HTTP 429, 5xx만. **timeout(`APITimeoutError`)·연결 오류(`APIConnectionError`)는 재시도 없이 바로 실패**한다(status code가 없어 transient로 분류되지 않음) |
| 시도 횟수 | 최대 4회 (`max_retries=3`). OpenAI SDK 자체 재시도는 꺼져 있다(`max_retries=0`) |
| 시도 사이 대기 | 5초 → 10초 → 20초, **합계 35초** (`retry_base_sec × 2^n`) |
| 시도별 timeout | 남은 run budget. 대기도 남은 budget으로 잘린다(#152) |
| 전체 상한 | `max_latency_sec`를 넘지 않는다(#180). 넘으면 `DeadlineExceededError` → Coarse는 `FAILED`(COST) |

**예시 (측정 p50에 대기 35초를 더한 값):** 429가 빠르게 3번 난 뒤 성공하면
- Fine: 8.5초 + 35초 ≈ **44초**
- Coarse 5분(순차): 47.6초 + 35초 ≈ **83초**

5xx가 느리게 오면(시도마다 응답 대기) 이보다 길어지지만, 어떤 경우든 `max_latency_sec`에서 끊긴다.

## 7. #72 공식에 넣을 때 참고

`case`가 제안한 공식(Coarse 전체 = 클립당 timeout × 클립 수 / 동시성, Fine = 실측 최대 × margin)에 대응되는 측정값만 적는다. 값 결정은 `case`가 한다.

| 공식의 빈칸 | 이번 측정 |
| --- | --- |
| Coarse 클립당 시간 | 순차 기준 5분 클립 wall 47.6~68.5초 (provider만 보면 9~21초). 길이 L초에 대해 wall ≈ 0.141·L + 5.4초 (A 기준) |
| 클립 수 | 인라인 상한 기준 클립 최대 5.7~8.2분(이 원본 기준) → 5분 단위면 40분 영상 8개 |
| 동시성 | Search 내부 동시성 없음 → Case가 Job을 몇 개 동시에 발주하느냐의 문제. **같은 머신이면 클립당 시간이 늘어난다**(동시성 8에서 341초). 공식의 "/ 동시성"은 전처리가 병렬로 나뉠 때만 성립 |
| Fine 후보당 | wall p50 8.5초 / p95 15.5초 / 최대 33.4초 |
| 재시도 | 429·5xx일 때 최대 +35초 대기. 전체는 `max_latency_sec` 안 |
| 전처리 몫 | Coarse 1분 이상에서 wall의 절반 이상(5분은 약 2/3). provider 지연만으로 timeout을 잡으면 모자란다 |

토큰 합계: (A) 입력 207,088 / 출력 20,132 (49회), (B) 입력 475,056 / 출력 11,457 (24회). 비용은 단가 설정이 비어 있어 ledger에 기록되지 않았다.

## 8. 재현

```bash
# 클립 준비 (doc/는 gitignore 대상 — 원본·클립은 커밋하지 않는다)
for d in 20 60 120 300; do
  ffmpeg -nostdin -v error -y -ss 600 -i doc/gangbyeon-40min-source.mp4 -t $d -c copy -an doc/latency/clip_$(printf %03d $d)s.mp4
done

uv run python examples/search_latency_baseline.py \
  --clip doc/latency/clip_020s.mp4 --clip doc/latency/clip_060s.mp4 \
  --clip doc/latency/clip_120s.mp4 --clip doc/latency/clip_300s.mp4 \
  --repeats 5 --fine-top-k 3 \
  --out docs/modules/search/experiments/latency-baseline-2026-09-28/run.jsonl

# (B) 동시성 — 40분 원본을 5분씩 8개로
for i in 0 1 2 3 4 5 6 7; do
  ffmpeg -nostdin -v error -y -ss $((i*300)) -i doc/gangbyeon-40min-source.mp4 -t 300 -c copy -an doc/latency/split/part_$i.mp4
done
for c in 1 4 8; do
  uv run python examples/search_latency_baseline.py $(for i in 0 1 2 3 4 5 6 7; do echo --clip doc/latency/split/part_$i.mp4; done)     --concurrency $c --out docs/modules/search/experiments/latency-baseline-2026-09-28/concurrency.jsonl
done
```

(B)는 5분 클립 8개를 동시에 전처리하므로 임시 파일로 약 1.3 GB가 필요하다.
