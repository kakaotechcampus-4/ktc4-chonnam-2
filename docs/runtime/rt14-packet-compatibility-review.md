# B legacy / C chunked packet 조건 조사 — 제품 변경 없음

대상: B `ce0750d5a3317ad1c810783d67f8a05ba88bce08`, C 후보 `8d6a0979ff68e3273587ec08397ce05d92f4c865`. 이번 publish PR에서는 `docker/runtime.py`, Recording writer, `deploy/ec2.py`를 수정하지 않는다. 아래는 코드 대조와 후속안이며 운영 DB packet/config·실영상 SQL·메모리 측정은 NOT_RUN이다.

## 현재 실제 조건

`deploy/ec2.py`는 quiesce/MySQL 이후 migrate container의 `docker/runtime.py deploy-packet <policy margin>`을 호출한다. runtime은 실제 session max_allowed_packet=P를 읽고 Analysis 최대 bytes=M에 대해 `M + margin < P`를 요구한다. 세 값은 양의 정수여야 한다. B와 현재 C 모두 같은 runtime 검사를 갖고 writer format을 구분하지 않는다.

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

C의 총 media M이 P보다 커도 청크 command가 예산 안이면 SQL 전송은 가능하다. 따라서 현재 runtime의 M+margin<P는 C의 분할 저장과 맞지 않는 추가 제약이다. C writer가 실제 사용하는 budget·chunk_size 양수·각 command 예산과 정책 reserve를 확인해야 한다.

예시 P64MiB에서는 command budget1MiB, chunk size256KiB다. 작은 P에서는 크기를 줄이지만, P-64KiB 및 allowance가 너무 작으면 writer가 거부한다. 충분한 SQL packet은 metadata/메모리/전체 영상 지원의 충분조건이 아니다. materializer의 전체 bytes·detached read·temp·CPU·Search/Case budget과 Recording의 MAX_DURATION_MS/MAX_BYTES는 별도로 검증한다.

## 최소 후속안 — 이번에 구현하지 않음

1. **C 애플리케이션의** runtime deploy-packet이 실제 image 안 `PREPARED_WRITE_FORMAT`을 읽어 분기한다. host 입력/env로 writer를 위장하는 toggle은 만들지 않는다. 알 수 없는 format은 거부한다.
2. legacy는 기존 제약과 실제 escaping guard를 유지한다. 최대 입력 보장이 필요하면 별도 검증된 보수적 전체 command 상한을 추가한다. 고정 B 이미지는 수정되지 않으며 B에도 개선을 적용하면 B′ SHA/image가 필요하다.
3. chunked는 총 M을 packet과 직접 비교하지 않고 실제 command budget과 양수 chunk size를 검사한다. 최소한의 보수적 후속 형태는 기존 `check_packet(command_budget,P,margin)`를 재사용하는 것이다. 이는 정책 margin까지 남기기 위해 일부 작은 P를 더 보수적으로 거부할 수 있으며, writer 상수/계산과의 동기화를 검사해야 한다. 총 M의 양수·업무 한도 검증은 계속 유지한다.
4. 후속 RED/GREEN은 legacy의 M>P 거부·escaping 경계, C의 M>P/command<P 허용, budget+margin==P 거부, 너무 작은 P·잘못된 형식 거부를 포함한다. 실제 B/C 이미지·MySQL session·최대 metadata/IncidentClip·caller transaction을 별도 승인 자원에서 검증한다. 기존 guard·timeout을 완화하지 않는다.

**C 후보 8d6a0979의 runtime은 여전히 기존 검사다.** 새 publisher로 이 SHA를 build해도 packet 수정이 들어가지 않는다. 위 수정이 추가되면 C′ 전체 SHA·push CI·build/Web·image identity·immutable tag·registry digest와 config/승인/복구 근거를 다시 고정해야 한다. 기존 C 태그를 덮어쓰거나 새 코드에 옛 C revision을 붙이지 않는다.
