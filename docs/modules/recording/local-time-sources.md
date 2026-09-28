# 실제 로컬 원본의 시간 관찰과 수동 anchor

RecordingService의 실행 내 관찰 저장소를 사용한다. Canonical Contract는
`docs/architecture/contracts/contract-recording-timeline-asset-span.md`를 따른다.
Candidate는 시각 관찰이며 최종 시각의 정확성이나 Evidence 판정을 의미하지 않는다.

## 공개 capability

```python
observer = LocalTimeSourceObserver(filename_offset="+09:00", mdr_century=2000)
service = RecordingService(time_source_observer=observer)
observed = service.observe_time_sources(source_asset_ref)
observed = service.get_time_sources(source_asset_ref)  # candidates와 checks tuple
candidate = service.get_time_source_candidate(candidate_id)
result = service.apply_filename_anchor(
    timeline_ref, candidate_id, overlay_matches=True, trusted=True,
)
```

`filename_offset`은 실행자가 주입하는 고정 UTC offset이며 필수 기본값이 없다.
위의 +09:00은 예제 설정이다. 호스트 timezone이나 파일명에서 추정하지 않는다.
Candidate.value는 offset-aware datetime이다. filename parser 식별자는
`source_detail`, 관찰한 basename은 `provenance.observed_from`에 기록한다.
전체 로컬 경로는 노출하지 않는다. candidate_id는 `tsc_`와 무작위 UUID로 발급한다.

| 조사 대상 | 지원 경계 | 실패/부재 |
| --- | --- | --- |
| FILENAME EVT | 정확한 YYYYMMDD_HHMMSS_EVT_<숫자>.avi 규칙 | 미지원 형식/offset 미설정은 UNSUPPORTED, 잘못된 날짜·시각은 PARSE_ERROR |
| FILENAME MDR | 별도 MDR_YYMMDD_HHMMSS.AVI 규칙, 실행자가 mdr_century를 100년 단위로 명시 | century 미설정은 UNSUPPORTED. 2000 설정의 26은 2026, 1900 설정의 26은 1926 |
| FILE_METADATA | ffprobe format.tags.creation_time의 명시적 offset 포함 ISO datetime | 필드 부재는 NOT_FOUND, naive/잘못된 값은 PARSE_ERROR |
| VENDOR_METADATA | 이번 단위에서 parser 미지원 | UNSUPPORTED |

확장자와 EVT/MDR 표기는 대소문자를 구분하지 않는다. container의 명시적 offset은
그대로 사용하고 filename 설정을 덮어씌우지 않는다. mtime은 시각 후보가 아니다.
null value Candidate, OCR/사용자 Candidate, confidence, VERIFIED 등은 만들지 않는다.
도구 실행 실패는 기존 TEMPORARY_FAILURE, 변경·소실 원본은 UNAVAILABLE capability 오류다.

## Anchor 경계

`overlay_matches=True`와 `trusted=True`를 둘 다 명시한 경우에만 해당 원본의
FILENAME 후보를 anchor로 사용한다. 이 입력은 사람이 대조한 결과를 실행자가 전달하는
것이며 Recording이 overlay OCR을 수행하거나 신뢰를 판단하는 기능이 아니다.
반환된 AnchorApplication에 manual flags와 applied를 별도로 보존한다.
Candidate.producer_checks.parse_valid는 파싱 성공 의미로 유지한다.

이번 지원 범위는 0초에서 시작하는 단일 원본 relative-only Timeline이다.
입력 timeline_ref는 현재 최신 revision이어야 하며, 과거 revision은 ValueError로 거부한다.
최신 revision으로 자동 치환하거나 과거 내용을 복사한 새 revision을 만들지 않는다.
성공하면 최신 revision+1로 USABLE Timeline을 저장하며 기존 revision은 변경하지 않는다.
불일치·미확인·신뢰 미지정·후보 없음은 입력 relative-only Timeline을 그대로 반환한다.
관찰/조회만으로 Timeline을 absolute로 바꾸지 않는다.

같은 service에서 재관찰하면 최초 관찰 ID와 Check를 재사용한다. 관찰과 anchor 적용은
원본 hash·크기·mtime을 검사한다. get 함수는 과거 관찰 snapshot 조회이며 원본을 재조사하지 않는다.
영속 저장소, 동시 revision 발급, 다중 원본 anchor, 기존 absolute Timeline 재조정은 후속 범위다.

## 재현

```powershell
.venv/Scripts/python.exe examples/recording_time_sources.py C:\normal\20260620_141956_EVT_1.avi --filename-offset=+09:00
```

기본값은 미확인으로 relative-only를 유지한다. 사람이 실제로 일치와 신뢰를 확인했을 때만
`--overlay-match match --trusted`를 추가한다. 음수 offset은 `--filename-offset=-04:30`처럼 지정한다.

```powershell
$env:DAESINGO_RECORDING_VIDEO='C:\normal\20260620_141956_EVT_1.avi'
.venv/Scripts/python.exe -m pytest tests/recording/test_local_time_sources.py -q -s -p no:cacheprovider
```

opt-in 검증은 +09:00을 명시적으로 설정하고 대표 파일에서 filename FOUND,
container NOT_FOUND, vendor UNSUPPORTED를 검사한다. anchor True/True 입력은
경계 검증을 위한 시뮬레이션이며 실제 overlay 확인 결과가 아니다.
실행 전후 SHA-256·크기·mtime을 비교하며 원본을 복사하거나 변경하지 않는다.
