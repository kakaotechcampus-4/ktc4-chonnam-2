# File-backed backup/restore Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline and one independent whole-change review. Staging/commit/push/publish/server work are forbidden.

**Goal:** 기존 host logical backup 도구의 대형 SQL 전체 메모리 경로를 파일 기반으로 바꾼다.

**Architecture:** SQL transport stdout·검증 SQL·재덤프는 작업 소유 임시 파일이며1MiB read/write로 처리한다. 기존 format1 envelope/heads/빈target/lock/180·600초/실제 byte비교는 유지하고 restore mysql client와실target64MiB를검사한다. hostCLI는 `--source-root`를필수로받아 source image에서취득한migrations를사용한다. 동일checkout의기존small smoke API는유지하되byte pack/unpack은1MiB로제한한다.

**Tech Stack:** Python stdlib, existing Docker Compose/mysql CLI; offline pytest only.

**Spec:** 사용자 요청 및 `.codex-scratch/rt14-b-cprime-transition-20261106/measured-budget-final-20261106.md`.

## Global Constraints

- branch `codex/rt13-file-backed-backup`, base `70f1c47cbc7c08fa848d057687f7130047f1126c`, 시작 clean.
- 수정범위: `scripts/backup_compose.py`, focused backup tests, 관련runtime 문서와이계획. 독립리뷰에서발견한 `scripts/smoke_backup_restore.py`의None.decode 연결문제는사용자의추가명시승인에따라해당연결부만최소수정.
- 실제 e50/B/C′ source의migrations와DBheads를결속한다. latest ROOT를e50으로위장하지않는다. source-root는명시적이며서버의실제source/이미지/hash provenance는운영자binding에서별도로확인한다.
- 현재dumpargv/skip-extended-insert·기존artifact형식·quiescence·빈target·lock·timeout 유지. 새toolhash/argv에크기근거재결속, olde50 D829309877을새argv의정확D로간주하지않음.
- B/C′ app source/image/digest, controller/workflow/config/Coarse600과종료후150조건/#583 변경없음. image 의존없음(Dockerfile에script COPY없음).
- Docker rebuild/대규모이미지복제/AWS/서버쓰기/서비스중단/추가dump/실제복원/배포/staging/commit/push/게시 금지. 기존원본·증거·volume 보존.

## Review Focus

- 큰stdout/stdin은 file fd, bounded read/write만 사용. 정상·손상·추가bytes의검증이import보다앞선다.
- artifact 바깥파일 교체/실패/cancel에서호출자자료를삭제하지않고,작업소유spool만정리한다.
- headers/json size/type·heads·EOF/hash/bytecmp·nativeproducer실패/부분write를fail-closed로다룬다.
- server64MiB가아니거나clientflag가잘못되면import전에거부한다. 서버SET/강제오류무시는없다.
- 고정Git e50/B/C′의실migration source roots와불일치부정대조,기존smoke호환을확인한다.

## Task: host 도구 최소 보완

- [x] 새focused 테스트: 유효 RED14failed/8passed(`red2.xml`), 이후 packet help명령오류무시 RED1failed/31passed(`shell3.xml`), adapter None.decode RED1failed/6passed(`adapter-red.xml`). 초기경로/Windows shell환경실패와기능RED를구분했다.
- [x] stdlib1MiB 파일copy/hash/검증/bytecmp, 소유spool/inode정리, 복원client/target GLOBAL·SESSION64MiB검사 구현. server SET없음.
- [x] 기존transportfake의파일fd적응. assertion/failure/collision/180·600timeout·skip-extended-insert 유지.
- [x] 최종focused94passed/0failed/0skip(`focused-final.xml`), 경계검사0위반, 변경Python4파일Ruff PASS. 기존smoke제품연결부파일은기존F401×2/F841×1이남고baseline과동일함을별도대조하며관련없는정리는하지않음.
- [x] e50/B/C′고정commit/tree와실제migration파일hash/heads확인 및각source-root fake-only왕복PASS(`fixed-source-binding/report.json`). 실제DB/큰artifact/peak는NOT_RUN.
- [x] 독립리뷰최초P2(adapter) 재현/수정/7PASS독립확인;후속기존P2해결/새P1·P2없음. 새toolhash/argv/변경목록·Draft PR본문은ignored증거폴더에준비. 운영실행없음.

## Completion evidence / limits

증거는 `.codex-scratch/file-backed-backup/`에 보존한다. 최종도구/file manifest와argv binding은
`tool-binding.json`, Draft PR은 `draft-pr.md`다. 기존source실측D829309877은oldtool+oldargv값이며
새skip-extended-insert옵션의정확D가아니다. 새도구의크기측정/현재데이터artifact/격리target실복원,
MySQL실client/server64MiB수용/byte-identical재덤프/180초수용/RAM·diskpeak/전체mandatorygate/원격CI는NOT_RUN.
Draft자료준비와운영실행/배포승인은구분한다. staging/commit/push/게시/서버작업은하지않았다.

Ruling: 사용자가 앞서 정리된 최소 설계의 구현을 명시적으로 요청했으므로 설계 재승인을 묻지 않는다. 기존 smoke가 사용하는 small pack/unpack은 bounded compatibility helper로 유지하고 실제CLI에는 쓰지 않는다. source-root CLI 필수화는 e50에 최신checkout heads를 잘못 적용하는 것을 피하기 위한 범위 내 변경이다.
