# 15개 전체 입력 로컬 준비 계획

사용자가 지정한 checkout·branch와 상세 작업 범위를 구현 기준으로 삼는다. 작성자가 순차 구현한다. 병렬 작업은 계약·배포 코드의 읽기 검토만 맡는다. commit·push·PR·외부 댓글 및 운영 실행은 하지 않는다.

## 설계

기존 120초 EC2 감독기·청크 저장 검증·phase observer·소유 정리를 재사용한다. 새 `full` stage는 원본 15개 전체와 소수초 끝점을 명시적으로 요구한다. 1200초 prefix 확대나 기존 운영 Compose 재사용은 전체 입력 검증을 대신하지 않는다. 제품 `src/`·Owner 계약·운영값은 수정하지 않는다.

새 보호 입력 도구는 기존 manifest와 원본을 읽기 전용으로 대조하고, 익명 fixture·logical placement·보호 전송 계획만 새 폴더에 만든다. 촬영 연속성은 UNKNOWN으로 유지한다. 유한 profile은 출력 512MiB·전체 scope 상한 1584174ms·runner 3600초와 RAM/temp/DB/disk 예산을 함께 결속한다. 이는 실험 중단 한도이며 완료 보장이나 운영 지원값이 아니다. Search 270p·CRF28은 명시적 송신 직전 중단 실험으로만 허용한다.

## 구현·검증 순서

- [x] manifest 순서/개수/VIDEO/소수초 전체 범위·변조·원본 불변 controls를 RED→GREEN으로 구현한다.
- [x] 전체 profile과 Linux 감독기/entry/패키지 연결, 단계 건너뛰기·자원 부족·송신 차단 controls를 RED→GREEN으로 구현한다.
- [x] 실제 15개 hash/stat/metadata를 대조하고 보호 증거를 새 scratch에 저장한다. encode·Docker·DB·provider는 이 대조에 필요하지 않다.
- [x] 코드 근거별 차단 표, Owner 판단, 유한 예산의 근거/한계, 로컬/운영 실행 위치·명령·기대·복구가 있는 한국어 runbook을 작성한다.
- [x] 관련 controls·경계·계약·quality·diff를 실행하고 변경 파일 전체와 PASS/NOT_RUN/확인 필요를 보고한다. 최초600초TIMEOUT은보존하고, 후속진단/회귀의실패포함결과는runbook §9에구분한다.

## 직접 검증·독립 검토 기록

전체 endpoint의 Decimal/float 비교 오류는 독립 검토에서 재현한 뒤 control RED→GREEN으로 수정했다. 다중 VIDEO 거부도 RED→GREEN으로 확인했다. 최종 focused160 PASS, 실제 원본15개 대조를 처음/마지막 두 번 수행해 hash/stat/metadata·manifest 불변을 확인했다. HEAD 제품과 현재 하네스를 묶은 로컬 무실행 package269파일의 build/unpack/verify PASS이며 실제 운영 config 없는 구조 검증물이다. 경계·계약·Runtime lint/type(Linux/Windows)·변경 하네스 lint PASS. 비-MySQL 회귀는 별도 유한600초 시도 결과를 runbook에 기록한다.

배포 검토에서 probe 후 즉시 exact 복귀·lock 해제, full resource_gate 인자 명시, 읽기/무료probe/유료E2E gate 분리를 보완했고 같은 reviewer가 해소를 확인했다. 실제 full 컨테이너·DB·provider·AWS·제품 배포는 실행하지 않았다.

## 후속 검토 — 기존 EC2 전체 완주 목표 유지

사용자 후속 지시를 기준으로 먼저 timeout을 좁혔다. Python/pytest 시작과수집은정상이며첫API TestClient의Windows asyncio socketpair fallback accept가sandbox에서멈추는것을stack으로재현했다. 같은첫테스트는호스트에서0.186초PASS, API239 PASS. 같은600초한도안의나머지partition실행도완료했고, 총14475선택node 누락/중복0을대조했다. 합계14431 PASS/22 FAIL/26 SKIP이며전체green을주장하지않는다.

실패21개는Windows symlink권한WinError1314, 나머지1개는detached close직후파일부재assertion이다. 후자는단독1/모듈18 PASS·임시폴더사후잔여0, 합성product/stdlib각200회관측에서stdlib의일시잔여만1회관측했다. 원래실패를지우거나cleanup/strict/허용오차를완화하지않는다. 잔존task process는초기/종료호스트조회0개이고다른작업을종료하지않았다.

이번후속의공개파일수정은계획과runbook 두문서뿐이다. 기존269패키지파일hash는현재와일치하므로새실행물을만들지않았다. 기존EC2무미디어/10초/120초PASS는원래revision의근거로보존하고, 현재frozen조합의EC2재검증은별도로남긴다.

실제input15 첫PTS0·마지막PTS259.60초·관측duration0.04초를확인했다. 기존ms FLOOR끝259.639668과exact끝259.64가같은마지막frame을선택하므로0.332ms를새RC blocker로분류하지않는다. 기존시간/coverage계약을유지한다. 전체showframes20초timeout은별도보존하고first/tail좁힌source관측과encode/strict미실행을구분한다.

provider 예산은기존retry/STALE/SDK제한과유한사용자동작수로계산한다. 최초I1C1F1=최대24, Fine3개=40, 필요시추가검색pass1회와각pass Fine3개까지의제안상한I2C2F6=80 HTTP시도다. 실제설정·허용동작/금액·추가실행절차를확인하되범용비용관리/새금액gate 구현을선행요구하지않는다. Case유한대기/late반영정책과Search270p 품질채택답변은별도필요하며180초성능최적화/4GiB보완으로범위를넓히지않는다.

후속증거/실패목록/명령/운영조건은runbook §9와새scratch `full15-followup-20261104`에보존한다. AWS·전송·서비스중단·provider·배포·commit·push·게시는실행하지않았다.

## 검토 초점

전체 대신 prefix 통과, 부동소수점 끝점 손실, 2개 전송 계획의 오용, 운영 reader/rollback 오판, 작은 표본의 선형 외삽, provider 비용의 승인 없는 채택을 우선 검토한다. 운영 정보가 없으면 가짜 config/image digest를 만들지 않고 실행 불가 상태를 남긴다.


## PR 준비 후속 — Linux22와 독립 fresh review

기존 Windows 전체14431 PASS/22 FAIL/26 SKIP·600초TIMEOUT을 보존하고 전체 회귀는 반복하지 않았다. 기존 Linux 격리 이미지·legacy 자원 예산에서 정확한 원래 실패22개를 실행해22 PASS/skip0(5.13초), cgroup peak79798272B·OOM0·경계별 자식0·소유 정리/보호 volume3개 보존 PASS를 확보했다. 처음의 오프라인 pytest/mount 준비 실패도 새 scratch에 남겼다. 실제 원본/운영 DB/provider는 연결하지 않았다.

독립 fresh reviewer가11개 전체 변경을 검토해 Coarse CPU journal의 공유 json.dumps hook 재귀 P2를 발견했다. provider 전용 참조 임시 교체/복원으로 최소 수정하고 두 control RED→GREEN을 확인했다. 실제 Linux 준비에서 발견한 init 로그의 runner 로그 덮어쓰기도 역할별 파일명으로 수정하고 보존 control RED→GREEN을 확인했다. 새3개는 Linux에서도3 PASS(2.99초), 전체 관련 controls163 PASS(신규full23 포함), ruff·경계/계약 PASS다. 제품 src/deploy/계약 변경은 없다.

원래 cleanup 실패는 직전8개 순서·monkeypatch 범위·동기 ffmpeg/reader 종료 코드·Windows TemporaryFile 경로를 독립 감사했다. 당시 PID/handle/file identity가 없어 원인은 미확정이며, 단독/모듈/Linux PASS로 원래 실패를 해결됐다고 쓰지 않는다. assertion/strict/skip을 완화하지 않았다.

두 하네스 수정 이후 현재 package269파일을 새 scratch에서 build/unpack/verify했다. 이전 package는 보존하되 현재 hash와 다름을 구분한다. 운영 config/image가 없는 실행 불가 구조검증물이며 새 실행물의 운영 환경 재검증 조건은 유지한다. 원본15개도 다시 hash/stat/metadata 대조 PASS다. 기존 EC2 실제26분 E2E·Package READY·다운로드는 NOT_RUN이다. 최종 근거·남은 Owner 답변·실행 순서는 runbook §10에 둔다. staging/commit/push/게시는 하지 않는다.
