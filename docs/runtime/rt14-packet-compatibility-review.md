# B legacy / C chunked packet 조건과 writer-aware 기동 검사

고정 baseline: B `ce0750d5a3317ad1c810783d67f8a05ba88bce08`, 기존 C `8d6a0979ff68e3273587ec08397ce05d92f4c865`는 변경하지 않는다. #589 publish 변경은 이 문서의 조사만 포함했으며 packet 제품 코드를 바꾸지 않았다. 이후 별도 `codex/rt14-chunked-packet-check` 작업에서 아래 writer-aware 검사를 구현한다. 이 미커밋 코드는 새 C′ 대상이며 아직 SHA/image/digest를 고정하지 않았다. 운영 DB packet/config·실영상 SQL·실제 이미지·메모리 측정은 **NOT_RUN**이다.

## 고정 baseline의 조건과 writer 예산

`deploy/ec2.py`는 quiesce/MySQL 이후 migrate container의 `docker/runtime.py deploy-packet <policy margin>`을 호출한다. 고정 B와 기존 C runtime은 실제 session max_allowed_packet=P를 읽고 Analysis 최대 bytes=M에 대해 `M + margin < P`를 요구한다. 세 값은 양의 정수여야 하며 두 고정 revision은 writer format을 구분하지 않는다. controller 호출과 기동 순서는 이번에도 유지한다.

| 경로 | Recording writer의 실제 기본 SQL 예산 |
| --- | --- |
| B legacy 신규 content | `budget=P-64KiB`. 전체 BLOB UPDATE의 실제 PyMySQL mogrify 길이+command byte가 budget 이하일 때만 전송 |
| C chunked 신규 content | `budget=min(1MiB,P-64KiB)`. `chunk_size=min(256KiB,(budget-16KiB)//2)`를 사용하며 양수여야 함. 모든 실제 command도 mogrify 길이+1≤budget 검사 |
| metadata/기존 ref 재전달 | media 총 크기만으로 metadata/descriptor command 크기를 증명하지 못함. 기존 exact·integrity·representation·원자성 guard도 별도로 유지해야 함 |

64KiB는 writer packet/protocol 여유,16KiB는 command allowance다. policy margin과 같은 변수라고 가정하지 않는다. Analysis M은 IncidentClip 전체 크기의 상한도 아니다.

### B에 필요한 조건

legacy는 실제 전체 content가 하나의 SQL command에 들어간다. binary escaping이 최대 약2배이므로 `M+margin<P`는 최악 content의 전송 성공을 보장하지 않는다. 정확한 조건은 각 SQL의 **실제 렌더 길이+1≤P-64KiB**다. 최대 크기 전체를 사전 보장하려면 `2*M + 검증된 SQL/quote overhead +1 ≤ P-64KiB` 같은 보수적 상한 근거가 별도로 필요하며 overhead 값을 임의로 정하지 않는다. metadata/IncidentClip 경로도 별도 대조한다.

예시일 뿐 실제 운영값은 아니다: M48MiB·margin8MiB·P64MiB는 현재 deploy-packet을 통과하지만,2배 escaping 경계에서는 content만 약96MiB여서 B writer가 전송 전에 거부할 수 있다. 이 거부를 없애려고 packet guard나 exact 검사를 완화하지 않는다. B는 중간 legacy release이며 긴 E2E writer로 사용하지 않는다.

### C에 필요한 조건

C의 총 media M이 P보다 커도 청크 command가 예산 안이면 SQL 전송은 가능하다. 따라서 고정 C runtime의 M+margin<P는 C의 분할 저장과 맞지 않는 추가 제약이다. C writer가 실제 사용하는 budget·chunk_size 양수·각 command 예산과 정책 reserve를 확인해야 한다.

예시 P64MiB에서는 command budget1MiB, chunk size256KiB다. 작은 P에서는 크기를 줄이지만, P-64KiB 및 allowance가 너무 작으면 writer가 거부한다. 충분한 SQL packet은 metadata/메모리/전체 영상 지원의 충분조건이 아니다. materializer의 전체 bytes·detached read·temp·CPU·Search/Case budget과 Recording의 MAX_DURATION_MS/MAX_BYTES는 별도로 검증한다.

## 새 C′의 최소 구현

1. runtime `check_prepared_packet`이 실제 image 안 `mysql_repository.PREPARED_WRITE_FORMAT`을 읽어 분기한다. host 입력/env로 writer를 위장하는 toggle은 없다. 알 수 없는 format은 거부한다.
2. legacy는 기존 제약과 실제 escaping guard를 유지한다. 최대 입력 보장이 필요하면 별도 검증된 보수적 전체 command 상한을 추가한다. 고정 B 이미지는 수정되지 않으며 B에도 개선을 적용하면 B′ SHA/image가 필요하다.
3. chunked는 총 M을 packet과 직접 비교하지 않는다. 기존 writer 계산을 `prepared_command_limits(packet, *, write_format, command_budget=None)`로 추출하여 **실제 writer와 runtime이 같이 사용**한다. 양의 정수 packet, 지원 형식, 유효한 optional cap, 양수 chunk size를 검증하고 runtime은 기존 `check_packet(command_budget,P,margin)`를 재사용한다. 이는 일부 작은 P를 더 보수적으로 거부할 수 있다. 총 M의 양수·업무 한도·MAX_DURATION_MS 설정 검증은 유지한다.
4. metadata·재전달·무결성·SAVEPOINT·RR·실제 SQL mogrify guard는 변경하지 않는다. M은 IncidentClip 전체 크기 상한이 아니며, startup 성공만으로 최대 metadata/IncidentClip·메모리·실제 데이터 호환을 승인하지 않는다. Coarse 600초/종료 후150초 복귀와 #583 분리는 유지한다.

예시 P64MiB·M256MiB·margin8MiB에서는 chunked budget1MiB/size256KiB로 기동 검사를 통과하고 legacy는 거부한다. P1MiB에서는 budget960KiB라 margin64KiB의 동등 경계를 거부하고 margin65535B는 통과한다. P81921B는 size0으로 거부한다. P81922B는 size1이므로 margin1B에서 계산상 통과할 수 있으나, 실제 metadata/SQL/메모리 수용 보장은 별도 guard·실측 대상이다. 예시는 운영값이 아니다.

## 검증과 배포 경계

`tests/deploy/test_packet_compatibility.py`는 실제 runtime main에 DB session 조회 경계만 대역으로 연결한다. 전체 M>P 성공과 legacy 부정 대조·unknown format·작은 P·budget+margin 경계·양수 MAX_BYTES·env 위장 무효를 RED→GREEN으로 검증한다. 고정 B 이미지를 실행한 것이 아니라 새 코드의 legacy 분기를 검증한 것이다. 실제 PyMySQL renderer와 기존 SQL guard를 연결한 offline 검사는 raw bytes가 budget 안이어도 렌더된 SQL이 초과하면 거부함을 확인한다.

실제 repository 기본값과 이미지 format 상수의 일치, shared policy 거부의 SQL 전파를 보강했다. DB DML 자체는 대역이므로 실제 MySQL 전송·rollback acceptance로 표시하지 않는다. 검증 결과와 Draft PR 본문은 Windows `.codex-scratch/chunked-packet-check/`에 기록한다. 실제 이미지·MySQL session·최대 metadata/IncidentClip·caller transaction·B→C′→B·backup/restore는 별도 승인 자원에서 검증해야 하며 이번에는 **NOT_RUN**이다. 기존 guard·assertion·skip·timeout·CI gate를 완화하지 않는다.

최종 offline 실행은 배포/secret-scan 회귀(controller 전용 파일 제외), chunk reader·metadata decoder·Recording 설정·기본 envelope/legacy·양수 업무 한도 설정을 포함해 **410 passed / failures0 / errors0 / skipped0**이다. 전체 테스트 suite와 실제 media/DB/image 검증 통과를 뜻하지 않는다. Ruff·경계 검사·diff 검사도 통과했다. 독립 리뷰 및 보강 테스트 재검토에서 잔여 확정 P1/P2는 없었다. reviewer는 실제 테스트/DB/image를 실행하지 않았다.

초기 테스트에서 설치된 PyMySQL의 bytes가 hex literal로 렌더됨을 확인해 합성 positive fixture를 바로잡았다(guard/budget은 유지). 제품 수정 전 재확인 RED는23 failed/22 passed이며 feature 부재와 unknown format 허용을 확인했다. 첫 GREEN의17 setup errors는 Windows 기본 temp 권한 문제로55 passed와 구분해 보존했다. 새 작업 전용 temp로72 passed, 관련392 passed, 리뷰 보강 후 최종410 passed를 확인했다. 기존 임시 파일/보호 증거는 삭제하지 않았다.

**고정 C 8d6a0979의 runtime은 여전히 기존 검사다.** 새 publisher로 이 SHA를 build해도 이번 수정은 포함되지 않는다. 이번 변경을 병합한 뒤 C′ 전체 SHA·push CI·build/Web·image identity·immutable tag·registry digest와 config/승인/복구 근거를 다시 고정해야 한다. 기존 C 태그를 덮어쓰거나 새 코드에 옛 C revision을 붙이지 않는다. C′ 이후 e50 rollback도 승인하지 않는다.
