# Real E2E 실행 기록 — 월요일 대표 영상 (`20260620_141956_EVT_1`)

**날짜:** 2026-09-22 · **실행자:** 유소연(Claude Code 보조) · **브랜치:** `fix/case-search-stream-context-wiring`

**목적:** PM 전달사항(`doc/real-e2e-protocol.md`, git 미커밋)에 따라 실제 대표 영상 1개를
Recording→Search(Elice/Gemini)→Readout→Evidence까지 실제 함수·실제 외부 호출로 통과시킨다.
정확도 평가가 아니라 "각 실제 Producer가 실제로 호출되고 그 결과가 다음 단계로 전달되는가"를
증명하는 것이 목표다.

**입력 영상:** `20260620_141956_EVT_1.avi` (로컬 경로 `doc/`, git 미커밋)

## 사전 준비

- [x] PR #128(search)·#129(recording)·#130(readout)·#113(PaddleOCR) develop 병합 확인
- [x] `.env`에 `GEMINI_API_KEY`/`DAESINGO_GEMINI_BASE_URL`/`DAESINGO_GEMINI_MODEL` 값 존재 확인(값은 로그에 남기지 않음)
- [x] ffmpeg/ffprobe 설치 — `conda install -c conda-forge ffmpeg`가 멈춘 듯해서(장시간 무응답)
  중단하고 `pip install static-ffmpeg`로 대체. 정적 바이너리를 받아 PATH에 얹었다
  (`static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()`). **나중에 확인해보니
  conda 설치도 실제로는 끝까지 돌아 있었다** — 그런데 conda-forge 4.3.1 빌드는 이 영상을
  480p로 transcode할 때 `RecordingCapabilityError`(media/frame coverage 불일치)로 **매번**
  실패하고, static-ffmpeg의 8.0.1 essentials 빌드는 **매번** 성공한다(재현 확인, 우연 아님).
  ⚠️ **PATH에서 어느 ffmpeg가 먼저 잡히는지에 따라 이 레포의 real-video 테스트/스크립트
  결과가 갈린다** — `tests/case/test_real_video_pipeline.py` 상단 주석에도 남겨뒀다.
- [x] `opencv-python`/`paddlepaddle`/`paddleocr` 설치 — 1차 시도는 `cv2.pyd` 파일 접근 거부로
  일부 실패(`WinError 5`, 다른 프로세스가 파일을 잡고 있었던 것으로 보임). 재시도로 해결.

## build_real_video_evidence_bundle() 코드 작성 중 발견한 것들

### 1. search에 실제 service 주입 경로가 처음 짠 구조와 안 맞았다

처음엔 "candidate.span으로 좁힌 AnalysisSource 하나만 만들면 된다"고 가정했는데,
`RecordingAnalysisSourceResolver`가 `scope_sources`(scope_id → AnalysisSource ref)로
coarse 검색 **이전에** AnalysisSource가 이미 있어야 하는 구조라 candidate가 나오기도
전에 AnalysisSource를 만들어야 했다. → **전체 영상 범위로 AnalysisSource를 한 번만
만들고**, coarse/fine 둘 다 이걸 재사용하도록 고쳤다(Fine이 candidate.span으로 좁히는
건 search 자신의 `MediaPreparer`가 내부에서 한다 — case가 두 번째 AnalysisSource를
따로 만들 필요가 없었다).

### 2. `RecordingOcrProvider`(#130)를 쓰려 했으나 아직 못 쓴다

`RecordingOcrProvider`는 `IncidentClipFrames`를 감쌀 `plate_reader`/`overlay_reader`
콜러블을 생성자로 받는데, `paddle_provider.py`엔 그 모양(callable)의 함수가 없다 —
있는 건 `frame_source.frames(clip_ref)` 인터페이스를 기대하는 `PaddleOcrProvider`
클래스뿐이다. 새 adapter 함수를 직접 만드는 건 readout 소유 영역을 침범하는 것이라
만들지 않았다. 대신 이미 실측된 `PaddleOcrProvider(LocalVideoFrameSource({ref: path}))`
경로(`scripts/run_readout_real.py`와 동일 패턴)를 그대로 썼다 — clip 범위가 아니라
파일 전체의 30/50/70%를 본다는 제약이 있지만, 이번 목표(실제 pixel→실제 OCR)엔 지장 없다.

## 실행 1회차 — 2026-09-22

**명령:** (scratchpad) `python run_real_e2e.py` — `build_real_video_evidence_bundle(case_id=, local_video_path=doc/20260620_141956_EVT_1.avi, case=, scope_id=)`

**결과: 부분 성공 후 실패.**

| 단계 | 결과 |
| --- | --- |
| `register_local_source()` (ffprobe 실제 실행) | ✅ 성공 |
| `create_relative_timeline()` | ✅ 성공 |
| VIDEO stream 유일성 검증 | ✅ 성공 |
| `prepare_analysis_source()`(전체 영상) | ✅ 성공 |
| **Elice/Gemini Coarse 실제 호출** | ✅ 성공 — candidate 1건 생성 |
| **Elice/Gemini Fine 실제 호출** | ✅ 성공(API 응답은 받음) |
| Fine 응답의 시간 정합성 검증(`search/fine.py::_rebase_temporal_facts`) | ❌ **실패** |

**실패 원문:**
```
daesingo.search.smoke_errors.ProviderPayloadError: Fine temporal offset outside candidate window
```

**무슨 뜻인가:** search 자신의 `verify_fine()`이 Fine 응답의 `at_offset_ms`를 원본
시간으로 rebase한 뒤, 그 값이 **Coarse가 찾은 `candidate.span.start_ms~end_ms` 안에
있는지 검증**한다(`fine.py:62-64`). 이번 실행에서는 Fine이 돌려준 시간이 그 범위
밖이었다 — Coarse와 Fine이 서로 다른 순간을 가리켰다는 뜻이다.

**case 쪽 배선 문제인지 확인:** `candidate`는 `search_candidates()`가 돌려준 객체를
그대로(재계산 없이) `verify_visual_with_stream_context()`에 넘겼다 — case가 중간에
값을 바꾸거나 다시 계산하지 않았다. 즉 이 불일치는 **search 자신의 coarse↔fine 결과
사이의 불일치**이지 case의 배선 버그가 아닌 것으로 보인다.

**분류(프로토콜 §12 기준):** "Contract 변경/모듈 책임 경계/여러 Owner 합의가 필요한
문제"에 가깝다 — case가 `fine.py`의 검증 허용 범위를 임의로 넓히거나 우회하면 search
소유 정책을 침범한다. **큰 문제로 분류하고 Owner(서어진) 확인 필요.**

**멈춘 이유:** Elice/Gemini 호출은 유료라, 같은 원인으로 또 실패할지 모른 채 재시도를
반복하면 비용만 나간다. 여기서 멈추고 사용자에게 보고했다.

## 실행 2회차 — 2026-09-22 (사용자 지시로 재시도)

**결과: 정확히 같은 지점에서 정확히 같은 에러로 실패.**
```
daesingo.search.smoke_errors.ProviderPayloadError: Fine temporal offset outside candidate window
```

**1회차와 다른 점 없음** — 같은 파일·같은 코드 경로. 두 번 다 같은 이유로 실패했다는
것은 모델 응답의 우연한 변동이 아니라 **구조적으로 재현되는 패턴**이라는 뜻이다.

**재시도 전 `search/fine.py` 원문을 다시 읽어 원인을 좁혔다(추가 비용 없이):**

```python
start_sec = max(0.0, candidate.span.start_ms / 1000 - config.fine_padding_sec)
end_sec   = min(source.duration_sec, candidate.span.end_ms / 1000 + config.fine_padding_sec)
# Fine에는 이 [start_sec, end_sec] 패딩된(±fine_padding_sec=4.0초) 구간을 보여준다
...
# 그런데 검증은 패딩 없는 원래 candidate.span.start_ms~end_ms 안에 있어야 한다고 요구한다
if not candidate.span.start_ms <= rebased <= candidate.span.end_ms:
    raise ProviderPayloadError("Fine temporal offset outside candidate window")
```

**해석:** Fine은 모델에게 candidate 구간보다 **넓게(±4초) 패딩된** clip을 보여주고
정확한 순간을 짚어달라고 요청하는데, 검증은 그 결과가 **패딩 없는 좁은 coarse 구간
안**에 있어야만 통과시킨다. 즉 coarse가 잡은 구간이 실제 사건 순간보다 조금이라도
좁거나 어긋나 있으면, Fine이 패딩된 넓은 화면에서 찾은 "더 정확한" 순간은 구조적으로
항상 이 검증에 걸린다. 두 번 다 똑같이 실패한 것과 정합적인 설명이다.

**결론:** case의 배선이 아니라 **search 내부의 coarse↔fine 정합성 정책** 문제로 보고,
세 번째 유료 재시도는 보류한다. 서어진(search Owner) 확인이 필요한 지점 —
`docs/management/`가 아니라 GitHub Issue로 만들어 전달 예정(프로토콜 §12 "큰 문제"
분류). → **이슈 #132로 등록 완료.**

## 다운스트림 무료 dry-run — 2026-09-22 (search Coarse/Fine만 stub, 나머지 전부 real)

**목적:** 유료 재시도 전에 IncidentClip~EvidenceRecord 구간에 다른 버그가 있는지
무료로 먼저 잡는다. Coarse/Fine만 `search_module.search_candidates`/
`verify_visual_with_stream_context`를 스텁으로 바꿔서 실행했고, `register_local_source`
~`create_relative_timeline`~`prepare_analysis_source`~`build_incident_clip`~
readout(PaddleOCR 실제 실행)~`observe_time_sources`~`assemble_evidence`~
`evaluate_requirements`는 전부 real 함수다. **이건 Real E2E 증빙이 아니다** —
search 실제 호출이 없다. 순수하게 case 코드의 다운스트림 배선 점검용.

### 발견·수정한 실제 버그 2건

**1. `build_incident_clip()`이 로컬 원본에서 `incident_materializer` 없이는 항상 실패한다.**
```
RecordingCapabilityError: 실행 중인 단일 VIDEO 생성 설정이 필요합니다
```
`RecordingService(analysis_materializer=...)`만 넘기고 있었는데, local source의
`build_incident_clip()`은 **별도의** `incident_materializer`(`LocalIncidentMaterializer`)가
필요했다(`recording/service.py:606`). `prepare_analysis_source()`용
`analysis_materializer`와 `build_incident_clip()`용 `incident_materializer`는 서로
다른 설정이라는 걸 문서만 보고는 몰랐다 — 실행해봐서 발견했다. 같은 인코딩값
(480p/veryfast/crf23)으로 `IncidentClipEncoding`을 만들어 추가했다.

**2. `lookup_asset_facts()`는 로컬로 만든 `analysis_source`/`incident_clip`에 대해
AssetFacts를 등록하지 않는다.**
```
RecordingCapabilityError: 등록되지 않은 자산 ref입니다
```
`prepare_analysis_source()`/`build_incident_clip()`의 로컬 경로는 결과를
`self._local_analysis`/`self._local_clips`에만 저장하고 `add_asset_facts()`를
안 부른다 — `source_asset`만 `inspect_local_source()`로 즉석 조회되는 특수
경로가 있다. `happy_001` fixture도 원래 `analysis_source`는 asset_facts에
넣지 않는다는 것까지 확인했다(fixture와 다른 동작이 아니었다). `asset_facts_real`
목록을 `source_asset` 하나만으로 좁혔다 — **recording 쪽에 로컬 analysis_source/
incident_clip의 AssetFacts 등록이 없다는 것 자체는 잠재적 gap으로 남는다**(지금
당장 case 실행을 막지는 않아서 별도 이슈를 내지는 않았다).

### 실행 결과 — 끝까지 성공

```
EvidenceRecord 생성 ✅
  occurred_at.value = "2026-06-20T14:19:56+09:00"
  occurred_at.source.kind = "readout.overlay_ocr"  ← 실제 PaddleOCR이 영상 속
    타임스탬프 overlay를 실제로 읽어서 나온 값이다(스텁 데이터가 아니다 —
    stub은 candidate.span/visual_evidence만 대체했고 overlay 판독은 100% real).
    파일명(20260620_141956)과 정확히 일치 — 실제 블랙박스 화면 시각 표시를
    제대로 읽은 것으로 보인다.
RequirementReport(EVIDENCE): overall=UNKNOWN
  vehicle_number: UNKNOWN(재판독 대기) · occurred_at: PASS · visual_event: PASS
  · location: WARN(위치 미확보)
RequirementReport(FINAL_PACKAGE): overall=UNKNOWN
  situation_response 미확보·report_video 없음 등으로 여러 UNKNOWN(알려진 단순화,
  모듈 docstring 그대로) · deadline: WARN(실제 현재 시각 기준 기한 초과 —
  W6 happy_001 실행 때와 같은 정상 판정)
ReportPackage: package_error="package.requirement_not_ready"(PackageNotReady,
  알려진 단순화 2 그대로 — 실패 아님)
rec_service.close() ✅
```

**의미:** search의 Coarse/Fine만 해결되면(이슈 #132), 지금 이 다운스트림 코드는
이미 실제 데이터로 끝까지 검증된 상태다 — 세 번째 유료 시도에서 또 다른 코드
버그로 막힐 위험은 크게 줄었다.

## CaseView/Web 연결 — `RealVideoAdapter` 신설 (2026-09-22)

**문제:** `build_real_video_evidence_bundle()`은 `EvidenceBundle`만 돌려주고
candidate 선택을 자체적으로(`candidates[0]`) 해버려서, case의 상태 기계
(`case.select_candidate()`)와 `CaseView` 조립(`service.build_view_from_adapter()`)에
연결할 방법이 없었다. fixture 경로(`RealAdapter`)와 같은 흐름을 타려면 별도
adapter가 필요했다.

**한 것:**
1. `real_e2e.py`를 3단계로 쪼갰다 — `prepare_real_video_context()`(candidate
   탐색 전, 전체 영상 범위 AnalysisSource+real service 조립 1회) /
   `get_real_video_candidates()`(Coarse 실제 호출) /
   `build_evidence_for_real_video_candidate()`(선택된 candidate로 Fine~evidence).
   `build_real_video_evidence_bundle()`은 이 3개를 이어붙인 편의 함수로 남겼다
   (기존 스모크 스크립트 호환, 동작 동일함을 재실행으로 확인).
2. `adapters.py`에 `RealVideoAdapter` 추가 — `RealAdapter`와 같은
   `ModuleAdapter` 프로토콜을 실제 영상 백엔드로 구현. `case.select_candidate()`가
   고른 candidate로만 evidence를 계산한다(`RealAdapter`와 같은 원칙).
3. `scripts/dump_real_video_caseview.py` 추가 — `dump_real_caseview.py`(fixture)와
   짝. `data/real/case/real_e2e_monday_video.json`에 떨어뜨리면 web이 바로 읽는다.
4. `tests/case/test_real_video_pipeline.py` 추가(2건, search만 stub) — 실제
   ffmpeg/paddleocr/영상 파일 없으면 skip.

**검증(무료 dry-run, search만 stub):** `RealVideoAdapter`로
`receive_search_candidates()` → `case.select_candidate()` →
`build_view_from_adapter()`까지 실행 — **`stage=READY`, `event_time_display.value
="2026-06-20T14:19:56+09:00"`(실제 overlay OCR), `info_state="INFO_SOURCE_VERIFIED"`.**
CaseView가 web이 그대로 읽을 수 있는 모양으로 끝까지 나온다.

**남은 것:** 이슈 #132가 풀려야 `dump_real_video_caseview.py`를 stub 없이 그대로
돌려서 진짜 `data/real/case/` 산출물을 만들 수 있다. Web 업로드 API(protocol §8)는
이번에 손대지 않았다 — 프로토콜 자체가 "시간 부족하면 `Real E2E 실행 → data/real/case
JSON → Web 렌더`까지만 확인해도 된다"고 명시한 최소 기준에 맞춘 것이다.

## 실행 3회차 — 2026-09-22 (PR #133 병합 후 재시도)

서어진의 PR #133(`fix/search-fine-padded-window`, 이슈 #132 수정 — `at_offset_ms`를
절대시각으로 rebase하지 않고 clip 상대시간으로 유지, 패딩 구간도 유효 범위로 인정)
병합 확인 후 재시도.

**결과: 이슈 #132는 확실히 해결됨.** Coarse·Fine 둘 다 real Elice/Gemini 호출
성공, coarse/fine 시간 정합성 검증(`_clip_relative_temporal_facts`)도 통과 —
1·2회차에서 막혔던 지점을 완전히 통과했다.

**대신 그 다음 단계에서 새 문제로 막힘(#132와 무관, 별개 발견):**
```
pydantic_core._pydantic_core.ValidationError: 2 validation errors for TemporalFact
evidence_refs.0
  String should match pattern '^fr_[A-Za-z0-9_-]+$' [input_value='00:04']
evidence_refs.1
  String should match pattern '^fr_[A-Za-z0-9_-]+$' [input_value='00:05']
```
`TemporalFact.evidence_refs`는 계약상 `fr_...` 형태의 opaque FrameRef여야 하는데
(`search/visual.py` `FrameRef = Annotated[str, Field(pattern=r"^fr_[A-Za-z0-9_-]+$")]`),
이번 real 응답에서 **Gemini가 `"00:04"`/`"00:05"` 같은 원시 타임스탬프 문자열을
그대로 돌려줬다.** search의 새 `_clip_relative_temporal_facts()`(PR #133)가 이
값을 변환·검증 없이 그대로 `TemporalFact`에 넣어서 pydantic이 막았다.

**case 배선 문제 아님** — search의 프롬프트가 모델에게 evidence_refs 형식을
충분히 명확히 지시하지 못했거나, 모델 응답을 `fr_...`로 변환하는 단계가
없는 것으로 보인다. 둘 다 search 소유 영역이라 case가 대신 고치지 않는다.

**세 번째 유료 호출까지 완료 — 다음 재시도는 사용자 확인 후 진행.**

## 실행 4회차 — 2026-09-22 (PR #133 merge 후 재시도 확인용)

**결과: 정확히 같은 `evidence_refs` 문제 재현** — `"00:03"`/`"00:04"`(값만 다름,
패턴 동일). 3·4회차 연속 재현이라 우연이 아니라 판단, **이슈 #135로 등록.**
토큰 사용량: Coarse 1,722/1,581, Fine 1,073/508 (합계 input 2,795 / output 2,089).
`SearchLedger.records()`를 매 실행마다 JSONL로 남기도록
`docs/modules/case/experiments/real-e2e-usage-log.jsonl`을 추가함(성공/실패 무관
— `fine.py`의 `ledger.append()`가 파싱 실패보다 먼저 일어나서 실패한 실행도
토큰 사용량은 건질 수 있다).

## 실행 5회차 — 2026-09-22 (이슈 #135 PR #136 merge 후 재시도)

**결과: 이슈 #135 확실히 해결.** PaddleOCR 실제 실행, real Fine 호출 모두
성공, `evidence_refs` 문제 재현 안 됨(서어진 수정대로 빈 tuple로 나옴).

**대신 완전히 새로운 모듈(evidence)에서 막힘:**
```
daesingo.evidence.errors.ContractInputError: only an UNCERTAIN VisualEvidence may produce a null visual event
```
`search.VisualEvidence`의 `verification`은 `NOT_OBSERVED`/`UNCERTAIN` 둘 다
`visual_event_type=null`을 허용하는데, `evidence/assembly.py`의
`_event_values()`는 `UNCERTAIN`만 처리한다. 이번이 처음으로 real Coarse가
찍은 candidate를 real Fine이 "위반 확인 안 됨"(`NOT_OBSERVED`)으로 판정한
경우였던 것으로 보인다 — fixture 시나리오들은 이 조합이 없었다.

**추가 유료 호출 없이 synthetic 값으로 재현 확인** —
`_event_values({"verification": "NOT_OBSERVED", "visual_event_type": None, ...}, None)`
호출만으로 같은 에러가 남. **이슈 #137로 등록**(재현 코드도 댓글로 첨부).

**case는 대신 고치지 않음** — `NOT_OBSERVED`를 `UNCERTAIN`과 같이 취급할지,
별도 상태가 필요한지는 evidence(김준영) 소유 판단.

## 토큰 절약 원칙 (5회차 이후 정리)

1. **코드만 읽어도 원인이 확실하면 절대 재호출하지 않는다.** downstream(evidence/
   requirement/CaseView) 버그는 최소 synthetic 값으로 무료 재현 가능한 경우가
   많다(#137이 그 예).
2. **모델의 실제 응답 내용 자체가 궁금할 때만 호출**하고, **그 결과는 반드시
   저장해서 두 번 다시 안 쓴다.** `build_evidence_for_real_video_candidate()`/
   `build_real_video_evidence_bundle()`에 `on_visual_result` 콜백을 추가해서,
   Fine 응답을 받은 직후(이후 단계가 실패하기 전에) candidate·visual_evidence를
   `docs/modules/case/experiments/real-e2e-captures/`에 저장한다 —
   다음에 같은 상황을 다시 보고 싶으면 재호출 없이 replay하면 된다.


## 실행 6회차 — 2026-09-22 (이슈 #137 수정 후 재시도, 성공)

**결과: 성공.** PR #142(evidence `classify_visual_evidence()` 신설)와 그 case
쪽 후속 정합화(`build_evidence_for_real_video_candidate()`에 동일 분류 적용,
PR #131 rebase 후 커밋)를 마치고 재시도했다.

```
Disposition: decision=NOT_ASSEMBLED, verification=NOT_OBSERVED,
             reason_code=evidence.visual_event.not_observed
assembled: False
```

5회차와 같은 candidate가 다시 `NOT_OBSERVED`로 나왔지만, 이번엔 `ContractInputError`
없이 정상 종료했다 — `EvidenceRecord`/`RequirementReport`/`ReportPackage` 전부
`None`이고 `VisualEvidence`·Fine `AnalysisRun`·usage는 그대로 보존됐다
(`on_visual_result` 캡처: `real-e2e-captures/run-20260922-224602.json`). 이게
PR #142 본문이 정의한 negative 경로 성공 기준(Record/Report/Package 미생성,
예외 없음, VisualEvidence·Usage 보존)과 정확히 일치한다 — **case가 사용자에게
지시받은 이번 real E2E 목표는 이 negative 경로 확인으로 충분하다고 판단, 여기서
종결한다.** OBSERVED까지 가는 자동 후보 순회는 의도적 비범위(§ADR-EVIDENCE-007 §7).

실제 유료 호출 2건(Coarse+Fine), input_tokens=2818/output_tokens=1096,
`real-e2e-usage-log.jsonl`에 기록.

**환경 참고 — ffmpeg 빌드.** 이 실행 시점에 PATH 최우선 `ffmpeg`가 conda의 4.3.1이라
transcode가 실패했다(이전에 이미 발견한 그 버전 문제, 정철원에게 보고됨) —
`static_ffmpeg`(pip 패키지가 받은 8.0.1 essentials 빌드) 경로를 PATH 맨 앞에
둬서 우회했다. `daesingo.recording.materialization`은 `ffmpeg`/`ffprobe`를
bare 이름으로 호출해 PATH 탐색에 의존하므로, 이 환경에서 다시 실행할 땐 매번
PATH 순서를 확인해야 한다.
