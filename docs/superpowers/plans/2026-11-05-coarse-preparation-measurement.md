# 전체 Coarse 준비 시간 측정 실행물 준비

**Goal:** #452의 동일15개·270p/CRF28·provider0 격리 측정에서 준비 단계만 유한하게 늘리고 터미널과 분리된 복구를 준비한다.

**Architecture:** 기존 full15 하네스·정확성/자원/egress guard를 재사용한다. 준비 예산900초를 package config→host→entry→runner에 결속하고 송신 직전 request guard는 기존150초를 유지한다. 새 세션 wrapper는 파일 stdio·유한 자식 수명·finally 복구를 사용하며 systemd ExecStopPost가 독립 복구 진입점을 제공한다.

**Constraints:** AWS/전송/운영중단/실험/provider/배포/commit/push/게시 금지. 실제 영상 대신 작은 합성 controls만 로컬 검증한다. 운영 Search/Case/디코더/품질/strict/cap 변경 금지. 원본·기존 scratch·volume 보존.

**Spec:** 사용자 2026-11-05 요청 및 #452 댓글6634374912·6634842630·6634926335. 현재 develop d3301e91은 깨끗했고 새 codex/issue452-coarse-preparation-deadline 브랜치를 만들었다. #564는 원격 merged지만 현재 checkout에는 없으므로 제품 정책 판단을 최신이라고 가정하지 않는다.

## 작업

- [x] 로컬425MB 보존물 inventory와 익명파일·격리DB·정리 코드 대조. 서버 잔존은 미확인, 재생성 경로를 기본으로 준비.
- [x] RED→GREEN: 기본150초 실패 대조, full+명시적270p mode에서만900초 허용, 완료 시각/최종크기/duration·기존guard·hook복원 기록.
- [x] RED→GREEN: scratch 복구 후보를 검토하고 public wrapper/복구 진입점 작성. 출력 write/flush/close·로그open 실패·자식실패/timeout·연결종료를 구분. 기존 실제 자동복구 원인은 UNKNOWN 유지.
- [x] 필요한 Windows focused186PASS/4Linux전용SKIP·lint·경계/계약·270파일package 구조 검증. Docker/서비스는 대역임을 구분.
- [ ] 실제 Linux pipe/signal/자식 수명4개와 실제systemd/격리Docker 복구 검증: 기존 자원gate 미달로 NOT_RUN. 기준 변경/정리/우회 없음.
- [x] 한국어 runbook:900초는 실측 완료시간 보장 아님. full3600초/host4200초/복구900초 유지, systemd 전체중단상태 반영 최소10200초(170분) 점검 여유로 교정. 새실행물 사전 검증창은 별도. 새 owner·검증된 revision/config·팀점검 창 없으면 실행 금지.

## 검토 초점

900초가 운영/Case/request deadline으로 새지 않는지,150초 실패출력의 최종크기 오인,예산이 부족한 점검창,stdout/log 실패가 finally 앞에서 발생하는지,SIGKILL시 ExecStopPost/호스트 장애시 수동복구 한계를 확인한다. 기존425MB 파일/DB를 허위 재사용하거나 닫힌 owner의 후보를 그대로 실행하지 않는다.

독립 fresh review에서 운영root host전달과 반복TERM 자식회수 P2를 확인해 control RED→GREEN으로 수정했다. 같은reviewer가 해소와 추가확정결함 없음을 읽기확인했다. 실제Linux/EC2 검증은 하지 않았다. 수동복구는 기존unit/restore 종료를 확인한 뒤에만 명시적인 새900초창을 허용하며 자동재연장은 없다.

최종 focused186PASS/4Linux전용SKIP(18.77초). 복구 전 다른stage 실행 거부 control과 문서의 중단→사전검증→남은10200초재확인→full 순서를 추가 검증/독립 재확인했다. 최종270파일 구조검증물은 새hash로 남기고 이전 구조검증물도 보존했다.


## 실제 Linux 복구 후속

기존 시작 gate의 RAM/디스크가 모두 부족해 실제 Linux/ExecStopPost/중복복구/잠금보존은 NOT_RUN 유지. 작업소유 실행중 process/container/임시volume0, 현재 scratch 디렉터리 논리12MB·삭제없는 확인된 회수량0B. 삭제/타 작업 중단 없이 조사만 했다.

90분은 systemd의 중단/stop-post/final 종료 타이머를 누락하므로 v256 기본경로 기준5200+5×940+300=10200초로 admission만 교정했다. 운영 Search/Case/900초준비/복구900초/실제unit타이머는 그대로다.6000/8000 거부→11000 허용 대조 RED2/GREEN 및 관련5 controls PASS, Ruff PASS. 전체회귀 재실행 없음. 변경후package 재생성은 디스크 여유 확보 뒤 필요하며 기존 package는 보존했다.

최신develop a6c975f는현재HEAD보다20커밋·25파일앞. Case대기/plate_image_ref·Web·MLAPI문서 변경을읽기대조, Recording/Search/하네스 변경은없음. 자동병합하지않았다. runbook §7과 새 scratch linux-recovery-followup-20261105에근거보존.


## 실제 Linux 무미디어 검증 완료

자원 재관측 RAM6534922240B/free10387951616B로 기존gate PASS. systemd255에서 기존 신호4개만4PASS,실제임시unit 정상/실패/관측단절/감독TERM/KILL/순차중복복구/복구실패잠금보존7시나리오PASS. source session/restore 코드를 실행하되 Docker/snapshot/health/frozen binding adapter는대역이다. 실제unit/자식수명/ExecStopPost는native이며실운영복구PASS와구분한다.

170분은 유효timer와조건부 순차상태 그래프로재확인,중복900초추가없음·startup90초는live admission 이전재검사로정산. timeout/하네스기능/기존tests파일변경없음. memory peak59797504B/OOM0·18PID identity잔존0·unit/slice잔존0·정리오류0. 원본/보호volume/기존증거유지. runbook §8과 linux-recovery-actual-20261105/attempt2에근거보존.

이전 NOT_RUN 체크박스는당시기록이다. native신호/임시systemd 경로는이후완료했고, 실제운영Docker·EC2복구·동시수동복구·전체timer소진/커널hang은NOT_RUN으로남는다. 전체회귀/실미디어/provider/배포/commit/push는하지않았다.
