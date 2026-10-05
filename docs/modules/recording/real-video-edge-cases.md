# 실제 영상 처리 Edge Case 목록

> **작성 기준:** 2026-10-05 `develop`
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
| `VERIFIED` | 자동 테스트와 실제 또는 합성 media로 공개 경로를 재현함 |
| `OBSERVED` | 실제 원본에서 현상을 확인했지만 일반 해결책을 확정하지 않음 |
| `PENDING` | 정책·Owner·입력 조건이 확정되지 않아 의도적으로 실패 또는 미지원 |
| `NOT_TESTED` | 아직 대표 입력과 측정 결과가 없음 |

성공 판정은 최소한 입력 SHA-256·크기·mtime 불변, machine-readable 결과, 실패 시
부분 등록 금지 또는 명시된 부분 상태, 임시 파일 정리를 함께 확인해야 한다.

## 2. 입력·업로드 경계

| Edge case | 현재 동작·판정 | 상태 | 다음 증거 |
| --- | --- | --- | --- |
| 경로가 없거나 일반 파일이 아님 | 로컬 등록을 실패시키고 SourceAsset을 만들지 않는다. | `VERIFIED` | 기존 등록 회귀 유지 |
| 등록 중 원본 크기·mtime·hash 변경 | 변경을 감지해 실패하고 등록 결과를 남기지 않는다. | `VERIFIED` | 대용량 파일에서도 전후 snapshot 확인 |
| 0-byte·비영상·확장자만 영상인 파일 | 확장자가 아니라 media probe 결과로 판단해야 한다. 현재 ffprobe 실패는 손상/비영상과 도구의 일시 장애를 모두 `TEMPORARY_FAILURE`로 낼 수 있다. | `PENDING` | `422 source_rejected`와 `503 dependency_unavailable` taxonomy 분리 |
| 파일명에 한글·공백·특수문자·매우 긴 이름 | 등록 path의 basename을 시간 후보 입력으로 사용한다. HTTP에서는 사용자 파일명을 저장 경로로 쓰지 않는 방향이 Draft다. | `NOT_TESTED` | path traversal·Unicode·길이 제한 테스트 |
| 같은 파일 재업로드 | 성공 호출마다 새 SourceAsset ref를 발급한다. 내용 기반 dedupe는 없다. | `VERIFIED` | HTTP 재시도·중복 등록 UX 정책 확인 |
| 여러 파일 중 일부 업로드 실패 | HTTP API Draft는 파일마다 독립 요청을 제안한다. `failed_file_count` 영속 의미와 실패 파일 표시 방식은 미확정이다. | `PENDING` | PR #265 Recording·Case·Web 합의 |
| 업로드 중 연결 종료·프로세스 종료 | 실제 HTTP upload/staging 구현이 아직 없다. | `NOT_TESTED` | staging 잔여, publish 전후 crash, 재시도 실험 |
| 디스크 부족·권한 오류·읽기 전용 mount | 로컬 capability의 파일 접근 실패는 처리하지만 실제 공유 저장소 운영 경로는 없다. | `NOT_TESTED` | API/Worker 공유 mount에서 ENOSPC·권한 실패 주입 |
| 단일 파일 최대 4GB | 현재 코드·CI·Benchmark에서 검증하지 않았다. | `NOT_TESTED` | 4GB 근처 실제/합성 파일의 upload·probe·disk peak·timeout 측정 |
| 60분 분할 원본 전체를 1분 안에 업로드 | HTTP upload 자체가 없어 속도 목표를 검증하지 않았다. | `NOT_TESTED` | 파일 수·총 bytes·network·fsync·publish 시간을 단계별 측정 |

## 3. 컨테이너·codec·stream

| Edge case | 현재 동작·판정 | 상태 | 근거·다음 증거 |
| --- | --- | --- | --- |
| AVI·MP4 | 실제 AVI와 합성 MP4의 등록·해소·materialization·frame 경로를 검증했다. 모든 codec 조합을 의미하지 않는다. | `VERIFIED` | Recording 실제 영상·CI smoke |
| MOV | 실제 비교 영상의 전체 Recording 경로를 통과했다. | `VERIFIED` | PR #220 |
| MKV stream duration이 본 필드에 없음 | `stream.duration` 다음 `tags.DURATION`을 사용하고 둘 다 없으면 모른다고 유지한다. container duration을 stream에 복사하지 않는다. | `VERIFIED` | PR #220 |
| MKV 1ms time-base 양자화 | 검증된 일정 반올림 패턴과 ±1 tick 중간 coverage만 제한적으로 정규화한다. gap·역전·중복은 거부한다. | `VERIFIED` | `experiments/mkv-frame-quantization.md` |
| 마지막 output frame duration 누락 | frame 수·상대 PTS와 stream duration이 expected coverage와 일치할 때만 복원한다. | `VERIFIED` | PR #233 |
| 구버전 ffprobe가 frame `duration`을 생략 | `duration`·`pkt_duration`·인접 timestamp 근거를 순서대로 사용한다. 근거 없는 마지막 frame은 거부한다. | `VERIFIED` | PR #134 및 실제 FFprobe 4.3.1 피드백 |
| FFmpeg가 `-fps_mode`를 지원하지 않음 | 현재 생성 경로는 FFmpeg 5.0 이상을 요구한다. 4.3.1 encode는 실패한다. | `VERIFIED` | `local-analysis-source.md` 실행 환경 |
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
| 여러 span을 하나의 AnalysisSource로 생성 | 구현·실측은 PR #256에 있으나 2026-10-05 기준 미병합이다. 실제 AVI 일부는 후행 H.264 오류 정책이 필요했다. | `PENDING` | PR #256 병합·CI·실제 연속성 증거 |
| 여러 span을 하나의 IncidentClip으로 생성 | strict stitching 구현은 PR #258에 있으나 기준 PR #256 위의 미병합 상태다. 실제 제공 AVI의 strict 양성 연결은 확인하지 못했다. | `PENDING` | PR #258 병합 후 깨끗한 실제 연속 원본 양성 검증 |
| 실제 촬영 gap·overlap | metadata duration을 이어 붙인 실험 좌표는 실제 촬영 연속성을 증명하지 않는다. | `OBSERVED` | 화면·GPS·제조사 시각 등 독립 근거 필요 |

## 5. Frame·materialization·출력

| Edge case | 현재 동작·판정 | 상태 | 근거·다음 증거 |
| --- | --- | --- | --- |
| 요청 시각이 frame 사이에 있음 | 요청 시각 이상 첫 decoded frame을 반환하며 실제 PTS를 기록한다. 요청값으로 덮어쓰지 않는다. | `VERIFIED` | `local-frame-access.md` |
| 요청 범위가 stream 끝을 넘음 | usable 부분과 missing range를 분리해 `PARTIAL`, 전부 밖이면 `FAILED`로 반환한다. | `VERIFIED` | `local-span-resolution.md` |
| 요청 구간에 frame 없음 | `FRAME_NOT_FOUND` 또는 `UNSUPPORTED_MEDIA`로 실패하고 가짜 frame을 만들지 않는다. | `VERIFIED` | frame/materialization 실패 테스트 |
| 원본이 등록 후 변경·소실 | fingerprint 불일치 또는 접근 실패를 감지해 원본·파생 결과를 사용할 수 없다고 처리한다. | `VERIFIED` | AssetFacts·Frame·materialization 회귀 |
| ffmpeg timeout·비정상 종료 | machine-readable 실패를 반환하고 임시 작업공간을 정리한다. | `VERIFIED` | timeout·실패 주입 테스트 |
| AVI 정상 frame 뒤 후행 H.264 오류 packet | 실제 7개 AVI에서 반복 관찰했다. AnalysisSource에만 제한적 재시도하는 구현은 PR #256에 있으며, IncidentClip은 strict 유지다. | `OBSERVED` / `PENDING` | PR #256, B4·후방 stream은 계속 거부 |
| frame coverage gap·역전·중복 | 양자화로 입증된 제한적 예외 외에는 거부한다. | `VERIFIED` | MKV·AVI 실패 회귀 |
| 출력 bytes와 metadata 불일치 | 출력 ffprobe·frame 수·PTS·duration·크기를 다시 검사하고 요청 범위로 보정하지 않는다. | `VERIFIED` | AnalysisSource/IncidentClip 테스트 |
| 긴 입력·다수 materialization의 메모리 사용 | 파생 bytes를 서비스 메모리에 보관하므로 증가 가능성이 있으나 peak memory를 측정하지 않았다. | `NOT_TESTED` | 60분·동시 요청 RSS/temporary disk benchmark |
| 서비스 종료 뒤 파생 ref 재조회 | 현재 로컬 materialization은 서비스 수명 안의 메모리 보관이다. `close()` 뒤 unavailable이며 영속 자산 경로는 별도 Runtime 작업이다. | `VERIFIED` / `PENDING` | persistent repository·restart 통합 테스트 |
| 같은 요청의 중복 실행 | 일부 identity/ref 재사용은 있으나 process 간 동시 요청 중복 방지는 없다. | `NOT_TESTED` | 동시 실행·lock·idempotency 실험 |

## 6. 시각·GPS·외부 의존성

| Edge case | 현재 동작·판정 | 상태 | 다음 증거 |
| --- | --- | --- | --- |
| 파일명 시각 파싱 실패 | 후보를 만들지 않고 relative-only를 유지한다. | `VERIFIED` | time-source 테스트 |
| overlay를 자동으로 확인할 수 없음 | 사람이 일치와 신뢰를 확인한 경우에만 filename anchor를 적용한다. | `VERIFIED` | 실제 overlay 확인 기록 |
| GPS 미장착·수신 실패 | 실제 parser는 없으며 GPS 부재는 오류와 구분해야 한다. | `PENDING` | GPS 탑재 원본·SD카드 전체 구조·Viewer 비교 |
| GPS가 영상 stream이 아닌 sidecar/private metadata | ffprobe에 안 보인다는 이유로 GPS 없음으로 단정하지 않는다. | `PENDING` | 제조사·모델별 실제 원본 묶음 |
| 범위 밖·NaN·무한 GPS 좌표 | 유효 좌표로 채택하거나 geocoder를 호출하면 안 된다. | `PENDING` | GPS Mock PR #271 및 실제 parser 후속 |
| reverse geocoder 인증·quota·timeout·빈 결과 | 좌표 자체를 삭제하거나 가짜 주소를 만들면 안 된다. Kakao adapter는 PR #272에 있으며 미병합이다. | `PENDING` | 실제 키 opt-in 검증, Consumer 배선 합의 |
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
| P0 | 일부 파일 실패 | 성공 파일 유지·실패 파일 식별·재업로드 단위·`failed_file_count` 정책 합의 |
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
