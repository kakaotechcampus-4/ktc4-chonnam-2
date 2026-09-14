# 이슈 초안 — `PLATE_IMAGE` 생성과 크기 전달이 기존 Contract로 충분한지 확인

> 상태: **게시 완료 — [이슈 #47](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/47)** (2026-09-13). 이 문서는 이슈의 원본 초안과 재검토 기록으로 남는다. 이후 논의는 이슈에서 진행한다.
>
> 작성일: `2026-09-13`
>
> 관련 결정: [`ADR-EVIDENCE-002` K1](../adr/adr-first-completion-owner-decisions.md#3-k1--첨부-용량개수-policy)
>
> 제안 논의자: 정철원(`recording`) · 신유민(`readout`) · 유소연(`case`) · 김준영(`evidence`)

## 제안 제목

`[recording/readout/case/evidence] PLATE_IMAGE 생성 입력과 byte_size 전달 — 기존 Contract로 충분한지 확인`

## 한 줄 요약

`REPORT_VIDEO`에는 「누가 발주하고, 누가 만들고, 실패하면 무슨 code를 내는지」가 전부 있는데 **`PLATE_IMAGE`에는 그게 하나도 없다.** 두 role이 같은 표에 나란히 등재돼 있어서 같은 흐름이 있는 것처럼 보이지만 실제로는 비어 있다. 그래서 신고용 번호판 이미지의 용량 판정을 실제로 돌릴 수 없다. 이 이슈는 그 빈 자리를 **기존 Contract로 메울 수 있는지** 확인한다.

## 배경

### 무엇을 하려는 것인가

대신고는 마지막에 `ReportPackage`를 만들어 사용자에게 넘긴다. 여기에는 신고 제출용 영상(`DerivedAsset.derived_role=REPORT_VIDEO`)이 필수로, 번호판 이미지(`derived_role=PLATE_IMAGE`)가 optional로 들어간다.

안전신문고는 첨부 파일에 용량 제한을 둔다. `evidence`는 Package를 넘기기 전에 이 제한을 검사해 `RequirementReport`에 `PASS`/`UNKNOWN`/`BLOCK`으로 남긴다.

### 용량 정책(K1)이 정한 것 — 인용

이 이슈를 읽는 데 필요한 만큼만 옮긴다. **원문과 값의 해석·변경은 [`ADR-EVIDENCE-002` §3](../adr/adr-first-completion-owner-decisions.md#3-k1--첨부-용량개수-policy)이 소유한다.** 아래는 참고용 인용이다.

- 판정 대상은 사용자 원본이나 분석 중간 파일이 아니라 **실제로 Package에 첨부할 자산 집합**이다. `SourceAsset`·`AnalysisSource`·`IncidentClip`·thumbnail·OCR crop은 대상이 아니다.
- 상한은 **이미지 각 파일 `30,000,000 bytes`** · 동영상 각 파일 `130,000,000 bytes` · 전체 합계 `180,000,000 bytes`다. `MB`는 decimal이고 비교는 정수 byte로 한다. 상한과 같은 값은 통과다(`actual <= limit`).
- 개별 파일 판정은 `byte_size=null → UNKNOWN` · `<= 상한 → PASS` · `> 상한 → BLOCK`이다.
- `UNKNOWN`(판정 보류)도 `BLOCK`(현재 자산으로 진행 불가)도 `FINAL_PACKAGE`의 `PACKAGE_READY`를 성립시키지 않는다. **크기를 모르면 신고자료가 완성되지 않는다.**
- 외부 제출 제한보다 낮은 **내부 목표 용량은 두지 않는다.** 실제 파일이 상한을 넘었을 때만 후속 처리를 한다. 내부 목표가 필요해지면 신고요건이 아니라 `recording` Tech Spec의 생성 전략으로 따로 정한다.

### 왜 `evidence`가 직접 확인할 수 없는가

`evidence`는 파일을 열지 않는다. `evidence → recording` 직접 호출은 구조상 금지돼 있다(`contract-analysis-source-derived.md` §10 금지사항). `evidence`가 보는 것은 `case`가 주입해 준 `AssetFacts`(`availability` · `byte_size` · `lineage`)뿐이고, 실제 구현도 이미 그렇게 돼 있다.

따라서 위 판정이 돌아가려면 **누군가 실제 파일을 만들고, 실제 크기를 재서, `evidence`까지 전달**해야 한다. 이 이슈는 그 「누군가」와 「무엇을 입력으로」를 확인한다.

### `REPORT_VIDEO`에는 있고 `PLATE_IMAGE`에는 없는 것

| | `REPORT_VIDEO` | `PLATE_IMAGE` |
| --- | --- | --- |
| `derived_role` 등재 | ✅ `analysis-source-derived` §7.3 | ✅ 같은 표에 나란히 |
| 생성 capability | ✅ `export_report_video(...)` | ❌ 없음 |
| 발주 `JobRecord.kind` | ✅ `REPORT_VIDEO_EXPORT` | ❌ 없음 |
| 사용자 재시도 action | ✅ `GENERATE_REPORT_VIDEO` | ❌ 없음 (`notices[].actions[]`는 닫힌 목록) |
| 생성 실패 code | ✅ `REPORT_VIDEO_EXPORT_FAILED` | ❌ 없음 |
| evidence의 크기 rule code | ✅ `package.asset.report_video.size` | ❌ 없음 |
| Mock fixture | ✅ 발주 Job까지 존재 | ⚠️ 자산은 있는데 발주 기록이 없음 |

오른쪽 열의 ❌가 이 이슈의 전부다. **「계약이 틀렸다」가 아니라 「아직 아무 데도 없다」**이므로, 기존 Contract로 메울 수 있는지부터 확인하는 것이 맞다.

### 이미 닫혀 있어서 다시 논의하지 않는 것

- `readout`은 `PlateReadout`으로 OCR 결과·`best_frame`·frame/crop 근거를 생산한다. 값을 확정하지는 않는다.
- `crop_ref`는 **readout 내부 identity이고 이미지 조회 handle이 아니다.** crop 이미지를 가져오는 public 경로는 어느 계약에도 없다(2026-09-10 확정, 이슈 `#31` A-3 / `#40` C절).
- `recording`은 `DerivedAsset`의 Runtime Producer이고 canonical `AssetFacts.byte_size`·`lookup_asset_facts`를 소유한다.
- `case`가 `recording`에서 `AssetFacts`를 조회해 `evidence`에 주입한다.
- `evidence`는 주입받은 자산 사실만 K1과 비교해 `RequirementReport`를 만든다.
- 재생성할 때 기존 자산을 조용히 덮어쓰지 않고 새 ref와 provenance로 잇는 것은 이미 확정된 패턴이다(§6.7 · §7.2).

### 아직 닫히지 않은 것

- 어느 `PlateReadout`의 어떤 근거를 `PLATE_IMAGE` 생성 입력으로 쓸지
- `case`가 언제, 어떤 공개 capability로 생성을 발주할지
- `recording`이 `crop_ref`를 해석하지 않고도 동일한 제출 이미지를 만들 입력이 충분한지
- 30MB를 넘었을 때 새 `DerivedAsset`을 만드는 주체와 재검사 흐름
- 이미지 변환 provenance와 생성 실패 code의 최소 표현

## 문제

현재 계약만 보고 다음 흐름을 결정론적으로 구현할 수 없다. 중간 두 칸이 비어 있다.

```text
readout   PlateReadout.best_frame / target_association
              ↓  ← ❓ 어떤 근거를 입력으로 쓰는가 (Q1·Q2)
case      PLATE_IMAGE 생성 발주
              ↓  ← ❓ 언제, 어떤 capability로 (Q3·Q4)
recording 이미지 추출·변환 → DerivedAsset(role=PLATE_IMAGE)
              ↓
recording AssetFacts(byte_size, availability, lineage)
              ↓
case      lookup_asset_facts 결과를 evidence에 주입
              ↓
evidence  K1 판정 → PASS / UNKNOWN / BLOCK
                     ↑  ← ❓ BLOCK이면 누가 다시 만드는가 (Q5)
```

빈 칸을 급하게 메우면 나오기 쉬운 두 가지 구현이 있는데, 둘 다 이미 확정된 경계를 깬다.

**(1) `case → recording.export_plate_image(crop_ref)`** — `crop_ref`는 조회 handle이 아니고 `recording`이 생성하거나 해석하는 값도 아니다. `recording`은 그 문자열로 아무것도 열 수 없다.

**(2) `readout`이 제출 파일과 `byte_size`까지 생산** — `DerivedAsset`과 자산 사실의 `recording` 소유권을 침범한다. `readout`은 「무엇이 보였는가」까지만 말하는 모듈이다.

그래서 「어떻게 구현할까」를 각자 정하기 전에, **입력과 발주와 소유권을 먼저 확인**해야 한다.

## 확인할 질문

질문마다 답해야 할 Owner가 다르다. **각자 자기 이름이 붙은 항목만 답하면 된다** — Q1만 두 모듈이 함께 본다. 이미 확정된 선례로 답이 정해지는 것은 질문에서 빼고 「권장 경계」와 「완료 조건」으로 옮겼다(무엇을 왜 뺐는지는 아래 재검토 절).

### Q1. 무엇을 만드는가 — `readout`·`evidence`

신고용 `PLATE_IMAGE`는 번호판 crop인가, 주변 맥락을 포함한 영역인가?

`core-user-flow.md` §12는 출처를 「영상에서 가장 선명한 번호판 장면과 **주변 장면을 함께** 확인」으로 적는다. 그런데 `ReportPackage.assets.plate_image_ref`는 optional **단일** ref다. 화면 문구가 이미지 2장을 뜻하는지 맥락을 포함한 1장을 뜻하는지에 따라 아래 질문의 답이 갈린다.

### Q2. 생성 입력이 기존 Contract로 충분한가 — `readout`

`target_association.associated_region.bbox_xywh`는 **제출 이미지를 재생성하는 authoritative 영역**인가, 단지 차량 association 근거인가?

현재 `PlateReadout`에서 영역 값은 이 한 곳뿐이고 `best_frame`에는 `frame_ref`·`crop_ref`·`quality`만 있다. Mock도 마찬가지여서, `da_h001_plate_image`는 `source_refs=[{incident_clip, clip_h001}]`·`transform_ref=null`이고 같은 시나리오 readout의 `fr_h001_plate1`·`bbox_xywh=[820,410,176,68]`과 이어지는 값이 없다. **fixture만 봐서는 어느 프레임의 어느 영역을 잘라 만든 이미지인지 알 수 없다.**

기존 필드로 부족하다면 어떤 최소 locator가 어느 Contract에 필요한지까지 함께 답해야 닫힌다.

### Q3. 누가 언제 발주하는가 — `case`

`case`는 `PlateReadout` 생성 직후 발주하는가, 사용자 번호판 확인 이후 발주하는가?

`core-user-flow.md` §12의 `[번호판 이미지 보기]`는 상태가 아직 `AI 추정`일 때 이미 떠 있다. 사용자 확인 이후에만 만든다면 그 버튼이 무엇을 보여주는지가 따로 정리돼야 한다.

Mock에는 `REPORT_VIDEO_EXPORT` Job은 있는데 plate image에 대응하는 Job이 없어서, 지금 fixture는 「누가 언제 발주했는지」를 말하지 않는다. 발주가 필요하다면 `JobRecord.kind` 신규 등재가 뒤따르는지도 함께 확인한다(현재 등재 5종에 없음).

### Q4. recording의 공개 capability와 실패 표현 — `recording`

생성 capability의 입력과 최소 성공 응답은 무엇인가? 그리고 `REPORT_VIDEO_EXPORT_FAILED`에 대응하는 plate image 생성 실패 code가 필요한가?

짝이 되는 것은 이미 있는 `export_report_video(span_or_clip, options)`다. 같은 자리에 이미지용이 하나 필요한지, 아니면 기존 frame 조회 capability 조합으로 충분한지가 실제 질문이다. 함수명 자체는 `module-architecture.md`도 「예시」라고 밝힌 수준이라 이름보다 **입력과 응답의 모양**이 중요하다.

실패 code는 없으면 곤란하다. `contract-analysis-source-derived.md` §9의 failure code 표에 plate image 항목이 없어서, 지금은 생성이 실패해도 `case`가 그것을 `CaseView.notices[].code`로 옮길 경로가 없다 — 사용자 화면에 「번호판 이미지를 만들지 못했다」가 뜨지 않는다.

### Q5. 30MB를 초과하면 누가 다시 만드는가 — `case`·`recording`

`case`가 새 변환을 재발주하는가, `recording`이 하나의 요청 안에서 제한을 만족시키는가?

용량 정책은 **판정만** 소유하고 재생성 흐름은 소유하지 않는다. 지금 상태로는 `BLOCK`이 나와도 그다음에 아무 일도 일어나지 않는다.

사용자에게 재생성 버튼까지 주려면 `notices[].actions[]`에도 값이 필요한데 이 목록은 7종으로 **닫혀 있다**. 어느 쪽으로 정하든 「완료 조건」의 provenance 규칙(과거 자산을 덮어쓰지 않고 새 ref로 잇기)은 그대로 지켜야 한다.

## 권장 경계

아래 방향을 기본안으로 검토한다. 이는 이슈 초안의 제안이며 아직 cross-module 결정이 아니다.

```text
readout
  → 번호판 관찰과 재생성 가능한 근거 제공

case
  → 선택·사용자 확인 상태에 맞춰 PLATE_IMAGE 생성 발주

recording
  → canonical source에서 제출 이미지를 생성·변환
  → DerivedAsset(role=PLATE_IMAGE)과 실제 byte_size 제공

case
  → lookup_asset_facts 결과를 evidence에 주입

evidence
  → K1 policy로 PASS / UNKNOWN / BLOCK 판정
```

- readout은 최종 첨부 용량을 판정하지 않는다.
- recording은 30MB라는 신고 정책의 의미를 소유하지 않는다. 요청받은 생성 조건에 따라 파일을 만들고 실제 자산 사실을 제공한다.
- case는 크기 제한을 복제 계산하지 않고 orchestration만 담당한다.
- evidence는 파일을 직접 읽거나 recording을 호출하지 않고 주입된 `AssetFacts`만 판정한다.
- 내부 목표 용량은 두지 않는다. 실제 파일이 외부 상한을 초과한 경우에만 후속 변환 흐름을 수행한다.
- 이미지 format·quality·crop/resize 방식은 Contract에 고정하지 않고 `recording` Tech Spec에 둔다. AnalysisSource profile 값과 proxy resolution/FPS/bitrate를 계약에 고정하지 않은 선례를 그대로 따른다(`contract-analysis-source-derived.md` §10 금지사항 · §11-1 · §11-5).

## 완료 조건

- [ ] `PLATE_IMAGE` 생성 입력이 기존 Contract만으로 충분한지 Yes/No가 기록되어 있다.
- [ ] 부족하면 필요한 최소 Contract 변경과 Owner가 특정되어 있다.
- [ ] `crop_ref`를 외부 조회 handle로 사용하지 않는다.
- [ ] readout은 관찰 근거, recording은 DerivedAsset·byte 크기, case는 발주·전달, evidence는 정책 판정을 각각 소유한다.
- [ ] 성공 시 `DerivedAsset.derived_role=PLATE_IMAGE`, `availability`, 실제 `byte_size`, source/lineage를 관찰할 수 있다.
- [ ] `availability=AVAILABLE`이면 `byte_size`가 non-null이다.
- [ ] 미측정·생성 실패·30MB 초과를 서로 구분할 수 있다.
- [ ] `byte_size=null → UNKNOWN`, `<=30,000,000 → PASS`, `>30,000,000 → BLOCK`을 실제 전달 값으로 검증한다.
- [ ] 재생성 시 과거 자산을 조용히 mutate하지 않고 새 결과와 provenance를 추적할 수 있다.
- [ ] 실제 `case → recording → case → evidence` 통합 test 또는 동등한 Contract-shaped artifact가 있다.

## 범위 밖

- OCR 모델·confidence threshold 선정
- 이미지 codec·품질·resize 알고리즘의 구체값
- UI 표시 디자인
- 안전신문고 자동 업로드·자동 제출
- 최대 4개 첨부를 표현하기 위한 `ReportPackage` 배열 변경

## 레포 내 중복·기존 근거 재검토 (2026-09-13)

게시 전에 같은 질문이 이미 닫혀 있는지 레포와 GitHub 이슈를 다시 확인했다. **닫혀 있지 않다.**

### 확인한 대상

| 대상 | 확인한 것 | 결과 |
| --- | --- | --- |
| GitHub 이슈 `#15`-`#41` (open·closed 전부, 본문과 코멘트) | `PLATE_IMAGE` · `plate_image` · `crop_ref` 언급 | 생성 입력·발주 경로·크기 전달을 다룬 이슈 없음 |
| `contract-analysis-source-derived.md` | §6.6 public capability · §7.3 role · §7.5 export 실패 · §9 failure code 표 · §11 Pending 8건 | `build_incident_clip`과 Report Video export만 등재. `PLATE_IMAGE` 생성 capability도 failure code도 없고 Pending 목록에도 없다 |
| `contract-plate-overlay-readout.md` | §3 `crop_ref` identity 절 (2026-09-10 확정) | `crop_ref`가 조회 handle이 아니라는 것까지만 닫혔다. crop 자산 발급은 **미래 항목**으로 남아 있다 |
| `contract-job-record-case-view.md` | A절 §7 `JobRecord.kind` · B절 `notices[].actions[]` | kind 등재 5종에 plate image 생성 발주가 없다. `actions[]`는 7종으로 **닫힌** 목록이고 `GENERATE_REPORT_VIDEO`만 있다 |
| `module-architecture.md` 모듈 1 ⑥·⑩ | recording Public Capability와 Owner Review Required | `export_report_video(...)`만 있다. plate image 생성은 capability에도 Owner Review 목록에도 없다 |
| `modules/recording/decisions/` · `modules/readout/decisions/` · `modules/case/decisions/` | 관련 결정 문서 | recording에는 결정 문서가 아직 없고, readout·case 어느 문서도 이 경계를 다루지 않는다 |
| `data/mock/**` · `src/daesingo/evidence/**` | 실제 fixture와 구현 | 아래 「재검토에서 드러난 빈 자리」 |

### 재검토에서 드러난 빈 자리

1. **발주 경로가 fixture에 없다.** `data/mock/case/*.json`의 `job_records[].kind`에는 `REPORT_VIDEO_EXPORT`가 있지만 plate image 생성에 대응하는 값은 어느 시나리오에도 없다. `da_h001_plate_image`·`da_u001_plate_image`는 발주 기록 없이 recording 사실로만 존재한다.
2. **생성 입력이 fixture에서 복원되지 않는다.** `recording/scenario_happy_001.json`의 `da_h001_plate_image`는 `source_refs=[{incident_clip, clip_h001}]`이고 `transform_ref=null`이다. 같은 시나리오 `readout/scenario_happy_001.json`의 `best_frame.frame_ref=fr_h001_plate1`·`associated_region.bbox_xywh=[820,410,176,68]`과 이어지는 값이 없다. **어느 frame의 어느 영역을 잘라 만든 이미지인지 fixture가 말하지 않는다.**
3. **K1의 이미지 상한을 소비하는 rule code가 없다.** `src/daesingo/evidence/requirements.py`의 자산 크기 검사는 `package.asset.report_video.size` 하나뿐이고 레포 전체에 `package.asset.plate_image.*` code가 없다. K1이 이미지 각 파일 `30,000,000 bytes`를 확정했는데 그 판정을 실제로 수행할 입력 경로가 아직 없다.
4. **실패 표현이 비대칭이다.** `contract-analysis-source-derived.md` §9는 Report Video export에만 `REPORT_VIDEO_EXPORT_FAILED`를 둔다. plate image 생성 실패를 `case`가 `CaseView.notices[].code`로 옮길 최소 code가 없고, `notices[].actions[]`는 닫힌 목록이라 재생성 버튼이 필요해지면 그 목록도 함께 봐야 한다.

### 이 초안을 지지하는 기존 발언

- **`contract-analysis-source-derived.md` §7.2-7** — 사후 timestamp 각인에 대해 「판단은 `evidence`, 발주는 `case`, 생성은 `recording`」이 이미 확정돼 있다. 아래 「권장 경계」는 새 원칙이 아니라 **같은 패턴을 `PLATE_IMAGE`에 적용하자는 제안**이다.
- **이슈 [`#40`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/40) A절** (recording Owner 정철원, closed) — `da_u001_plate_image`의 `byte_size: 172032`를 「고정 보장값이 아니라 fixture 예시값으로 보고, 실제 구현에서는 **생성된 파일의 측정값을 사용하겠습니다**」라고 답했다. 이 초안의 「실제 byte_size는 recording이 측정해 제공한다」와 일치한다. 다만 **무엇을 입력으로 어떻게 발주받아 생성하는지는 그 답변의 범위가 아니었다.**
- **이슈 [`#39`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/39) · [`#40`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/40) C절** — `crop_ref`의 Producer 경계를 정철원 확인 항목으로 남겼고 「recording은 crop identity를 생성하거나 해석하지 않는다」로 닫혔다. 이 초안이 `export_plate_image(crop_ref)` 형태를 금지하는 근거가 여기까지 이어진다.
- **`adr-first-completion-owner-decisions.md` §3.9** — K1이 단독으로 확정하지 않는 항목으로 「`PLATE_IMAGE` 생성 요청과 크기 측정의 실제 cross-module 호출 흐름」을 명시하고 이 초안을 가리킨다. 이 이슈는 **이미 등록된 후속 항목**이지 새로 만든 논점이 아니다.

### 제품 쪽 입력 (Q1·Q3과 직접 연결)

`core-user-flow.md` §12 「번호판」 화면은 상태가 아직 `AI 추정`인 시점에 `[번호판 이미지 보기]`를 노출하고, 출처를 「영상에서 가장 선명한 번호판 장면과 **주변 장면을 함께** 확인」으로 적는다. Q1(순수 crop인가 주변 맥락 포함인가)과 Q3(사용자 확인 전에 발주하는가)에 대한 제품 쪽 제약이다. 다만 이것은 화면 설명이지 생성 입력 계약이 아니므로 이슈에서 그대로 답으로 쓰지 않는다.

### 질문을 9개에서 5개로 줄인 근거

초안 1차에는 질문이 9개였다. 재검토에서 4개는 **이미 답이 있거나 다른 절과 중복**이라 뺐다.

| 뺀 질문 | 왜 뺐나 | 어디로 옮겼나 |
| --- | --- | --- |
| 「생성 입력은 기존 `frame_ref`와 명시적 영역 값만으로 충분한가?」 | Q2의 Yes/No 껍데기다. 실제로 답이 필요한 것은 `bbox_xywh`의 성격이고, Yes/No 기록 자체는 이미 완료 조건 1번이 요구한다 | Q2에 흡수 |
| 「부족하다면 어떤 최소 crop locator가 필요한가?」 | 위 질문의 후속이고, 완료 조건 2번(「부족하면 필요한 최소 Contract 변경과 Owner가 특정되어 있다」)과 같은 말이다 | Q2에 흡수 |
| 「재압축·재생성 시 기존 DerivedAsset은 보존하고 새 ref로 연결하는가?」 | **이미 확정된 원칙이다.** `contract-analysis-source-derived.md` §6.7(「recording은 provenance가 달라지면 새 `IncidentClip`을 발급한다. 기존 clip을 mutate하지 않는다」) · §7.2 invariant 1·4·5 · `crop_ref` identity 규칙(「id를 재사용하지 않는다」)이 같은 패턴을 이미 닫아 뒀다. 다시 묻는 것은 결정된 사안을 되묻는 것이다 | 완료 조건(「재생성 시 과거 자산을 조용히 mutate하지 않고…」)으로 유지 |
| 「이미지 format·quality·resize 방식은 Contract가 아니라 recording Tech Spec에 둘 수 있는가?」 | 같은 계약 §10이 「proxy resolution/FPS/bitrate 임의 확정」을 금지하고 §11이 profile 값 목록을 Pending으로 남긴 선례가 이미 답이다. 질문 형태로 두면 열린 논점처럼 보인다 | 권장 경계의 기본값 + 범위 밖 |

남은 5개는 각각 답해야 할 Owner가 다르고, 어느 것도 기존 문서에서 답을 찾을 수 없었다.

### 결론

**게시할 가치가 있다.** 같은 질문을 다룬 이슈·계약 절·결정 문서가 레포에 없고, 반대로 K1 ADR §3.9가 이 항목을 열어둔 채 이 초안을 가리키고 있다. 그래서 제목을 **「경계 확정」에서 「기존 Contract로 충분한지 확인」**으로 바꿨다. 위 확인에서 드러난 것은 「계약이 틀렸다」가 아니라 「생성 입력·발주 경로·실패 code가 아직 어디에도 없다」이기 때문이다.

## 관련 근거

아래는 위 재검토에서 실제로 열어 확인한 것이다. 괄호 안은 확인한 위치다.

### 계약

- [`contract-plate-overlay-readout.md`](../../../architecture/contracts/contract-plate-overlay-readout.md) — §3 `crop_ref` identity(2026-09-10 확정, Decider 신유민): identity는 `(frame_ref, bbox, 추출 파라미터)`이고 **opaque identity이지 조회 handle이 아니며** 발급 주체는 `readout`이다. 「나중에 `recording`이 crop 자산을 발급하게 되면 `PLATE_IMAGE`처럼 별도 필드로 받는다」가 미래 항목으로 남아 있다. §6 `PlateReadout` 예시에서 영역 값은 `target_association.associated_region.bbox_xywh` 한 곳뿐이고 `best_frame`에는 `frame_ref`·`crop_ref`·`quality`만 있다 — Q2의 출발점
- [`contract-analysis-source-derived.md`](../../../architecture/contracts/contract-analysis-source-derived.md) — §6.6 `build_incident_clip` capability와 「case는 이미 결정된 interval을 전달하고 materialization option은 recording이 소유」 선례 · §7.2-7 각인 책임 분리 선례 · §7.3 `PLATE_IMAGE` role 등재 · §7.4 `transform_ref` 조회 가능성 보장 · §7.5·§9 failure code(Report Video만) · §11 Pending 8건(이 항목 없음)
- [`contract-source-asset-media-stream.md`](../../../architecture/contracts/contract-source-asset-media-stream.md) — canonical `AssetFacts`와 `lookup_asset_facts` 전달 경계, `availability` 3값 부여 조건, `byte_size` nullable 규칙
- [`contract-requirement-report-package.md`](../../../architecture/contracts/contract-requirement-report-package.md) — §8.4 Source/Derived 분리와 `plate_image_ref` optional 규칙, FINAL_PACKAGE ASSET 판정, 자산 사실 계약을 가리키는 포인터 갱신 주석
- [`contract-job-record-case-view.md`](../../../architecture/contracts/contract-job-record-case-view.md) — A절 §7 `JobRecord.kind` 등재값 `COARSE_SEARCH`·`PLATE_READ`·`OVERLAY_TIME_READ`·`FINE_VERIFY`·`REPORT_VIDEO_EXPORT`(열린 enum, plate image 없음) · B절 `notices[].actions[]` 닫힌 7종과 `GENERATE_REPORT_VIDEO → kind=REPORT_VIDEO_EXPORT` 발주 매핑

### 구조·제품

- [`module-architecture.md`](../../../architecture/module-architecture.md) — 모듈 1 `recording` ③(「Report Video / Plate Image 같은 파생 자산 생성」이 책임으로는 적혀 있음) · ⑥ Public Capability(`export_report_video`만 존재) · ⑩ Owner Review Required(이 항목 없음), 모듈 3 `readout` ③ Public Capability, 모듈 5 `case` ③ 책임, §3-3 사건 영상 생성 책임, §3-4 Plate Pipeline, §3-7 최종 Package 정책
- [`core-user-flow.md`](../../../product/core-user-flow.md) — §12 「번호판」 화면의 `[번호판 이미지 보기]`와 출처 문구

### evidence 쪽 기록

- [`adr-first-completion-owner-decisions.md`](../adr/adr-first-completion-owner-decisions.md) — §3 K1 전체(대상·상한·경계값·`UNKNOWN`/`BLOCK`·내부 목표 미설정) · §3.9 「K1이 단독으로 확정하지 않는 것」에 이 항목이 등록돼 있고 이 초안을 가리킴
- [`10_first-completion_decisions_and_integration_2026-09-13.md`](./10_first-completion_decisions_and_integration_2026-09-13.md) — K1 결정 맥락과 통합 단계 작업 분류

### 구현·fixture

- `src/daesingo/evidence/requirements.py` — 자산 크기 검사는 `package.asset.report_video.size` 하나(`byte_size=null → UNKNOWN`, 상한 초과 → `BLOCK`, `measurement.actual/limit/unit` 출력). Package 조립은 주입된 `assets`에서 role `PLATE_IMAGE`를 찾아 `availability=AVAILABLE`일 때만 `plate_image_ref`를 채운다 — **evidence가 recording을 호출하지 않는다는 경계는 이미 코드에 있다**
- `data/mock/recording/scenario_happy_001.json` · `scenario_unknown_abstain_partial_001.json` — `da_*_plate_image`의 `source_refs`는 `incident_clip`, `transform_ref=null`, `AssetFacts.byte_size`는 각각 `184320` · `172032`(둘 다 `availability=AVAILABLE`)
- `data/mock/readout/scenario_happy_001.json` — `best_frame.frame_ref=fr_h001_plate1` · `crop_ref=crop_h001_001` · `associated_region.bbox_xywh=[820,410,176,68]`
- `data/mock/case/*.json` — `job_records[].kind`에 plate image 생성 발주 없음

### GitHub 이슈

- [`#40`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/40) — recording 4차 검수(정철원, closed). A절 2·3에서 `da_u001_plate_image`와 `AssetFacts`를 승인하며 byte_size는 생성 후 측정값을 쓰겠다고 답했고, B절 1의 recording Pending 5건에 이 항목은 없다. C절에서 recording이 crop identity를 생성·해석하지 않음을 확인
- [`#39`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/39) — evidence/common-runtime 4차 검수. `crop_ref` Producer 경계의 최종 확인을 정철원 항목으로 남김
- [`#31`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31) A-3 · [`#30`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/30) B-2 — `crop_ref` identity 확정 경위

## 게시 결과 (2026-09-13)

[이슈 #47](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/47) · label `question` · assignee 정철원·신유민·유소연.

게시 전 확인 항목 처리:

- [x] 기존 관련 이슈와 중복 여부 확인 — `#15`-`#41` 본문·코멘트 전수 확인, 중복 없음(위 「레포 내 중복·기존 근거 재검토」)
- [x] 기존 Contract로 충분한 구현 질문인지, Contract 변경 제안인지 제목과 라벨을 구분 — 제목을 **「충분성 확인」**으로 수정, label은 `question`
- [x] 제안 문구가 합의 완료로 오해되지 않게 확인 — 「권장 경계」 도입부에 「아직 cross-module 결정이 아니라 이 이슈의 제안」을 명시
- [x] 정철원·신유민·유소연 assignee 지정 — 지정됨. 본문에서도 질문별로 담당 Owner를 @멘션으로 표시했다(Q1 신유민·김준영 / Q2 신유민 / Q3 유소연 / Q4 정철원 / Q5 유소연·정철원)

게시 시 이슈 본문에 추가한 것(이 문서에는 없는 부분):

- **참고 문서 열람 안내** — evidence ADR · `src/daesingo/evidence/**` · 이 초안은 아직 `develop`에 없어 링크가 열리지 않고 PR 병합 후 열람 가능하다는 안내. 그래서 용량 정책 값과 맥락을 이슈 본문에 인용해 **외부 문서를 열지 않아도 답할 수 있게** 했다.
- 참고 문서를 「지금 열람 가능(`develop` blob URL)」과 「PR 병합 이후 열람 가능」으로 분리
- 질문별 담당 Owner @멘션

이후 논의는 이슈에서 진행한다. 이 문서는 원본 초안과 재검토 기록으로 남긴다.
