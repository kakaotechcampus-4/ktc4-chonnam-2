# Mock Pack v1 — ref 예시 (계약 아님)

> **정식 recording 계약 이전의 비규범 보조 자료였다.** 필드·lookup·시간 변환 규칙을 정의하지 않는다. ref 작업 규약의 원천은 `module-architecture.md` §5-3이며 여기에는 규칙을 복제하지 않는다. **정식 계약 2건이 Accepted가 되어 이 문서는 아래 `Status`대로 폐기됐다** — 규범으로 읽지 않는다.

**Status:** **폐기 — 2026-09-08.** 폐기 조건이 충족됐다: `contract-source-asset-media-stream.md`(`source-asset-media-stream/v1`)와 `contract-analysis-source-derived.md`(`analysis-source-derived/v1`)가 Consumer Review 종결로 `Final — Accepted`가 됐다. **이 문서를 규범으로 읽지 않는다.** 자산 ref의 형식·필드·lookup·`AssetFacts`·`FrameRef`·자산 계층 `ContractRef.kind` 값 공간은 그 두 계약이 소유하고, ref 작업 규약의 원천은 `module-architecture.md` §5-3이다. 아래 본문은 역사적 기록으로 남긴다
**Owner:** 김준영 (PM)
**폐기 조건:** `contracts/contract-source-asset-media-stream.md` 및 `contracts/contract-analysis-source-derived.md`가 **Accepted**(Consumer Review 종료)로 전환 — **2026-09-08 충족.** 근거 `contracts/adr/adr-data-contract-call-closure-2026-09-08.md` §4.10

## 1. 사용할 수 있는 범위

이미 정의된 응답에서 opaque ID를 일관되게 연결하는 개별 fixture를 만들 때 참고한다. `RecordingTimeline`·`AssetSpan`·`SpanResolution`에 Final 헤더가 있다는 것만으로 소비자 접합이 검증되지는 않는다.

**B06~B09 상태 (2026-09-07 → 2026-09-08).** Owner 결정은 끝났다(`contracts/adr/adr-data-contract-call-closure-2026-09-07.md` §4.5~§4.9). `SpanResolution` failure 직렬화와 `AnalysisScope` relative range 직렬화는 2026-09-08에 종결됐다(`contracts/adr/adr-data-contract-call-closure-2026-09-08.md` §4.3·§4.4). 그러나 이 문서의 ID만으로 자산 크기·가시성·원본 무변형·ReportPackage gate를 계산할 수 없다는 점은 그대로다 — **Asset Facts 필드는 recording 자산 계약 2건이 소유하고 2026-09-08에 `Final — Accepted`가 됐다.** 필요한 필드는 이 문서가 아니라 그 계약(`contract-source-asset-media-stream.md` §6 · `contract-analysis-source-derived.md`)에서 읽는다.

## 2. ID 예시

아래 값은 사람이 비교하기 위한 샘플이며 ID suffix에 파일·카메라·위치 의미를 배정하지 않는다. 형식과 해석 원칙은 v4 §5-3을 따른다.

```text
sa_0001, sa_0002
ms_0001, ms_0002, ms_0003
fr_a1b2c3
as_0001, rc_0001, clip_0001, da_0001
```

## 3. 미결과 제한적 실행

- `CaseView.candidates[].thumb_ref`는 `FrameRef`(`fr_` 계열)로 확정됐다(2026-09-07). `FrameRef`·파생 자산의 필드 계약과 thumbnail 이미지 전달 형태는 recording 자산 계약 2건 대기다.
- `source_profile`은 ref 목록에 넣지 않는다. 판독 계약의 라벨이며 자산 ID 타입이 아니다.
- upload 방식·proxy profile 값·retention·provider별 delete 방식은 기존 미결을 유지한다.
- 고정된 입력으로 개별 응답을 비교하는 작업과 `ownership.md` §7-④ 전체 E2E 통과는 구분한다. 실행 결과가 아직 없으므로 여기서 E2E PASS를 선언하지 않는다.

**§1~§3은 폐기 시점(2026-09-08) 이전의 역사 기록이다.** 현재 닫힌 항목·Pending·종결·다음 단계 준비도 판정은 `contracts/adr/adr-data-contract-call-closure-2026-09-08.md` §9·§10.2를 따른다(이전 회차는 같은 폴더의 `adr-data-contract-call-closure-2026-09-07.md`, 2026-09-06 보정 기록은 `contracts/adr/adr-consistency-followup-2026-09-06.md`).
