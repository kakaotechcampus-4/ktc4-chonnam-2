# Search 실행 경로 지연 baseline (2026-09-28)

작성: 서어진 (`search`) · 요청: #72

> #72 timeout 결정에 쓸 **현재 제품 경로** 지연 실측이다. 9/12 탐침(`coarse-fine-probe-summary-2026-09-12.md`)은 Gemini 직접 호출·Files API·`gemini-3.7-flash` 조건이라 #95 이후 경로와 다르다.
> 이 문서는 숫자와 그 한계만 적는다. timeout 값은 `case` 소유다(`docs/modules/case/decisions/timeout-fallback.md`).

## 1. 결론 먼저

- **Coarse는 영상 길이에 비례하고, 대부분이 provider가 아니라 로컬 ffmpeg 전처리다.** 5분 클립에서 호출 바깥 시간(wall) 중앙값 47.6초 중 provider 응답은 13.8초, 나머지 약 32초가 원본 복사·360p/1fps 재인코딩이다.
- **Fine은 영상 길이와 무관하다.** 전체 29회 wall 중앙값 8.5초, p95 15.5초, 최대 33.4초(provider 응답 26.1초짜리 1회).
- **5분 클립은 인라인 상한 안에 들어간다.** 전처리 결과 최대 9.3 MB (상한 12 MiB의 약 74%).
- **Coarse 20회 중 2회(120초·300초 각 1회)가 `InvalidCoarseSpanError`로 run 전체가 예외로 끝났다.** 후보를 하나도 돌려주지 않았다. 9/12의 `SPAN_OUT_OF_CLIP`과 같은 계열로 보인다(아래 §5).
- 재시도가 실제로 일어났는지는 **이 측정으로 판별할 수 없다**(§6).

## 2. 조건

| 항목 | 값 |
| --- | --- |
| 경로 | `build_gemini_search_service()` — Case 실영상 E2E와 같은 경로 (Elice 프록시, OpenAI 호환 API, base64 인라인) |
| 코드 | `experiment/search-latency-baseline-72` (#180 `4b6e340` 위, 스크립트 `dbe8dcd`) — #180은 실행 상한만 바꾸고 호출 경로는 develop과 같다 |
| 모델 | `gemini-3.8-flash`, `reasoning_effort=low` |
| 전처리 | Coarse 1fps·360p·무음 재인코딩 / Fine 2fps·720p·무음, 후보 span ± 4초 |
| 재시도 | `max_retries=3`, `retry_base_sec=5.0` |
| 실행 상한 | `max_latency_sec=600` (측정이 잘리지 않도록 넉넉히) |
| 입력 | 강변북로 원본(1080p·29.97fps·H.264, 약 4.1 Mbps)의 10:00 지점부터 `-c copy`로 자른 20초 / 1분 / 2분 / 5분 클립 |
| 규모 | 5회 반복 × 4개 길이 Coarse, 후보 rank 상위 3개 Fine. 회차 안에서 길이를 번갈아 실행 |
| 실행 환경 | 로컬 Windows 11, CPU 4코어, ffmpeg 9.0.1 |
| 실행 시각 | 2026-09-28 04:42~ UTC, 순차 실행(동시성 1) |

원장: `latency-baseline-2026-09-28/run.jsonl` (본 측정), `dry-run.jsonl` (20초 1회 사전 확인). 한 줄 = 호출 하나.
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

**클립 최대 길이:** 전처리 결과가 이 원본에서 약 31 KB/영상초였다. 인라인 상한 12 MiB 기준 약 6.8분이다. 장면 복잡도에 따라 달라지므로 5분은 여유가 있고 10분은 넘을 가능성이 높다(10분은 재지 않음).

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

## 5. 실패: `InvalidCoarseSpanError` 2/20

- 120초 4회차, 300초 2회차. provider 응답은 정상으로 받았고(ledger에 `latency_ms` 기록됨), 후보 span 검증에서 실패했다.
- 이 오류는 `AnalysisRun(FAILED)`로 기록되지 않고 **`search_candidates()`에서 예외로 올라간다.** 같은 응답의 다른 정상 후보도 함께 버려진다.
- 측정 스크립트는 오류 type만 남기고 span 값은 남기지 않아서, 클립 밖 시각이었는지 순서가 뒤집혔는지는 구분하지 못한다.
- timeout과 별개 문제라 여기서는 기록만 한다. 후속은 search 이슈로 따로 연다.

## 6. 이 측정이 답하지 못하는 것

| 항목 | 이유 |
| --- | --- |
| 재시도 포함 시간 | 스크립트가 시도 횟수를 기록하지 않았다. `wall − latency` 최대값(Fine 8.7초)은 backoff 5초 1회와 ffmpeg 편차 둘 다로 설명된다. 429/5xx를 일부러 만들지 않는 한 순차 실행에서는 드물다. |
| 동시성 | 순차 실행만 했다. Case가 클립별 Job을 동시에 발주할 때의 429 여부는 재지 않았다. |
| runtime 환경 | 전처리 몫은 로컬 4코어 기준이다. |
| 다른 영상 | 원본 1개(강변북로 주간 고속도로)에서 자른 구간이다. 야간·도심·저비트레이트 블랙박스 영상은 재지 않았다. |
| tail | 길이별 표본 4~5개, Fine 29개로는 p99를 말할 수 없다. |

## 7. #72 공식에 넣을 때 참고

`case`가 제안한 공식(Coarse 전체 = 클립당 timeout × 클립 수 / 동시성, Fine = 실측 최대 × margin)에 대응되는 측정값만 적는다. 값 결정은 `case`가 한다.

| 공식의 빈칸 | 이번 측정 |
| --- | --- |
| Coarse 클립당 시간 | 5분 클립 wall 최대 52.3초 (provider만 보면 20.8초). 길이 L초에 대해 wall ≈ 0.141·L + 5.4초 |
| 클립 수 | 인라인 상한 기준 클립 최대 약 6.8분(이 원본 기준) → 5분 단위면 40분 영상 8개 |
| 동시성 | Search 내부 동시성 없음. Case가 Job을 몇 개 동시에 발주하느냐의 문제 |
| Fine 후보당 | wall p50 8.5초 / p95 15.5초 / 최대 33.4초 |
| 전처리 몫 | Coarse 1분 이상에서 wall의 절반 이상(5분은 약 2/3). provider 지연만으로 timeout을 잡으면 모자란다 |

토큰 합계: 입력 207,088 / 출력 20,132 (49회). 비용은 단가 설정이 비어 있어 ledger에 기록되지 않았다.

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
```
