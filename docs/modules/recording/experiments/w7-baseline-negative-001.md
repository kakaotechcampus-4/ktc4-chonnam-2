# W7 Recording 분리 범위 baseline — negative-001

**상태:** FROZEN · **Owner:** 정철원 · **범위:** 익명 실제 단일 원본의 Recording 처리시간 기준선

Git 밖에 보존된 bundle과 raw run 3개를 확인한 결과다. 각 raw JSON의 SHA-256을
manifest와 대조하고, 단계별 min/median/max를 재계산해 bundle 요약과 일치함을 확인했다.
이 문서에는 로컬 경로·원본 파일명·개인정보·인증정보를 기록하지 않는다.
영상, raw bundle/runs JSON 및 기존 단일 실행 JSON은 커밋 대상이 아니다.

## 입력과 실행 조건

| 항목 | 값 |
| --- | --- |
| Bundle schema | `recording-baseline/v2` |
| Raw run schema | `recording-benchmark/v2` |
| Bundle ID | `baseline_3253585b0f604589b00f306d2e24773e` |
| 익명 dataset_id | `ds_2818d7a1ad144c948f8000803b71c9f4` |
| 원본 SHA-256 | `5c82b6f7b163ae400fbdc20a2a121f639ed32b141e0b0c9682eef531a6114008` |
| 원본 byte_size | 25,804,800 bytes |
| 원본 duration_sec | 20.024656초 |
| VIDEO stream 수 | 1 |
| 명시적 VIDEO 순번 | 0 |
| Python | 3.12.14 |
| ffmpeg / ffprobe | 9.0.1 / 9.0.1 |
| 생성 설정 | 480p · H.264 · veryfast · CRF 23 · audio off · yuv420p · faststart |
| Profile 범위 | `benchmark_trial` — 최종 Canonical profile 확정이 아님 |
| Analysis 요청 범위 | 0–20.024656초 |
| Incident 요청 범위 | 1–2초 |
| 요청 / 완료 반복 | 3회 / 3회 |
| Service 수명 / warm-up 제외 | 매 실행 새 service / 0회 |

AnalysisSource는 analysis 범위, IncidentClip과 Frame은 incident 범위로 실행했다.
각 실행에서 두 범위는 동일 Timeline revision과 명시적 VIDEO stream을 사용한다.
3회 모두 analysis·incident 해소 결과가 `COMPLETE`였으며, 최초 실패(`failure`)는 null이다.
기존 단일 범위 결과는 smoke/micro baseline으로 따로 보존하며 이 결과로 덮어쓰지 않는다.

## 동결과 원본 불변 확인

| freeze_checks | 값 |
| --- | --- |
| all_repeats_completed | true |
| all_runs_usable | true |
| original_unchanged | true |
| same_fingerprint | true |
| same_settings | true |
| same_versions | true |
| same_technical_metadata | true |

각 실행 전후 원본 SHA-256·byte_size·mtime이 동일하고, 반복 간 fingerprint도 동일했다.
상태 집계는 `FALLBACK: 3`이다. 이는 신뢰된 절대시각 anchor를 적용하지 않아 Timeline이
`USABLE_RELATIVE_ONLY`로 유지된 정상 상태다. 구간 해소 실패나 materialization 실패를 뜻하지 않는다.
Timeline 단계를 제외한 측정 단계는 모두 `SUCCESS`였고, 실패 시간 표본은 0개다.

## 단계별 측정 결과

단위는 초, 각 단계 표본 수는 3이다. 소수점 아래 7자리로 반올림했다.
경과시간은 `perf_counter` 기준이며 CPU time이 아니다.

| 단계 | min | median | max |
| --- | ---: | ---: | ---: |
| input_fingerprint | 0.0184552 | 0.0188958 | 0.0220630 |
| tool_versions | 0.0542974 | 0.0551095 | 0.0603016 |
| register_probe | 0.1098736 | 0.1155433 | 0.1451356 |
| timeline | 0.0000787 | 0.0001139 | 0.0001594 |
| stream_selection | 0.0000009 | 0.0000010 | 0.0000015 |
| resolve_analysis_span | 0.0179210 | 0.0212622 | 0.0231685 |
| resolve_incident_span | 0.0214178 | 0.0246019 | 0.0247896 |
| analysis_source | 5.2066464 | 5.5232308 | 5.5402514 |
| incident_clip | 3.1843389 | 3.3233905 | 3.4157864 |
| frame | 0.3148276 | 0.3327682 | 0.3834709 |
| original_integrity | 0.0189263 | 0.0193026 | 0.0199286 |
| **전체 실행** | **9.2554491** | **9.3125912** | **9.4494193** |

`register_probe`에는 등록에 포함된 probe·fingerprint 비용이 들어 있다.
`analysis_source`는 준비·open·전체 stream 읽기/hash, `incident_clip`은 생성·공개 조회,
`frame`은 resolve_frame·read_frame을 포함한다. 전체 시간에는 버전 조회·원본 검사·cleanup도 포함된다.
단계별 중앙값의 합이 전체 중앙값과 같다는 가정은 하지 않는다.

## 관찰과 다음 단계

전체 중앙값은 약 **9.31초**, AnalysisSource 약 **5.52초**, IncidentClip 약 **3.32초**,
Frame 약 **0.33초**였다. 다음 계산으로 두 materialization 단계의 비중을 비교했다.

```text
(AnalysisSource 중앙값 + IncidentClip 중앙값) / 전체 중앙값 × 100
= (5.523230799939483 + 3.3233904999215156) / 9.31259119999595 × 100
≈ 94.996% ≈ 95%
```

이는 **단계별 중앙값 합과 전체 중앙값의 비율**이며, 실행별 비율의 중앙값이나 인코딩만의 비용 비율은 아니다.
이 입력·설정·환경에서는 두 단계의 측정 비용이 대부분을 차지한다는 관찰로 한정한다.

실제 영상 1개를 3회 측정한 결과만으로 일반적인 성능 목표나 병목 원인을 확정하지 않는다.
매번 service는 새로 만들었지만 OS 파일 캐시·encoder warm-up을 초기화한 cold 측정은 아니다.
원본 길이·해상도·codec·하드웨어가 달라질 때의 성능, 동시성·메모리 사용량,
Search 탐지율·OCR 정확도도 이 결과로 주장하지 않는다.

**다음 단계는 materialization 내부의 source probe / encode / output probe / read 비용을
분리 측정한 후 개선 대상을 선택하는 것이다.** 현재 총시간만으로 encode가 원인이라고
단정하거나 cache·TTL·proxy 최적화 정책을 확정하지 않는다.

측정 방법과 schema는 [Benchmark 실행기](w7-benchmark-runner.md),
동결·통계·raw 보존 규칙은 [Baseline bundle](w7-baseline-bundle.md)을 따른다.
