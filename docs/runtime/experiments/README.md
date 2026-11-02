# Runtime Experiments

Runtime의 cross-cutting 실행 질문을 실제 환경에서 검증하기 위한 experiment plan/result 라우터다.

> 이 폴더의 실험 문서는 **결정의 근거(evidence)** 이며 Final Contract, Runtime Tech Spec, Ops Spec을 대체하지 않는다. 반복 가능한 결과가 실제 구현·운영 결정을 만들 때만 상위 문서로 승격한다.

## 이 폴더가 다루는 것

```text
recording
→ media/profile/ffmpeg/storage 사실

search
→ provider compatibility / recall / token / cost / latency 사실

runtime experiments
→ 위 경로가 실제 실행 환경에서 합쳐졌을 때
   CPU / RAM / disk / queue / concurrency / recovery에 미치는 영향
```

대표 질문:

- api + worker + mysql이 같은 baseline host에서 함께 동작할 때 자원 경합이 있는가
- ffmpeg materialization과 provider request construction의 peak working set은 얼마인가
- Worker concurrency를 늘릴 여유가 실제로 있는가
- 실행 내 reuse·반복 job의 재준비·durable ref 읽기 비용이 restart/다중 Worker에서 어떻게 달라지는가
- failure/crash 후 temp asset과 실행 상태가 회수되는가
- long-duration Real E2E가 현재 storage/capacity 가정을 깨는가

Search/Recording 자체의 품질·profile·provider 내부 알고리즘 실험은 각 module Owner 문서가 소유한다.

## 문서 lifecycle

```text
상위 이슈 / module 실험 결과
→ Runtime에 남은 질문 정의
→ experiments/* plan
→ 실제 환경에서 측정
→ result 기록
→ 반복 가능한 사실만 runtime-tech-spec / ops-spec에 승격
→ 여러 구현에 장기 영향을 주는 구조 결정이면 decisions/ ADR
```

### Plan

아직 검증하지 않은 질문, 입력 후보, 관측 항목, 실험 순서를 적는다.

Plan 단계에서는 다음을 하지 않는다.

- 근거 없는 PASS threshold 발명
- module canonical profile 확정
- EC2/Worker/Object Storage 확장 선결
- provider-specific 계약을 Runtime 문서에 복제

### Result

실제 실행 환경, revision, 입력, 측정 방식, raw observation과 해석을 구분해 남긴다.

한 호스트·한 입력의 단회 수치를 일반적인 운영 상수로 승격하지 않는다.

### Decision / ADR 승격

실험 결과가 다음 조건을 만족할 때 Tech/Ops 문서에 반영한다.

1. 어떤 질문을 닫는 결과인지 명확하다.
2. 실행 환경과 revision이 식별 가능하다.
3. module Owner의 품질/계약 의미를 Runtime이 재정의하지 않는다.
4. 결과가 구현·운영 선택을 실제로 바꾼다.

다음처럼 여러 구현과 향후 migration에 장기 영향을 주면 `docs/runtime/decisions/` ADR 후보로 올린다.

- Worker concurrency/scaling model 변경
- persistent/shared media storage 도입
- DB Queue에서 전용 Queue로 전환
- baseline deployment topology 변경
- 공용 versioned pricing/FX artifact 도입 같은 cross-module 구조 변경

단순 tuning 값이나 단회 benchmark마다 ADR을 만들지는 않는다.

## 현재 계획

| 문서 | 상태 | 닫으려는 질문 |
| --- | --- | --- |
| [RT-14 AWS 배포·Real E2E 2026-10-31](./2026-10-31-rt14-aws-real-e2e.md) | Result | 실제 EC2 배포·public smoke·7 job 실행과 최종 Package READY의 입력 조건을 구분한 단회 acceptance |
| [Runtime Capacity Smoke Plan — P2 (Elice ML API)](./elice-runtime-capacity-smoke-plan.md) | Planned · 2026-11-02 구현/Product 정합성 반영, 미실행 | 0a 현 baseline rejection 회귀 / 0b 현 baseline 안 characterization / 0c 격리 experimental override로 최초 병목·최소 20분 logical timeline 가능성 판단. RT-14 단회 acceptance와 구분 |
| [Pre-implementation Spike 2026-10-03](./pre-implementation-spike-2026-10-03.md) | Result | workflow §5 A Decision의 기술 semantics — claim lock(RR/RC) · conditional UPDATE 경합 · Compose secret file · shared volume rename. capacity 실험이 아니다 |

[P2 수정 전 감사](../reviews/runtime-p2-plan-audit-2026-11-02.md)는 기존 A~F 판정·현재 코드 경로·계측 공백을 기록한다.
RT-14 Result의 §14~§15와 Recovery §10에는 재부팅·DB/media 격리 복원의 운영자 제공 후속 결과가 있다.
이를 P2 capacity 완료 또는 RT-14 전체 완료로 확대하지 않는다.

[Product Spec](../../product/product-spec.md)의 핵심 약속은 장시간·다중 블랙박스에서 사건 후보를 먼저 찾는 것이다.
4분/48 MiB는 초기 배포 안전 baseline·현재 config snapshot이며 최종 제품 지원 길이가 아니다.
약 19분 26초/22개 입력의 baseline rejection PASS도 제품 지원 범위 밖 확정이나 장시간 문제 해결을 뜻하지 않는다.
최소 20분 logical timeline은 이번 PM 요청의 **검증 목표/decision target**이며 현재 지원 확정값이 아니다.

P2-0c에서는 운영과 분리된 target에 근거·유한한 안전 한도·복귀 계획을 갖춘 experimental override를 허용한다.
운영 baseline 변경이나 측정값의 자동 production 승격과 구분한다. 현 single-source/단일 Coarse 구조가
제품 목표를 충족하지 못하면 bounded/chunked processing·storage·Search 요청·Case merge/dedup 등을
포함한 cross-module 설계를 다시 연다. 채택 방식은 아직 미정이며 제품 지원 범위 변경의 최종 승인자는 PM이다.

P3는 **30분~1시간 logical timeline Real E2E**다. single AnalysisSource인지 다른 bounded 처리인지 미정이며,
P2 결과와 Recording/Case/Search의 장시간 지원 설계 결정 후 정한다.

## Routing

- 실행 lifecycle / queue / UsageRecord persistence → [Runtime Tech Spec](../runtime-tech-spec.md)
- deployment / capacity / storage / monitoring → [Runtime Ops Spec](../ops-spec.md)
- 배포 실행 체크 → [Deployment Runbook](../deployment-runbook.md)
- 장기 구조 결정 → `../decisions/`
- Search/usage/pricing/provider config 경계 조사·합의 → [Issue #153](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/153) (Runtime 반영: Tech Spec §11.3 · §15.1)

## References

- [Issue #95 — Elice ML API migration tracker](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/95)
- [Issue #153 — provider usage · pricing · runtime config boundary review](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/153)
- [Runtime README](../README.md)
