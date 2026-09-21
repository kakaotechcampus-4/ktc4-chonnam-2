# 실행별 로컬 AnalysisSource materialization

Owner: 정철원. 3주 설계서 §5.3과 이슈 #95의
[D1·D2 합의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/95#issuecomment-5749597376),
[실측 보고](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/95#issuecomment-5756689492)를 따른다.
RemoteCopy는 사용하지 않는다. 최종 Canonical profile registry, TTL, Search 전송 방식은 변경하지 않는다.

## 공개 경계

```python
from uuid import uuid4
from daesingo.recording import AnalysisProfile, LocalAnalysisMaterializer, RecordingService

profile_ref = f"prof_{uuid4().hex}"
materializer = LocalAnalysisMaterializer({
    profile_ref: AnalysisProfile(height=480, preset="veryfast", crf=23),
})
with RecordingService(analysis_materializer=materializer) as recording:
    # register_local_source → create_relative_timeline → 명시적 VIDEO resolve_span 결과를 사용한다.
    source = recording.prepare_analysis_source(span, profile_ref, timeline_ref=timeline_ref)
    opened = recording.open_analysis_source(source.analysis_source_ref)
    with opened.stream:
        data = opened.stream.read()
```

- `prepare_analysis_source(span, profile_ref, *, timeline_ref=None) -> AnalysisSource`
- `open_analysis_source(ref) -> OpenedAnalysisSource(stream, content_type, byte_size)`
- `RecordingService.close()`와 context manager는 실행별 메모리를 해제한다.

실제 경로에는 timeline_ref가 필수다. AssetSpan에는 revision이 없으므로 원본 ref나 최신 Timeline에서
추정하지 않는다. 전달 revision의 공개 resolve_span 결과와 span 전체가 일치해야 한다.
기존 fixture의 2인자 prepare/open 동작은 유지한다.

잘못된 Timeline 참조·malformed span·COMPLETE 결과와 전달 span의 값 불일치는 입력 오류(ValueError)다.
원본 상태 때문에 해소 결과가 PARTIAL/FAILED이면 RecordingCapabilityError로 전달한다. 구체적인
failure.code를 우선 보존하고, NO_USABLE_SPAN 또는 PARTIAL의 단일 missing reason은 그 reason을 code로
보존한다. 원인이 복수이면 기존 failure.code 또는 TEMPORARY_FAILURE를 사용하며 새 taxonomy를 만들지 않는다.

profile configuration은 실행 조립 시 Recording에 주입한다. 소비자는 opaque ref만 전달하며 문자열을
파싱하지 않는다. 위 480p·H.264·MP4·veryfast·CRF23·yuv420p·audio off·faststart는 월요일 시험 후보다.
고정 Canonical profile 이름이나 registry 목록을 만들지 않는다. source aspect ratio에 맞춰 짝수 width를 계산한다.

```powershell
uv run --locked python -m examples.recording_analysis_source <로컬영상> --video-index 0 --start 3.7 --end 18.4
```

예제는 필수 VIDEO 순번에서 실제 ref를 얻고 공개 함수를 호출한다. 출력에는 요청 span, 실제 계약 객체,
content_type/크기/hash/재사용 여부만 담는다. 영상 bytes·경로를 출력하지 않는다.

## frame 경계와 metadata

원본의 지정 VIDEO를 ffprobe로 decode해 정수 timestamp·duration과 time base를 읽는다.
첫 frame을 source-local 0으로 정규화하고 **frame 시작 시각이 요청 [start,end) 안에 있는 frame**을 선택한다.
시작/끝 frame index로 trim하고 timestamp 간격을 유지하며 재인코딩한다. 오디오·subtitle·data·원본 metadata를 제외한다.

- `timeline_range`: 실제 선택한 첫 frame 시작부터 마지막 frame coverage 끝까지를 원본 Timeline에 투영한다.
  요청과 다를 수 있다. 끝 frame의 coverage가 요청 end를 넘을 수도 있으며 몰래 clamp하지 않는다.
- `duration_sec`: 생성된 전체 MP4를 다시 ffprobe해 읽은 format duration이다. 요청 길이를 복사하지 않는다.
- MP4 duration의 표기 정밀도와 rational frame coverage 길이가 미세하게 다를 수 있다. 출력의 모든 frame PTS/길이는
  원본 선택 frame과 출력 time base 2 tick 이내인지, format duration은 실제 coverage와 1ms+2 tick 이내인지 확인한다.
  이는 검사 허용치이며 출력 metadata를 요청에 맞춰 보정하는 값이 아니다. 초과하면 발행하지 않는다.

Canonical §4.3의 timeline_range는 입력이 포괄하는 Timeline 범위, §4.5의 duration_sec는 준비 media 길이다.
두 실제 값을 각 필드에 표현한다. 요청 범위는 입력 span에 남으며 출력 Canonical에 새 requested_range를 추가하지 않는다.
Consumer는 반환 timeline_range를 확인해야 한다. 정확한 요청 경계 고정이 필요한 후속 정책은 별도 합의 대상이다.

출력은 단일 H.264 video, 설정된 해상도, yuv420p, MP4, frame 수·PTS·duration을 재검사한다.
MP4 box를 읽어 moov가 mdat보다 앞에 있는지도 확인한다. 검증 전 AVAILABLE을 발행하지 않는다.

## 재사용·cleanup·보안

- 동일 서비스에서 source/span 전체·timeline id/revision·profile ref가 같으면 같은 AnalysisSource를 재사용한다.
  새 revision은 같은 좌표라도 다른 ref다. 재사용 전에 공개 span 계산으로 원본 fingerprint도 재확인한다.
- 임시 MP4는 Recording이 생성한 TemporaryDirectory 안에만 쓴다. 성공 시 bytes를 메모리로 읽고 디렉터리를 즉시 제거한다.
  encoder 실패·검사 실패·timeout도 같은 정리 경로를 거친다. 사용자 원본에는 쓰지 않는다.
- 원본 hash·크기·mtime을 변환 전후 비교한다. 참조가 변했거나 검사하지 못하면 성공을 발행하지 않는다.
- 매 open은 독립 BytesIO를 반환한다. 위치 0부터 시작하며 .name 같은 파일 경로 속성도 없다.
  공개 오류에는 argv·stderr·로컬 경로를 넣지 않는다. byte_size는 실제 bytes 길이다.
- close는 메모리 cache를 비우며 이후 해당 ref의 open은 UNAVAILABLE이다. 이미 열린 독립 stream은 호출자가 닫는다.
- 영속 cache·TTL·eviction·동시 요청 단일화·강제 프로세스 종료 후 고아 파일 회수는 구현하지 않는다.

## 한계와 검증

원본 frame 전체 조사와 출력 재검사를 수행하므로 decode 비용이 있다. 출력 bytes를 메모리에 보관하므로
긴 영상/다수 요청에서 메모리 사용량이 증가한다. 서비스 수명/close와 각 stream close는 실행기가 관리해야 한다.
불연속 PTS, duration 미관측 frame, 요청 안에 frame이 없음, 검증할 수 없는 MP4는 UNSUPPORTED_MEDIA로 거부한다.
복수 원본·시작 지연 보정·GPU 변환·provider 호출·IncidentClip·AnalysisSource AssetFacts/purge 배선은 이번 범위가 아니다.

`tests/recording/test_local_analysis_source.py`는 실제 합성 VIDEO 2개+audio에서 선택 픽셀·전체/부분·재사용·revision 분리·
원본 변경 거부·실패/timeout cleanup·fixture 호환·CLI를 검사한다. opt-in 실제 검증은
`DAESINGO_RECORDING_VIDEO`를 설정해 실행하며 공개 stream bytes를 테스트 임시 파일로 독립 검사한 뒤 제거한다.
테스트는 원본을 복사하거나 외부 provider로 전송하지 않는다.
