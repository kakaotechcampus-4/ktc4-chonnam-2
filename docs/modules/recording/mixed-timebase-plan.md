<a id="mixed-time-base-implementation-plan"></a>

# 혼합 시간 기준 구현 계획

상태: IN_PROGRESS · Refs #425 · 관련 #452, #460.

권한 근거: [이슈와 재현](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425),
[MP4 관측](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425#issuecomment-6490185400),
[Owner 결정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/425#issuecomment-6493673627).

목표: 개별 검증된 동일 영상 크기의 H.264 출력들이 서로 다른 clock을 가질 때,
디코딩된 프레임 PTS, duration, 개수와 source provenance를 보존한다.
고정 FPS, gap 보정, 허용 오차 확대, 분류 체계 또는 운영 제한 변경은 없다.
TDD로 현재 세션에서 구현하고 이후 새 읽기 전용 GPT-6.1 Sol / High 검토를 받는다.
worktree, staging, commit, push, 배포, 원격 호스트, provider 호출은 없다.

<a id="design"></a>

## 설계

- 기존 동일 time-base 경로는 유지한다. 혼합 출력은 AnalysisSource와 IncidentClip이
  공유하는 별도 내부 정규화 단계를 사용한다. 공개 스키마, source stream 사실,
  prepared-media 영속화와 provenance는 변경하지 않는다.
- 공통 역수 정수 clock을 계산하기 전에 분수를 기약한다. Python 정수로 곱셈 전
  나눗셈과 경계 검사를 사용해 LCM을 계산한다. 모든 PTS, duration, 누적 offset과
  endpoint가 정수 tick인지 검증한다. 잘못된 coverage나 지원하지 않는 숫자 범위는
  Recording `UNSUPPORTED_MEDIA`로 거부하고 IncidentClip은 기존 공개 wrapper를 유지한다.
- 원래 선택한 coverage를 encoded coverage와 별도로 내부에 보존한다. 이전에 단일
  변환이 기존 허용 오차를 통과했어도 혼합 chain은 원래 coverage와 정확히 일치해야
  한다. 단일 입력 규칙은 변경하지 않는다.
- 검증된 part를 공유 MP4 track timescale로 remux하고 프레임과 packet을 독립적으로
  probe한다. 추가 손실 인코딩이나 encoder FPS 변환은 없다.
- FFmpeg concat의 manifest duration과 offset은 AV_TIME_BASE(마이크로초)를 사용한다.
  정수 연산으로 이 전송 offset을 계산한 뒤 setts로 각 part packet에 정확히 의도한
  tick offset을 복원한다. 표시 PTS, duration, packet 개수를 보존한다. 서로 다른
  B-frame 지연이 이음새 sample duration을 바꾸지 못하도록 공유 reorder delay로
  decode interval을 별도로 연결하며 최종 디코딩 coverage를 독립 검증한다.
  MP4/muxer 정수 필드와 binary64 표현식 정수를 모두 범위 검사한다.
  coverage를 보존할 수 없는 remux/concat 결과는 기대값을 바꿔 보정하지 않고 거부한다.
  기존 strict decode와 faststart 검사는 유지한다.
- 바이트 예산, 취소 checkpoint, 정리 lease, 트랜잭션 소유권을 보존한다. 추가 파일은
  기존 chain TemporaryDirectory 안에만 둔다. DB checkout을 도입하지 않으며
  Runtime 오류를 media 오류로 변환하지 않는다.

주요 참고 자료(FFmpeg n8.1):
[concat offset](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavformat/concatdec.c),
[setts 연산](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavcodec/bsf/setts.c),
[MP4 경계](https://github.com/FFmpeg/FFmpeg/blob/n8.1/libavformat/movenc.c).

<a id="execution-ledger"></a>

## 실행 기록

- [x] RED: 실제 합성 파일 최소 두 개, Issue clock 조합, 공개 AnalysisSource와
  IncidentClip로 개별 변환 성공을 검증한다.
- [x] GREEN: 유리수 계획, 검증된 remux, 정확한 concat projection.
- [x] 부정 대조: 잘못된 offset/PTS/duration/프레임 개수와 정규화 우회를 탐지하고,
  overflow와 표현 불가능한 coverage를 안전하게 거부한다.
- [x] 회귀: 같은 clock, gap/overlap/coverage/손상, source 해시, 스트림 선택,
  바이트/duration 예산, 프로세스/lease 정리, Worker receipt.
- [x] 실제 미디어: 메타데이터 우선 읽기 전용 목록, 관련 최소 sample을 사용하고
  사용 가능한 로컬 미디어와 검증하지 못한 원래 Issue 재현 세트를 구분한다.
- [x] 새 검토, 수정 재현, 같은 검토자의 차이 검사. Notes와 Log 증거를 추가하고
  작업 전용 산출물을 정리하며 diff를 unstaged 상태로 둔다.

검증에는 Windows PATH가 아닌 기존 로컬 FFmpeg/ffprobe 8.1 이미지를 사용한다.
전체 pytest, 필수 MySQL, 변이 목록은 원격 CI 조건으로 남는다.

<a id="implemented-numeric-rules-and-limitations"></a>

## 구현된 수치 규칙과 한계

관측한 모든 프레임 PTS/duration 및 인코딩 packet PTS/DTS/duration에 대해
`T = lcm(denominator(reduce(value)))`이며 출력 clock은 `1/T`다. 원래
MediaStream time base는 source 사실로 남는다. MaterializedVideo.time_base는
원래 clock이 아니라 각 encoded part(및 반환되는 최종 derived 출력)를 기술한다.
사용하지 않는 tick은 T를 제약하지 않는다. 프레임 관측값은 관측된 part clock에서
여전히 정수여야 한다. remux 전에 모든 packet 사실을 읽어 decode-time 정밀도가
공통 clock 결정에 참여하도록 한다. 곱셈 전에 `scale <= INT_MAX // factor`를
검사한다. FFmpeg 이전의 모든 연산은 `Fraction`/Python 정수다.
`T <= 2^31-1`은 movenc 옵션 범위를 따른다. 선택한 모든 source 프레임은 개별
encoded 프레임과 정확히 같아야 한다. 이전 단일 입력 허용 오차는 혼합 chain 지원을
입증하지 않는다. 각 프레임 PTS, 양의 duration, 누적 part offset과 endpoint는
정수 tick이어야 한다. source 좌표와 원래 stream 사실은 덮어쓰지 않는다.

part별 MP4 stream copy는 프레임 및 packet clock과 독립 대조한다. 실제 encoded
packet PTS 집합은 디코딩 프레임과 일대일로 일치해야 한다. decode interval은
연속이고 part 길이를 정확히 덮어야 한다. Packet PTS/DTS 및 표현식 피연산자/결과는
`[-(2^53-1), 2^53-1]` 안에 있어야 한다. setts가 binary64를 사용하므로 int64보다
엄격한 부분집합이다. Duration은 양수이며 최대 INT_MAX이고 인접 DTS delta는
INT_MAX보다 엄격히 작아야 한다(movenc가 같은 경우 다시 쓰기 때문). PTS-DTS는
지원되는 부호 있는 offset 범위 안에 있어야 한다(보수적으로 절댓값 최대 INT_MAX).
지원하지 않거나 누락된 timing 관측값은 거부한다.

Manifest duration은 정수 마이크로초이며 concat 전송 목적으로만 내림한다.
알려진 concat offset은 정수 최근접/동률 시 영에서 멀어지는 반올림 연산으로 rescale한다.
packet 순번 기반 균형 lookup 표현식이 정확한 표시 offset을 복원한다.
로그 수준 tree depth는 FFmpeg AVExpr의 depth 제한을 피하며 leaf와 피연산자는
정확한 정수다. decode interval은 별도로 연결한 뒤 하나의 공통 최대 reorder delay만큼
이동하여 PTS >= DTS를 보장한다. 프레임 기대값이나 source 시간은 반올림하지 않는다.
최종 출력은 계획된 clock, 영 표시 원점, 정확한 프레임 PTS/duration/개수와 계획된
정확한 packet PTS/DTS/duration을 가져야 하며, 이후 strict 전체 decode,
format/faststart/바이트 검사와 source fingerprint 재검증을 통과해야 한다.

동일 clock 입력은 이전 concat 경로와 검증을 유지한다. 이 변경은 encoder/FPS 선택,
API 필드, DB 스키마, 트랜잭션, receipt, Case 규칙을 추가하지 않는다.
remux/probe 작업은 추가되며 기존 메모리 내 part 바이트 한계는 유지한다.
#425의 명목상 AVI clock 네 개의 분모 LCM은 **12679469020444296**으로(직접 정수 계산),
INT_MAX를 초과한다. 이것만으로 거부를 입증하지는 **않는다**. 필요한 grid를 결정하려면
실제 프레임과 packet 관측이 필요하다. 명목 clock 1/65537 및 1/65539인 성긴 1fps
쌍은 출력 clock 1/1에서 검증됐다. 원래 아홉 개 파일 세트는 확인된 재현 세트로 사용할 수
없으므로 그 표현 가능성과 연결 결과는 검증되지 않았다. 표현 불가능한 clock을 맞추기
위한 반올림이나 한 시간 서비스 약속은 도입하지 않는다. 현재 concat 전송은 각 part가
최소 한 마이크로초를 차지하도록 요구한다. 이는 구현 한계이며 더 작은 모든 수학적
duration이 MP4에서 불가능하다는 주장이 아니다.

<a id="runtime-consumption-audit"></a>

## Runtime 소비 감사

`worker/search_handlers.py`는 context 진입 시 합의된 Analysis 크기 제한 코드만
매핑한다. UNSUPPORTED_MEDIA는 여전히 `KindRegistry.dispatch`의 일반
RUNTIME_HANDLER_ERROR를 거쳐 기존 candidate-search 실패 notice에 도달한다.
검사한 분류 체계에는 합의된 UNSUPPORTED_MEDIA 전용 terminal/Case 매핑이 없다.
해당 매핑/조치는 Owner 결정으로 남으며 이 구현은 추가하지 않는다.
IncidentClip은 기존 INCIDENT_CLIP_BUILD_FAILED 공개 wrapper와
RECORDING_INCIDENT_CLIP_BUILD_FAILED Worker 매핑을 유지한다. 입력, checkpoint,
영속화, T1/T2, 호출자 트랜잭션 코드는 변경하지 않는다. 집중 기존 매핑 테스트는
알 수 없는 Recording 코드가 Runtime 실패로 남는 것을 명시적으로 다룬다.
