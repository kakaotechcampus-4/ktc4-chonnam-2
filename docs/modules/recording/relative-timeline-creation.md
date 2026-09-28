# 단일 원본의 상대 Timeline 생성 — 두 번째 기능 단위

## 병합 영향 (627cc25 기준)

- root Python 3.12 표준화가 #111로 반영됐다. `pyproject.toml`, `uv.lock`,
  `.python-version`, setuptools와 Windows tzdata 설정을 그대로 사용한다.
  CI는 Python 3.12로 변경됐지만 현재 workflow는 여전히 boundary/contract 검사만 실행한다.
- Recording 구현·Canonical 모델·시간축 계약·3주 설계서는 이번 develop 병합으로 변하지 않았다.
- Case의 실제 선택 candidate/selection_rev, correction_records, location_hint 전달과
  후보 at_provenance 수정이 들어왔다. 기존 fixture 기반 `real_e2e`를 실제 영상 연결로
  해석하지 않는다. correction 시 media/provider 재호출 분리는 여전히 Case 후속이다.
- Web은 `data/real/case/*.json`을 읽을 수 있다. 현재 dump 실행기도 fixture를 사용한다.
  Recording이 이를 수정하거나 READY/ReportPackage를 생성하지 않는다.
- 설계서 OI-1(D1/D2)은 미확정 상태다. 이번 시간축 생성은 그 의미를 정하지 않는다.

## 공개 호출

```python
from daesingo.recording import RecordingService

service = RecordingService()
registered = service.register_local_source(local_video_path)
timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
same_revision = service.get_timeline(timeline.timeline_id, timeline.revision)
latest = service.get_latest_timeline(timeline.timeline_id)
```

`create_relative_timeline(source_asset_ref: str) -> RecordingTimeline`은 같은 service의
registry에 등록된 Source 사실을 사용한다. 입력에 파일 경로, 수동 duration, datetime을
받지 않는다. 경로·파일명·날짜 추정값은 출력하지 않는다.

반환값은 기존 `recording-timeline/v1`이다.

- 새 opaque `timeline_id`, `revision=1`. 매 생성 호출은 독립적인 시간축이며 rebase가 아니다.
- Source 하나를 `[0, SourceAsset.duration_sec)`에 배치하며 원본의 stream refs를 모두 보존한다.
- `timeline_status=USABLE_RELATIVE_ONLY`, anchor value/ref는 `null`, anchor status는 `UNKNOWN`.
- `time_basis.mode`는 기존 relative-only fixture와 동일한 `ABSOLUTE_AND_RELATIVE`다.
  새 mode 값을 만들지 않으며 절대시각의 존재는 anchor/status로 판단한다.
- 이 기능은 시각 후보를 수집하지 않으므로 `time_source_candidates=[]`다.
  이는 원본에 시각 metadata가 없다는 판정이 아니다.
- `gaps=[]`는 단일 파일 배치에 파일 간 gap이 없다는 뜻이다. stream별 decode 가능성이나
  전체 파일 범위의 frame coverage를 보증하지 않는다.
- Source container duration과 각 stream duration을 동일시하지 않는다. 예를 들어 파일이
  60.033333초이고 한 video가 59.9초여도 해당 stream을 늘리지 않는다. audio duration의
  `null`도 그대로 둔다. stream별 구간 가용성 처리는 이후 `resolve_span` 구현 범위다.
- Timeline 저장·조회는 deep copy로 분리한다. frozen 모델 안의 list를 Consumer가 바꿔도
  저장된 revision을 바꾸지 못한다. 기존 revision 덮어쓰기 금지 규칙은 유지한다.

## 실패와 한계

- 미등록 source ref: 기존 `RecordingCapabilityError(code="UNKNOWN_REF")`.
- Source duration 미확인·0·비유한 값, Source 읽기 미확인, 참조 손상, video 없음,
  접근 불가 stream 존재: `ValueError`. 실패 시 Timeline을 저장하지 않는다.
- 등록된 snapshot에서 시간축을 계산한다. 원본을 다시 읽거나 변경하지 않는다.
  파일의 후속 변경·삭제 여부는 이 함수가 재검사하지 않는다.
- stream availability `UNKNOWN`은 decode 미검증 상태로 유지한다. 상대 시간축을 계산할 수
  있다는 사실만으로 `AVAILABLE`로 승격하지 않는다.
- 절대 anchor/TimeSourceCandidate, rebase, 다중 파일 연결, 실제 span 계산,
  AnalysisSource, clip/frame 생성, JobExecution 배선은 이번 범위가 아니다.
  따라서 생성된 Timeline의 임의 구간에 대한 `resolve_span`은 아직 제공되지 않는다.

## 재현 (root PowerShell / Python 3.12)

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m examples.recording_relative_timeline "D:\videos\sample.avi"
.venv/Scripts/python.exe -m pytest tests/recording/test_relative_timeline_creation.py -q

$env:DAESINGO_RECORDING_VIDEO = "D:\videos\sample.avi"
.venv/Scripts/python.exe -m pytest tests/recording/test_relative_timeline_creation.py -k opt_in -q
```

예제의 경로는 실제 로컬 경로로 바꾼다. 예제는 stdout에 계약 JSON만 출력하고 파일을
복사·저장하지 않는다. 생성 영상 smoke와 사용자 영상 opt-in 검증을 구분한다.
두 파일을 검사하려면 각각 별도로 호출한다. 파일명 순서로 이어 붙이지 않는다.
