# 실제 영상 처리 Edge Case 목록

> **작성 기준:** 2026-10-06 `develop@1d40f0290a3b0886af22f9131919729438df6b34`
>
> **목적:** 실제 블랙박스 원본을 등록하고 Timeline·AnalysisSource·IncidentClip·Frame으로
> 처리할 때 발생할 수 있는 실패를 누락 없이 분류하고, 현재 동작과 다음 검증 증거를
> 한곳에서 추적한다.
>
> 이 문서는 지원 범위를 약속하는 Contract가 아니다. 실제 검증 없이 `지원`으로
> 올리지 않으며, 미병합 PR의 결과는 현재 구현과 구분한다.

## 1. 상태 표기

| 상태 | 의미 |
| --- | --- |
| `VERIFIED` | 자동 테스트 또는 명시된 실제·합성 입력으로 공개 경로를 재현함. 확인한 범위에 한정함 |
| `OBSERVED` | 실제 원본에서 현상을 확인했지만 일반 해결책을 확정하지 않음 |
| `PENDING` | 정책·Owner·입력 조건이 확정되지 않아 의도적으로 실패 또는 미지원 |
| `NOT_TESTED` | 아직 대표 입력과 측정 결과가 없음 |

media 처리의 성공 판정은 최소한 입력 SHA-256·크기·mtime 불변, machine-readable 결과, 실패 시
부분 등록 금지 또는 명시된 부분 상태, 임시 파일 정리를 함께 확인해야 한다.

## 2. 입력·업로드 경계

[HTTP Contract](../../architecture/contracts/contract-http-api.md)는 PR #265에서
`http-api/v1` · `Final — Accepted`로 확정됐다. 계약 확정은 endpoint 구현·운영 검증 완료를 뜻하지 않는다.
현재 `POST /cases/{case_id}/sources`는 파일을 staging에 받은 뒤 관리 경로에 발행하고 등록한다.
아래 상태는 연결된 테스트와 기록의 입력 범위에 한정한다. [업로드 구현과 검증](../../runtime/rt11a-source-upload.md) ·
[업로드 MySQL 테스트](../../../tests/api/test_sources_mysql.py)

| Edge case | 현재 동작·판정 | 상태 | 다음 증거 |
| --- | --- | --- | --- |
| 경로가 없거나 일반 파일이 아님 | 로컬 등록을 실패시키고 SourceAsset을 만들지 않는다. | `VERIFIED` | 기존 등록 회귀 유지 |
| 등록 중 원본 크기·mtime·hash 변경 | 변경을 감지해 실패하고 등록 결과를 남기지 않는다. | `VERIFIED` | 대용량 파일에서도 전후 snapshot 확인 |
| 0-byte·비영상·확장자만 영상인 파일 | HTTP는 `UNSUPPORTED_MEDIA`를 `422 http.source_rejected`, `TEMPORARY_FAILURE`를 `503 http.dependency_unavailable`로 반환한다. Recording은 probe 결과로 두 실패를 구분한다. | `VERIFIED` | 구조화된 probe 결과와 HTTP 오류 매핑 테스트 |
| 파일명에 한글·공백·특수문자·매우 긴 이름 | API는 사용자 파일명을 저장 경로와 분리해 Recording에 전달한다. | `VERIFIED` / `NOT_TESTED` | Unicode·경로형 파일명은 MySQL 테스트가 다룬다. 매우 긴 파일명 경계는 미확인이다. |
| 같은 파일 재등록·재업로드 | 성공한 등록마다 새 `SourceAsset` 참조를 발급한다. | `VERIFIED` | 로컬 등록 및 HTTP 반복 업로드 테스트 |
| 여러 파일 중 일부 업로드 실패 | API는 요청당 파일 1개를 처리한다. | `NOT_TESTED` | 여러 파일에서 일부만 실패한 뒤 해당 파일만 재업로드하는 전체 흐름 검증 |
| `failed_file_count`의 영속 의미 | 무엇을 세거나 실패 이력을 영속할지는 미결이다. MVP Web은 화면 판단에 이 값을 쓰지 않으며 새로고침 뒤 실패 목록 복원은 범위 밖이다. | `PENDING` | Final HTTP Contract §5.2·§9.2의 후속 결정 |
| 업로드 중 연결 종료·프로세스 종료 | 수신 중 연결 종료·제한 시간 초과는 등록 행과 최종 파일을 남기지 않는지 검사한다. | `VERIFIED` | [프로세스 종료와 정리 검증](../../runtime/rt11a-source-upload.md)에서 별도 조건을 확인한다. |
| 디스크 부족·권한 오류·읽기 전용 mount | API와 Worker는 Compose에서 미디어 볼륨을 공유한다. 업로드 저장 실패는 실패 주입 테스트로 다룬다. | `NOT_TESTED` | 실제 공유 볼륨의 ENOSPC·권한 실패 주입 |
| 단일 파일 최대 4GB | 현재 코드·CI·Benchmark에서 검증하지 않았다. | `NOT_TESTED` | 4GB 근처 실제/합성 파일의 upload·probe·disk peak·timeout 측정 |
| 60분 분할 원본 전체를 1분 안에 업로드 | 이 속도 목표는 미검증이다. | `NOT_TESTED` | 파일 수·총 bytes·network·fsync·publish 시간을 단계별 측정 |

## 3. 컨테이너·codec·stream

| Edge case | 현재 동작·판정 | 상태 | 근거·다음 증거 |
| --- | --- | --- | --- |
| AVI·MP4 | 실제 AVI와 합성 MP4의 등록·해소·materialization·frame 경로를 검증했다. 모든 codec 조합을 의미하지 않는다. | `VERIFIED` | Recording 실제 영상·CI smoke |
| MOV | 실제 비교 영상의 전체 Recording 경로를 통과했다. | `VERIFIED` | PR #220 |
| MKV stream duration이 본 필드에 없음 | `stream.duration` 다음 `tags.DURATION`을 사용하고 둘 다 없으면 모른다고 유지한다. container duration을 stream에 복사하지 않는다. | `VERIFIED` | PR #220 |
| MKV 1ms time-base 양자화 | 검증된 일정 반올림 패턴과 ±1 tick 중간 coverage만 제한적으로 정규화한다. gap·역전·중복은 거부한다. | `VERIFIED` | `experiments/mkv-frame-quantization.md` |
| 마지막 output frame duration 누락 | frame 수·상대 PTS와 stream duration이 expected coverage와 일치할 때만 복원한다. | `VERIFIED` | PR #233 |
| 구버전 ffprobe가 frame `duration`을 생략 | `duration`·`pkt_duration`·인접 timestamp 근거를 순서대로 사용한다. 근거 없는 마지막 frame은 거부한다. | `VERIFIED` | PR #134 및 실제 FFprobe 4.3.1 피드백 |
| FFmpeg가 `-fps_mode`를 지원하지 않음 | 현재 엔진은 `-fps_mode passthrough`를 요구하며 FFmpeg 4.3.1 encode는 해당 옵션 미지원으로 실패한다. FFmpeg/ffprobe 9.0.1의 실제 처리와 CI 합성 smoke 통과는 확인했지만 생성 경로 전체의 정확한 최소 지원 버전은 미확정이다. | `VERIFIED` | [실행 환경](local-analysis-source.md), CI smoke의 확인된 환경에 한정 |
| 지원하지 않는 codec·pixel format | probe 성공과 decode 성공은 다르다. 실제 materialization 검증을 통과하지 못하면 `UNSUPPORTED_MEDIA` 또는 해당 capability 실패로 종료한다. | `VERIFIED` | 실패 주입 테스트 유지, codec별 실측 추가 |
| VIDEO 없음·audio-only | AnalysisSource/Frame용 VIDEO를 고를 수 없으므로 명시적으로 실패해야 한다. | `VERIFIED` | stream 선택 단위 테스트 |
| VIDEO 복수(전·후방) | role이나 배열 첫 항목으로 고르지 않는다. 실행자가 VIDEO ref를 명시해야 한다. | `VERIFIED` | 실제 전·후방 AVI, `resolve_span` 테스트 |
| VIDEO role 미확인 | 실제 등록은 카메라 방향을 추정하지 않고 `UNKNOWN`으로 둔다. | `VERIFIED` | 로컬 등록 테스트 |
| subtitle/data/private stream | 현재 Canonical MediaStream 대상이 아니며 VIDEO/AUDIO처럼 등록하지 않는다. GPS가 없다는 증거로 사용하지 않는다. | `VERIFIED` / `PENDING` | subtitle 제외는 확인, private GPS는 실제 원본 필요 |
| stream duration `null` | 사용 불가나 전체 누락으로 추정하지 않는다. 선택 stream coverage를 확정할 수 없으면 해소 실패로 표면화한다. | `VERIFIED` | 실제 audio duration 누락 사례 |
| container와 stream duration 불일치 | 선택한 VIDEO의 관측 범위만 사용한다. 다른 stream 길이를 복사하지 않는다. | `VERIFIED` | 실제 전·후방 AVI에서 길이 차이 관측 |

## 4. Timeline·다중 파일

| Edge case | 현재 동작·판정 | 상태 | 근거·다음 증거 |
| --- | --- | --- | --- |
| 절대시각 근거 없음 | 가짜 날짜를 만들지 않고 `USABLE_RELATIVE_ONLY`로 둔다. | `VERIFIED` | `relative-timeline-creation.md` |
| 파일명 시각과 화면 overlay 불일치·미확인 | anchor를 적용하지 않고 relative-only를 유지한다. | `VERIFIED` | `local-time-sources.md` |
| timezone·century 불명 | 명시적 설정 없이 추정하지 않는다. | `VERIFIED` | MDR 파일명 parser 회귀 |
| stale Timeline revision으로 변경 시도 | 최신 revision에서만 새 revision을 만들고 stale 입력을 거부한다. 과거 revision 조회는 provenance 재현을 위해 유지한다. | `VERIFIED` | Timeline revision 테스트 |
| 파일 순서가 입력 배열·파일명에만 의존 | Recording은 배열 순서·파일명·ref에서 연속성을 추론하지 않는다. placement를 명시해야 한다. | `VERIFIED` | `multi-source-timeline.md` |
| 파일 사이 gap | `Timeline.gaps`와 `missing_ranges(TIMELINE_GAP)`로 보존하고 usable span이 있으면 `PARTIAL`로 반환한다. | `VERIFIED` | PR #222, 2·3원본 테스트 |
| placement overlap | 임의로 앞·뒤 파일 우선순위를 정하지 않고 입력을 거부한다. | `VERIFIED` | PR #222 |
| source-local 시작이 0이 아닌 trim | 현재 placement 입력으로 표현하지 못한다. | `PENDING` | offset·overlap 입력 모델 합의 |
| 사건 구간이 파일 경계를 넘음 | `resolve_span()`은 Timeline 순서의 여러 AssetSpan을 반환할 수 있다. | `VERIFIED` | 실제 AVI 두 파일 좌표 해소 및 합성 3원본 |
| 여러 span을 하나의 AnalysisSource로 생성 | 병합된 PR #256의 공개 경로로 연속 COMPLETE span을 연결한다. 합성 2·3원본의 frame 순서·provenance·실패 거부·원본 불변·cleanup을 검증했다. | `VERIFIED` | [다중 span AnalysisSource](multi-span-analysis-source.md), `test_multi_span_analysis_source.py` |
| 제한된 실제 AVI의 AnalysisSource 연결 | PR #256 실험에서 익명 A1–A3·B1–B3의 명시적 VIDEO 0 연결에 성공했다. 입증된 후행 H.264 패턴의 best-effort는 Search용 AnalysisSource에만 적용한다. B4 포함 VIDEO 0과 A/B VIDEO 1은 거부했다. | `VERIFIED` | [PR #256 실제 데이터 검증](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/256). 해당 입력·실험 배치에 한정 |
| 여러 span을 하나의 IncidentClip으로 생성 | 병합된 PR #258의 strict 구현과 합성 2·3원본 frame 순서·provenance·실패 거부·cleanup을 검증했다. AnalysisSource best-effort는 적용하지 않는다. | `VERIFIED` | [다중 span IncidentClip](multi-span-incident-clip.md), `test_multi_span_incident_clip.py` |
| 제공된 실제 AVI의 IncidentClip 연결 | PR #258 실험의 A1–A3·B1–B3·B1–B4는 strict encode에서 실패했으며 Clip 미발급·best-effort 미실행·cleanup을 확인했다. 실제 AVI의 양성 연결은 미확인이다. | `OBSERVED` | [PR #258 실제 블랙박스 검증](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/258). 깨끗한 실제 연속 원본 양성 검증은 `NOT_TESTED` |
| 실제 촬영 연속성·gap·overlap | metadata duration을 이어 붙인 실험 좌표는 실제 촬영 연속성을 증명하지 않는다. 실제 촬영 gap·overlap도 검증하지 않았다. | `NOT_TESTED` | 화면·GPS·제조사 시각 등 독립 근거 필요 |

## 5. Frame·materialization·출력

| Edge case | 현재 동작·판정 | 상태 | 근거·다음 증거 |
| --- | --- | --- | --- |
| 요청 시각이 frame 사이에 있음 | 요청 시각 이상 첫 decoded frame을 반환하며 실제 PTS를 기록한다. 요청값으로 덮어쓰지 않는다. | `VERIFIED` | `local-frame-access.md` |
| 요청 범위가 stream 끝을 넘음 | usable 부분과 missing range를 분리해 `PARTIAL`, 전부 밖이면 `FAILED`로 반환한다. | `VERIFIED` | `local-span-resolution.md` |
| 요청 구간에 frame 없음 | `FRAME_NOT_FOUND` 또는 `UNSUPPORTED_MEDIA`로 실패하고 가짜 frame을 만들지 않는다. | `VERIFIED` | frame/materialization 실패 테스트 |
| 원본이 등록 후 변경·소실 | fingerprint 불일치 또는 접근 실패를 감지해 새로운 `resolve_frame`·frame 추출·materialization을 거부한다. 이미 발행한 결과까지 자동 무효화하지 않는다. | `VERIFIED` | AssetFacts·Frame·materialization 회귀 |
| 이미 발행한 Frame·AnalysisSource bytes 조회 | 로컬 경로에서 이미 저장한 bytes는 원본 변경·소실 뒤에도 조회할 수 있다. 메모리의 AnalysisSource는 독립 `BytesIO`로 연다. | `VERIFIED` | `test_changed_source_rejected_but_published_bytes_stable` |
| ffmpeg timeout·비정상 종료 | machine-readable 실패를 반환하고 임시 작업공간을 정리한다. | `VERIFIED` | timeout·실패 주입 테스트 |
| AVI 정상 frame 뒤 후행 H.264 오류 packet | 실제 7개 AVI에서 반복 관찰했다. 모든 AVI/H.264 오류에 대한 일반 복구를 뜻하지 않으며 B4·후방 stream은 계속 거부한다. | `OBSERVED` | PR #256 실제 입력 기록 |
| Search용 AnalysisSource의 제한적 best-effort | 병합된 PR #256은 strict 실패 뒤 입증된 AVI/H.264 후행 패턴에서만 재시도한다. 출력은 frame 수·PTS·duration과 전체 strict decode를 검증한다. IncidentClip은 단일·다중 span 및 중첩 호출에서도 strict를 유지한다. | `VERIFIED` | [제한 조건](multi-span-analysis-source.md), `test_analysis_tail_policy.py` |
| frame coverage gap·역전·중복 | 양자화로 입증된 제한적 예외 외에는 거부한다. | `VERIFIED` | MKV·AVI 실패 회귀 |
| 출력 bytes와 metadata 불일치 | 출력 ffprobe·frame 수·PTS·duration·크기를 다시 검사하고 요청 범위로 보정하지 않는다. | `VERIFIED` | AnalysisSource/IncidentClip 테스트 |
| 긴 입력·다수 materialization의 메모리 사용 | 파생 bytes를 서비스 메모리에 보관하므로 증가 가능성이 있으나 peak memory를 측정하지 않았다. | `NOT_TESTED` | 60분·동시 요청 RSS/temporary disk benchmark |
| 메모리 경로의 `close()` 뒤 재조회 | 메모리만 쓰는 AnalysisSource·IncidentClip은 `close()` 뒤 다시 열 수 없다. 이미 연 독립 스트림은 호출자가 닫는다. | `VERIFIED` | AnalysisSource·IncidentClip 수명 회귀 |
| 새 서비스에서 영속 조회 | MySQL에 커밋한 분석용·사건 영상과 저장된 프레임은 새 서비스에서 복원할 수 있다. | `VERIFIED` | [영속 미디어의 새 연결 테스트](../../../tests/recording/test_durable_facts_mysql.py) · [프레임 복원 경계](rec1c-ownership-reads.md) |
| 같은 요청의 중복 실행 | 일부 identity/ref 재사용은 있으나 process 간 동시 요청 중복 방지는 없다. | `NOT_TESTED` | 동시 실행·lock·idempotency 실험 |

## 6. 시각·GPS·외부 의존성

| Edge case | 현재 동작·판정 | 상태 | 다음 증거 |
| --- | --- | --- | --- |
| 파일명 시각 파싱 실패 | 후보를 만들지 않고 relative-only를 유지한다. | `VERIFIED` | time-source 테스트 |
| overlay를 자동으로 확인할 수 없음 | 사람이 일치와 신뢰를 확인한 경우에만 filename anchor를 적용한다. | `VERIFIED` | 실제 overlay 확인 기록 |
| GPS 미장착·수신 실패 | Mock은 실제 GPS를 읽지 않는다. 실제 GPS parser와 제조사 원본 확인은 미구현·미완료이며 GPS 부재는 parser 오류와 구분해야 한다. | `PENDING` | GPS 탑재 원본·SD카드 전체 구조·Viewer 비교 |
| GPS가 영상 stream이 아닌 sidecar/private metadata | ffprobe에 안 보인다는 이유로 GPS 없음으로 단정하지 않는다. | `PENDING` | 제조사·모델별 실제 원본 묶음 |
| Mock GPS의 좌표·status·confidence·ref | 병합된 PR #271은 유한 좌표·범위, status별 value, confidence 0~1, source MediaStream ref와 fixture 소속을 검증한다. 실제 GPS parser 검증은 아니다. | `VERIFIED` | [Mock GPS 경계](mock-gps.md), `test_mock_gps.py` |
| 범위 밖·NaN·무한 GPS 좌표 | Mock 모델이 거부하며 변조된 입력도 Kakao adapter가 재검증해 호출 전에 거부한다. | `VERIFIED` | PR #271·#272 자동 테스트. 실제 parser는 별도 `PENDING` |
| non-OK GPS의 Kakao 호출 | 병합된 PR #272는 검증된 non-OK GPS를 SKIPPED로 반환하고 네트워크를 호출하지 않는다. | `VERIFIED` | `test_kakao_geocoder.py`의 무네트워크 자동 테스트 |
| reverse geocoder 인증·quota·timeout·빈 결과 | Kakao adapter는 오류를 분류하고 원래 GPS를 변경하거나 가짜 주소를 만들지 않는다. JSON/schema 오류와 빈 documents도 별도로 처리한다. | `VERIFIED` | [Kakao adapter](kakao-geocoder.md), fake HTTPS connection 자동 테스트 |
| Kakao adapter의 로그·repr 노출 방지 | 합성 키·좌표·주소·예외 메시지가 로그·repr·실패 결과에 노출되지 않음을 자동 테스트로 확인했다. 운영 배선 전체의 보증은 아니다. | `VERIFIED` | `test_kakao_geocoder.py`의 privacy·close·RecursionError 회귀 |
| 실제 Kakao 키 실호출 | 2026-11-01 운영자 기록은 Mock GPS 좌표로 실제 Kakao API 응답을 확인했다. | `VERIFIED` | [실호출 기록](kakao-geocoder.md#2026-11-01--운영자-실제-api-호출-확인). 실제 블랙박스 GPS와 배포 설정 주입은 이 시험에서 미검증이다. |
| Case/Evidence/Web의 실제 GPS·주소 배선 | adapter는 내부 provider이며 composition root 및 Case/Evidence/Web 표시 주소 선택·실연동은 후속 합의·구현 대상이다. | `PENDING` | Consumer 배선 합의 및 실연동 검증 |
| 정밀 좌표·주소·API key 로그 노출 | 로그·리포트에 남기지 않아야 한다. | `PENDING` | 실제 composition root와 운영 로그 검증 |

## 7. 실패 시 반드시 남길 증거

| 항목 | 기록 원칙 |
| --- | --- |
| 입력 identity | 외부 공유본에는 파일명·경로 대신 익명 dataset ID와 fingerprint 사용 |
| 환경 | Python·FFmpeg·ffprobe 버전, OS, 실행 profile |
| 단계 | register/probe, Timeline, resolve, AnalysisSource, IncidentClip, Frame 등 최초 실패 단계 |
| 결과 | status·failure code·requested/actual range·missing range |
| 자원 | elapsed time, 가능하면 peak RSS·temporary disk·입출력 bytes |
| 무결성 | 실행 전후 SHA-256·크기·mtime 동일 여부 |
| 정리 | staging·temporary·부분 파생물이 남았는지 |
| 재현 | 공개 capability 또는 명령, 명시적 stream·placement·range |

경로, 인증정보, 원본 주소·정밀 GPS, stderr 원문은 안전한 failure code와 분리한다.

## 8. 다음 실험 우선순위

| 우선순위 | 실험 | 완료 조건 |
| --- | --- | --- |
| P0 | 실제 분할 블랙박스 60분 분량 업로드 | 총 bytes·파일 수·파일별 성공/실패·전체/단계별 시간·재시도 결과 기록 |
| P0 | 4GB 경계 | body 한도, staging/fsync/publish, disk peak, timeout과 원본 불변 확인 |
| P0 | 일부 파일 실패 | Final HTTP Contract의 파일별 성공·실패·재업로드 검증. `failed_file_count` 영속 의미는 별도 후속 결정 |
| P1 | MOV·MKV·AVI·MP4 matrix | container만이 아니라 codec·stream 구성·duration source를 함께 기록 |
| P1 | 동시 upload/materialization | 요청 수별 latency·RSS·temporary disk·중복 실행 여부 측정 |
| P1 | 실제 GPS 원본 | 제조사 Viewer와 두 지점 이상 좌표·시각 대조, 부재와 parser 실패 분리 |
| P2 | 장시간 restart/recovery | staging orphan, persistent ref, Worker 재시도와 cleanup 확인 |

## 9. 완료 기준

이 목록의 항목은 다음 조건을 만족할 때만 `VERIFIED`로 변경한다.

1. 대표 입력과 실행 환경을 식별할 수 있다.
2. 공개 capability 또는 실제 HTTP 경로로 재현된다.
3. 성공·부분 성공·실패 중 하나가 machine-readable하게 구분된다.
4. 원본 불변과 임시 산출물 정리를 확인한다.
5. 자동 회귀 또는 반복 가능한 실험 문서가 있다.

단일 샘플 성공을 같은 확장자의 모든 영상 지원으로 일반화하지 않는다.
