# W7 Service 범위 source frame inspection 재사용

AnalysisSource와 IncidentClip이 동일 원본·VIDEO stream을 순차 materialize할 때,
공통 엔진의 source ffprobe와 frame coverage 조사 결과를 한 RecordingService 안에서 재사용한다.
Contract와 RecordingService capability 시그니처, RemoteCopy, profile, v3 trace schema는 변경하지 않는다.

## 저장·조회 경계

- Service가 내부 SourceFrameInspections를 소유하며 close에서 비우고 재저장을 막는다.
- materializer에 cache를 바인딩하지 않는다. Service가 실제 호출 동안만 context-local하게
  전달하므로 같은 materializer를 여러 Service가 사용해도 cache가 공유되지 않는다.
- key는 실제 source snapshot(device/inode/byte_size/mtime_ns/SHA-256), stream index,
  ffprobe 실행 파일 설정이다. 같은 bytes의 다른 파일이나 다른 probe 설정은 보수적으로 재사용하지 않는다.
- source stream metadata와 검증된 정규화 frame coverage만 저장한다. 원본 raw frame JSON,
  output probe, 출력 bytes, 실패 결과는 이 cache에 저장하지 않는다.
- output 검증·후속 source snapshot·임시 파일 cleanup까지 성공한 inspection만 저장한다.
- 외부에서 조회한 데이터를 수정해 cache를 바꾸지 못하도록 저장/조회 시 복사한다.

매 materialization의 source snapshot·등록 원본 비교와 변환 후 source snapshot 비교는 그대로다.
초기 원본 불일치는 cache 조회 전에 기존 오류로 실패한다. 변환 중 변경·실패 시에는
해당 key를 제거하며 파생 자산을 게시하지 않는다. output probe/encode/bytes 검증은 매번 수행한다.
Service 앞단에서 원본 변경을 거부한 경우 기존 entry가 메모리에 남을 수 있지만,
원본 검사를 통과하지 못한 호출은 그것을 반환하지 않는다. close에서 전체 정리된다.

## 측정 및 결과 호환

기존 `--materialization-trace` 실행법과 v3 구조를 그대로 사용한다.
source_probe phase는 실제 probe 또는 cache lookup/copy를 포함한 **inspection 결과 획득 시간**이다.
hit 여부를 새 schema 필드로 추가하지 않는다. 기존 FROZEN bundle/raw JSON은 수정하지 않는다.
비교 측정은 같은 dataset·설정으로 새 output bundle에 실행하고 구현 revision을 별도로 기록한다.

같은 Service의 AnalysisSource→IncidentClip 경로에서 source inspection 도구 호출은
2회에서 1회로 줄어든다. output probe는 2회, materialization 전후 snapshot은 4회 유지한다.
독립 Service 또는 다른 stream은 별도 source inspection을 수행한다.

## 검증

```powershell
.venv/Scripts/python.exe -m pytest tests/recording/test_source_inspection_reuse.py tests/recording/test_materialization_observability.py tests/recording/test_recording_benchmark.py tests/recording/test_recording_baseline.py -q -p no:cacheprovider
```

실제 영상 opt-in은 기존 DAESINGO_RECORDING_VIDEO와 DAESINGO_RECORDING_VIDEO_INDEX를 사용한다.
cache 없는 참조 실행과 hit 실행의 bytes·duration·실제 범위·provenance를 비교하고,
trace on/off 동일성, Service/stream 분리, 실패 미저장, 원본 변경 거부, cleanup을 검사한다.
실제 재사용 테스트는 48p 생성 조건이며 기존 v3 실제 opt-in은 480p 분리 범위 조건이다.

## 한계

Service 수명 안의 in-memory 저장소다. TTL·영속 cache·용량 제한·LRU·동시 miss 단일화는 없다.
메모리는 성공적으로 조사한 원본/stream의 frame 수에 비례한다. 동시 동일 miss는 중복 조사할 수 있다.
source inspection에 실패하거나 변환에 실패하면 다음 시도는 다시 조사한다.
원본 hash 비용·encode·output probe·bytes read는 줄이지 않는다. 실제 속도 향상 비율은
동일 조건의 별도 전후 측정으로 확인해야 하며 기존 중앙값만으로 확정하지 않는다.
