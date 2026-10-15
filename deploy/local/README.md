# RT-13(a) 로컬 Compose 초안

Python 3.12·ffmpeg image와 api·worker·MySQL 8.4 Compose 배치를 준비했다.
api와 worker는 같은 image·numeric UID(10001)를 사용하고, 같은 named media
volume을 `/srv/daesingo/media`에 mount한다. 일회성 `prepare-volumes` service가
두 process 시작 전에 media volume의 디렉터리 소유자를 맞춘다. Starlette upload
spool이 쓰는 `/tmp`에는 Compose tmpfs mount를 두지 않는다.

앱 설정 파일은 `/run/secrets/app_env`에 mount하고 `DAESINGO_ENV_FILE`에는
그 경로만 넣는다. MySQL password도 file secret으로 전달한다. service 환경변수에
secret 값은 없다. container log는 B-O1에 따라 20 MiB × 5개로 rotation한다.
API ready 호출은 4초, Docker healthcheck는 5초로 두어 B-H3 3초보다 길다.

## 로컬 준비

1. `deploy/local/app.env.example`을 `deploy/local/secrets/app.env`로 복사해
   DB URL password와 Search credential을 채운다. DB URL의 host는 `mysql`이다.
   password에 URL 예약 문자가 있으면 percent encoding한다.
2. `deploy/local/secrets/mysql-password`와
   `deploy/local/secrets/mysql-root-password`를 각각 만든다. 파일마다 password
   하나만 넣고, 첫 파일의 값은 앱 DB URL과 일치시킨다. 이 디렉터리는 Git에서
   무시한다. Linux host에서는 앱 설정 파일을 UID 10001이 읽을 수 있어야 한다.
   Compose file secret은 host 파일의 소유권·mode를 그대로 사용하므로 다른
   사용자가 읽지 못하도록 권한을 설정한다.
3. `docker compose config`로 service 구성을 확인한다. Secret 파일 값은 출력하지
   않는다. 선행 Runtime route와 migration 단계가 준비되면
   `docker compose up --build`로 실행한다.

이 branch는 RT-08(a) PR #366 위에 쌓였다. RT-09·RT-11도 아직 열려 있다.
Migration one-shot service, container 사이 upload/recovery smoke, clean-start
acceptance는 RT-13(b)에 남긴다. RD-12a/RD-12g의 service·volume·backup 결정과
Compose health/shutdown 값은 Runtime/Ops Owner의 Provisional 기록이 필요하다.
현재 Compose 설정은 검토용 후보이며 Accepted Decision이 아니다.
