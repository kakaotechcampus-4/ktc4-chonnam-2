# Mock Pack v1 — ref 예시 (계약 아님)

> **정식 recording 계약 이전의 비규범 보조 자료다.** 필드·lookup·시간 변환 규칙을 정의하지 않는다. ref 작업 규약의 원천은 `module-architecture.md` §5-3이며 여기에는 규칙을 복제하지 않는다. 정식 계약 두 건이 나오면 이 문서를 폐기하고 포인터를 교체한다.

**Status:** 임시 — 개별 fixture용, 전체 통합 가능 보증 아님 (2026-09-06 감사 후속)
**Owner:** 김준영 (PM)
**폐기 조건:** `contracts/contract-source-asset-media-stream.md` 및 `contracts/contract-analysis-source-derived.md` 제공

## 1. 사용할 수 있는 범위

이미 정의된 응답에서 opaque ID를 일관되게 연결하는 개별 fixture를 만들 때 참고한다. `RecordingTimeline`·`AssetSpan`·`SpanResolution`에 Final 헤더가 있다는 것만으로 소비자 접합이 검증되지는 않는다.

**B06~B09는 Pending이다.** SpanResolution의 요청 범위 완전성, 실제 evidence가 읽을 자산 metadata, 상대시각 입력, 사용 revision 연결이 남아 있다. 이 문서의 ID만으로 자산 크기·가시성·원본 무변형·ReportPackage gate를 계산할 수 없다. 필요한 필드가 없으면 임의 생성하지 않고 해당 Owner 계약을 기다린다.

## 2. ID 예시

아래 값은 사람이 비교하기 위한 샘플이며 ID suffix에 파일·카메라·위치 의미를 배정하지 않는다. 형식과 해석 원칙은 v4 §5-3을 따른다.

```text
sa_0001, sa_0002
ms_0001, ms_0002, ms_0003
fr_a1b2c3
as_0001, rc_0001, clip_0001, da_0001
```

## 3. 미결과 제한적 실행

- `CaseView.candidates[].thumb_ref`의 자산 종류와 FrameRef/파생 자산 필드 계약은 recording·case 확인 대기다.
- `source_profile`은 ref 목록에 넣지 않는다. 판독 계약의 라벨이며 자산 ID 타입이 아니다.
- upload 방식·proxy profile 값·retention·provider별 delete 방식은 기존 미결을 유지한다.
- 고정된 입력으로 개별 응답을 비교하는 작업과 `ownership.md` §7-④ 전체 E2E 통과는 구분한다. 실행 결과가 아직 없으므로 여기서 E2E PASS를 선언하지 않는다.

현재 닫힌 항목·Pending 및 담당 경계는 `contracts/adr/adr-consistency-followup-2026-09-06.md` §2~§5를 따른다.
