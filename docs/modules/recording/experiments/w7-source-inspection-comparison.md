# W7 source inspection 재사용 전후 v3 baseline 비교

동일 RecordingService 실행 안에서 AnalysisSource가 조사한 원본·VIDEO stream의
frame inspection을 IncidentClip이 재사용한 전후 결과다.
전체 실행 중앙값은 약 **28.5% 감소**, IncidentClip의 source_probe 중앙값은
약 **99.98% 감소**했다.

## 측정 근거와 비교 조건

이 문서는 실행자가 제공한 전후 v3 baseline 요약을 기록한다. 이번 문서 작성에서는
raw bundle과 실행 JSON을 다시 열어 독립 검증하거나 측정을 재실행하지 않았다.
아래 조건과 원본 불변 검사 통과 여부는 실행자의 확인 결과다.

| 항목 | 전후 비교 조건 |
| --- | --- |
| Bundle schema | recording-baseline/v3 |
| Raw run schema | recording-benchmark/v3 |
| 반복 수 | 개선 전·후 각각 3회 |
| Bundle status | 개선 전·후 모두 FROZEN |
| Dataset | 동일 익명 dataset ID와 동일 fingerprint |
| 실행 설정 | 동일 VIDEO stream·요청 범위·생성 설정 |
| 도구 버전 | Python·ffmpeg·ffprobe 모두 동일 |
| 원본 불변 | 전후 SHA-256·크기·mtime 검사 통과 |

원본 파일명, 로컬 경로, bundle 위치와 인증정보는 기록하지 않는다.
기존 raw bundle·실행 JSON·영상은 그대로 보존하며 이 문서에 복제하지 않는다.

## 중앙값 비교

단위는 초다. AnalysisSource와 IncidentClip 행은 Benchmark 단계 시간이며,
source_probe 행은 각 materialization 내부 trace phase 시간이다.

| 측정 대상 | 개선 전 중앙값 | 개선 후 중앙값 |
| --- | ---: | ---: |
| 전체 실행 | 12.268638 | 8.771333 |
| AnalysisSource | 6.863660 | 7.305733 |
| IncidentClip | 4.594775 | 0.651406 |
| AnalysisSource source_probe | 3.849445 | 4.204156 |
| IncidentClip source_probe | 3.954117 | 0.000972 |

비율은 **각각의 중앙값을 이용해 계산**했다. 개별 실행의 변화율을 계산한 뒤
그 중앙값을 구한 결과가 아니다.

- 전체 감소율: `(12.268638 - 8.771333) / 12.268638 × 100 = 28.506057…%`, 약 **28.5%**.
- IncidentClip source_probe 감소율: `(3.954117 - 0.000972) / 3.954117 × 100 = 99.975418…%`, 약 **99.98%**.
- AnalysisSource 증가율: `(7.305733 - 6.863660) / 6.863660 × 100 = 6.440776…%`, 약 **6.4%**.

단계별 중앙값의 합은 전체 실행 중앙값과 같다고 가정하지 않는다.

## 해석과 한계

이번 비교는 **service lifetime 내 동일 원본·stream inspection 재사용 효과**를 보여준다.
AnalysisSource가 먼저 조사하고 IncidentClip이 결과를 재사용하는 순서에서,
IncidentClip source_probe 시간이 크게 줄었다. 이 phase는 재사용 후에도
inspection 결과 획득 시간을 측정하므로 조회·복사 비용을 포함하며 0초가 아니다.
구현 경계는 [source inspection 재사용 설명](w7-source-inspection-reuse.md)을 참고한다.

AnalysisSource 중앙값은 약 6.4% 증가했다. 전후 각각 3회 측정만으로 이를
성능 퇴행으로 단정하지 않는다. 원시 분포와 추가 반복 없이 증가 원인이나
통계적 유의성을 확정할 수 없으며, OS 캐시·실행 시점의 부하 등의 영향을
이번 요약만으로 분리할 수 없다.

매 반복은 독립 Service를 사용한다. 이번 결과는 TTL·영속 캐시·서비스 간 재사용이나
동시 요청에서의 성능 효과를 입증하지 않는다. 다른 영상·stream·실행 환경에
동일한 감소율이 적용된다는 일반 성능 목표도 아니다.

원본 snapshot 및 materialization 전후 변경 검사, output probe와 출력 검증은 유지된다.
이 비교를 위해 Contract, profile 정책 또는 v3 schema를 변경하지 않았다.
후속 개선 대상은 남은 phase 비용과 추가 반복 측정을 근거로 선택한다.
