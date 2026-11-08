# 후보 미리보기 호환 중간 release

최종 배포 대상은 고정 `bb29d750d23765a73b7b6853b22086648684a392`다. 운영 `70f1c47cbc7c08fa848d057687f7130047f1126c`는 신규 `CANDIDATE_VIDEO_PREVIEW`를 처리하지 못한다. controller가 현재 revision을 rollback_targets에 요구하므로, 새 작업을 만들지 않으면서 새 작업을 처리하는 중간 release를 먼저 배포한다. schema/queue가 같다는 이유만으로70f를 최종 후보의 rollback 대상으로 승인하지 않는다.

중간 release는 bb29 reader·Case 반영기·9종 Worker·chunk/envelope writer를 그대로 사용한다. `candidate_video.PREVIEW_REQUESTS_ENABLED=False`는 release 코드이며 환경변수·host 설정으로 변경하지 않는다. 신규 미리보기 발주/FAILED 재요청은 변이 전에 `case.command.not_allowed`로 거부하고, 아직 요청하지 않은 카드는 UNAVAILABLE다. 기존 PREPARING/READY/FAILED 읽기와 기존 PREPARING/READY 요청의 동일 작업 재사용, Worker 실행·T1/T2·재전달은 유지한다. 다른 기능·공개 샘플 정책·controller·migration·Recording 한도는 변경하지 않는다. Coarse600초 유지.

검증은 기존 canonical MySQL/strict JSON·JUnit/실제 report 변조 경로를 확장한다. 기존 C feature 회귀의 `final_preview_writer`는 C 데이터를 합성하는 명시적 fixture다. 이 fixture의 결과로 B production 기본값을 주장하지 않는다. 별도 기본값 검사와 mandatory `candidate_video/compatible_bridge`는 고정70f·고정bb29 소스를 실제로 archive/import하여 실제 API 기본 발주, 현재 bridge API 거부/재사용, 실제 bridge Worker clip/T1/T2, 양쪽 저장 영상 byte/hash, schema heads와 재전달을 확인한다. 기존 고정ce0750과70f의 Case/Worker/common 소스가 동일함도 검증해 기존 mandatory old-job 전환 matrix의 재사용 범위를 결속한다. assertion/skip/timeout을 완화하지 않는다.

배포 순서:

1. 중간 release merge 후 정확한 develop push CI 전체·secret scan·publish acceptance·immutable tag/digest를 검증한다. B SHA/digest는 실제 결과로 고정하며 문서에 예상값을 쓰지 않는다.
2. source70f의 활성/미반영 작업0·새 preview0과 기존 tuple·config·heads·volume·이전 image·Web을 대조한다. 보존 입력/샘플/설정/인증/migration/비용 원장/백업/증거는 유지한다. 폐기 시험을 보존하기 위한 대형 백업은 만들지 않는다. 필요한 최소 보호의 내용과 실제 복구 방법을 사실대로 기록하며, 설정 checkpoint를 DB/media 복원 PASS로 적지 않는다.
3. B approval은 schema_parent=실조회70f, rollback_targets=[70f,B], 기존 config 유지다. 실제 통과한 호환 근거와 보호 receipt를 결속해 기존 controller로 배포하고 revision/schema/API/Worker/Web/dirty/lock·자원을 확인한다. 진행 중 팀원 job은 취소하지 않는다.
4. 최종 고정bb29 approval은 schema_parent=실조회B, rollback_targets=[B,bb29]다.70f/e50을 넣지 않는다. 두 번째 전환 직전 같은 검사를 반복한 뒤 기존 controller로 배포한다. 실패하면 실제 durable phase·schema authority와 검증된 tuple을 확인하고 기존 명시적 rollback/reconciliation 절차를 따른다.
5. 최종 bb29 이미지는 원래 신규 발주 기본값을 가진다. B의 코드/이미지를 환경변수로 C처럼 꾸미지 않는다. bridge가 current로 code rollback돼도 schema authority의 최종 rollback_targets를 과거 B의 [70f,B] 목록으로 되돌리지 않는다. bridge가 develop의 임시 기본값인 동안 후속 release는 이 상태를 의식적으로 복귀시키고 새 SHA·CI·이미지로 고정해야 한다. 이미 고정된bb29 source/image는 변경하지 않는다.

실제 DB/이미지/운영 전환 결과는 해당 run의 증거가 생기기 전까지 NOT_RUN이다. 공개 정책 A 구현·공개 범위 확대·실제 provider 호출·26분 E2E 재실행은 이 중간 release의 범위가 아니다.