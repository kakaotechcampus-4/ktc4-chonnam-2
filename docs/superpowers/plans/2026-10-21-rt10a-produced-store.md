# RT-10(a) 생성 객체 검증 gate

상태: IN_PROGRESS. 관련 이슈 #297(RT-10(a)).

요청된 범위는 기존 T1 원자성과 Case ProducedReader callable 안에서 Consult #346 O-1–O-3을 구현한다. 시작 시 최신 develop은 `596e8a162b71949e7b3189e994921bb6247aac4b`다. 계약·승인된 결정·기준선·다른 Owner 공개 영역의 변경은 계획하지 않는다.

1. 실패 확인: 구현 전에 불투명 JSON 스냅샷, 안정적인 execution/ordinal ref, 검증, reader 동작과 독립적인 MySQL 인수 검사 목록을 고정한다.
2. 통과 확인: 고정 runtime_0005 migration과 common 생성 객체 저장소를 추가한다. 추가 전용으로 동작하며 정확히 같은 재전달은 수락하고 충돌하는 재전달은 거부한다. 기존 외부 produced ref는 이 저장소에 중복 저장하지 않아도 유효하다.
3. 실패→통과: 내부 HandlerResult에 선택적 payload 객체를 연결하고, T1 영속화 재시도 전에 생성 ref를 결속한다. 종료 처리의 Connection으로 저장하고 COMMIT 결과 불명 복구에서 영속 payload를 검증한다. lease·취소 규칙은 보존한다.
4. 실제 MySQL로 종료 상태/payload 원자성, 양쪽 쓰기 실패 시 rollback, 중복/충돌/동시성, COMMIT 응답 소실, 재전달과 새 프로세스 조회를 검증한다. reader는 기본적으로 불투명 dict 하나를 반환한다. 여러 객체의 조립은 호출자가 주입하며 저장소는 도메인을 import하지 않는다.
5. 기존 검사·마감·workflow를 완화하지 않고 독립적인 필수 매개변수/계열 목록과 JSON/JUnit 누락 변조 시험을 추가한다.
6. 관련 회귀, 엄격한 MySQL 보고서 검사, 경계·계약 검사를 실행한다. 원래 실패와 성공한 재시도를 구분하고 인계 기록과 추가 전용 구현 로그에 소스 hash·한계를 기록한다.
7. 독립 리뷰를 위해 변경은 미커밋·미스테이징으로 남긴다. 실제 handler 등록, Case adapter/8-13, export, RT-11은 구현하지 않는다.

검토 중점: 복구된 종료 상태의 payload 누락, 재전달 시 payload 변경, lease 탈취, 외부 ref를 가진 여러 객체, 생산자의 객체 변경, 메모리 상태 없이 다른 프로세스에서 조회, 메타데이터/계열 또는 JUnit 누락이 gate를 통과하지 못함.
