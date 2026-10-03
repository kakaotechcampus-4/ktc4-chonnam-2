# Research Result — API ↔ Worker Media Persistence / Upload

**Status:** Evidence — 외부 기술 조사 결과 · **보조 검토 완료 2026-10-03 · Owner 확인 전** — 정정 사항은 [Review notes](#review-notes-2026-10-03)가 본문보다 우선\
**Owner:** common/runtime — 김준영\
**Workflow step:** [`runtime-ops-workflow.md`](../runtime-ops-workflow.md) §4 Decision-driven 외부 기술 조사\
**Prompt:** [`prompts/02-api-worker-media-persistence-upload.md`](./prompts/02-api-worker-media-persistence-upload.md)\
**Decisions:** [RD-17](../open-decision-register.md#rd-17--api--worker-recording--source-persistence-boundary) (17a · 17b, 인접 17c · 17d) · [RD-05](../open-decision-register.md#rd-05--http-api-contract와-transport-담당) (05e)\
**조사 기준일:** 2026-10-03

> 이 문서는 Decision 근거이며 결정이 아니다. 내용은 Owner 검토를 거쳐 Spec · Contract · ADR로 옮겨질 때만 효력이 있다. 외부 자료의 숫자는 대신고 baseline이 아니다.

## Review notes (2026-10-03)

> 이 절이 본문보다 우선한다. 본문은 조사 원문 그대로 두었다. 검토는 Claude Code 보조 검토이며 Owner 최종 확인 전이다. **★** = 검토 뒤 원문(공식 문서 · repo)을 다시 열어 재확인한 항목, 표시 없음 = 검토 단계에서 인용 출처와 대조한 항목.

**판정:** 아래 정정을 반영하면 RD-17a · 17b · 05e(인접 17c · 17d)의 Decision 근거로 쓸 수 있다. 출처 대조 24건 — 일치 20 · 부분 일치 3 · 인용 출처에 없음 1 · **반대 0**. 명시된 library 버전 · 날짜(FastAPI 0.142.2 · Starlette 1.7.0 · python-multipart 0.0.32 · Uvicorn 0.54.0)는 PyPI와 일치한다. 최종 선택 문장 · 외부 숫자의 baseline화 · 범위 밖 내용은 없다.

### 정정 · 보완

| Sev | 본문 위치 | 정정 | 근거 |
| --- | --- | --- | --- |
| Med | §1 · §3 · §4.3 · §6 RD-17a `rename()` | 조건은 「같은 mounted filesystem」이 아니라 **같은 mount point**다. man page는 같은 filesystem이 두 곳에 mount돼 있어도 mount point가 다르면 `EXDEV`라고 쓴다. Docker에서는 bind mount · volume이 각각 별도 mount이므로, 같은 root EBS 위라도 staging과 final이 서로 다른 volume이면 rename이 실패한다. §6 「원본과 파생 asset을 같은 volume에 둘지 나눌지」에 직접 걸린다 | [rename(2)](https://man7.org/linux/man-pages/man2/rename.2.html) `EXDEV` |
| Med | §1 · §3 · §4.7 body limit | `max_body_size` · `RequestBodyLimitMiddleware`는 Starlette **1.6.0 이상**에만 있다. FastAPI 0.142.2의 의존성 하한은 `starlette>=0.46.0`이라 FastAPI만으로는 보장되지 않는다. 현재 repo에는 fastapi · starlette pin이 없다 | FastAPI 0.142.2 `pyproject.toml` · Starlette 1.6.0 tag |
| Med | §3 · §4.5 · §4.8 Pattern 1 | 누락: FastAPI는 `await request.form()` 직후 `UploadFile`을 request 종료 시 close하도록 등록한다. 따라서 202 응답 뒤에는 temp spool이 사라진다 — Worker가 보려면 **응답 전에** managed 위치로 옮겨야 한다. RD-05e에 직결된다 | FastAPI 0.142.2 `fastapi/routing.py`(`file_stack.push_async_callback`) |
| Med | §3 · §4.5 container `/tmp` | 누락(Interpretation): 기본 container `/tmp`는 container writable layer라 root EBS의 Docker 저장 영역에 쌓인다. Compose에서 `/tmp`를 `tmpfs`로 잡으면 spool이 **RAM**을 쓴다. §8 Spike E 조건에 「`/tmp`가 tmpfs인지」를 넣는다 | Compose `tmpfs` 옵션 |
| Med | §3 · §8 Spike E · F temp 파일 | Python `TemporaryFile`은 Linux에서 `O_TMPFILE`이거나 생성 직후 unlink된다. 따라서 (a) hard kill 뒤에도 Starlette spool 잔여 파일은 남지 않는다(Part B Q5의 답), (b) 사용 중 용량은 `du` · `ls`로 보이지 않고 `df` · `lsof +L1` · `/proc/<pid>/fd`로 본다 | [tempfile (3.12)](https://docs.python.org/3.12/library/tempfile.html) |
| Med | §6 RD-17a | prompt에 없던 기존 guardrail: Ops §11 「50GB local disk를 장시간 원본의 영구 저장소로 설계하지 않는다」. shared volume을 원본 보존소로 보는 후보는 이 원칙과 대조해야 한다 | [`ops-spec.md`](../ops-spec.md) §11 |
| Low | 여러 곳 | §1 「독립 지표로 관찰해야 한다」 · 「protocol이 필요하다」는 단정형 → 조건형으로 읽는다. §1 body limit bullet 후반의 「별도 limit이 필요하다」는 implication · §4.3 「partial file을 발견하는 시간을 없앤다」는 Interpretation · durability(fsync) 주장의 출처는 rename(2)가 아니라 fsync(2) · Content-Length early rejection은 문서가 아니라 source(`middleware/body_limit.py`)에만 있고 app이 처음 `receive()`할 때 일어남 · tus 「maximum size」는 extension이 아니라 `Tus-Max-Size` header · §6 「API container가 쓴 file을 Worker에 mount하지 않았다」는 결함이 아니라 미정(compose 파일 · upload endpoint가 아직 없음) · Nginx `proxy_request_buffering` **기본값 on**, chunked 요청은 설정과 무관하게 buffering될 수 있음 · Uvicorn `--limit-concurrency`(초과 시 503)와 `Expect: 100-continue` 동작 누락 · orphan · stuck upload 정리는 Ops §10의 External Source / Managed Source Copy 구분과 연결 · 인용 링크 일부가 `blob/main` · Python 3.16 문서 → tag 고정 링크로 읽을 것 | 각 공식 문서 · source |

### Daesingo 사실 보강 (repo)

- `recording/materialization.py`는 ffprobe · ffmpeg를 `-protocol_whitelist file`로 실행한다 → Object Storage 후보에서는 처리 전 local materialization이 「가능성」이 아니라 현 구조상 필수다.
- 같은 파일의 `_snapshot` 비교는 **변환 도중** 원본 변경은 감지하지만, 시작 시점에 이미 partial인 파일은 감지하지 못한다 → publish 패턴(§4.3)의 필요성과 연결된다.
- cross-container `flock`은 공식 문서 근거가 없다 — 본문 §9가 Interpretation으로 둔 분류가 맞다. §8 Spike B에 「서로 다른 두 volume 사이 rename(EXDEV)」 케이스를 추가한다.

---

**버전 기준:** FastAPI **0.142.2** (2026-09-30), Starlette **1.7.0** (2026-09-23), `python-multipart` **0.0.32** (2026-06-04), Uvicorn **0.54.0** (2026-09-25), Python **3.12** 문서 계열을 기준으로 확인했다. ([pypi.org](https://pypi.org/project/fastapi/0.142.2/))

---

## 1. Executive Summary

- **Verified fact** — Docker의 bind mount와 named volume 모두 여러 container가 같은 파일을 볼 수 있게 할 수 있다. 차이는 bind mount가 **host의 지정 경로**를 그대로 연결하는 반면, named volume은 Docker가 host 내부 저장 위치와 lifecycle을 관리한다는 점이다. Named volume은 container가 재생성되어도 남지만 `docker compose down -v`의 삭제 대상이다. ([docs.docker.com](https://docs.docker.com/engine/storage/bind-mounts/))
- **Daesingo implication — RD-17a** — shared mount는 **영상 bytes의 process/container 경계**만 해결한다. 현재 `sa_*`, `ms_*`, locator, timeline이 process-local dict에 있는 문제는 별도로 남는다. Worker가 같은 path를 볼 수 있어도 어떤 파일이 어떤 ref인지 알 수 없기 때문이다.
- **Verified fact** — Linux에서 `temp → rename(final)`은 같은 mounted filesystem 안이면 pathname 교체가 atomic하다. 서로 다른 mount를 넘으면 `EXDEV`가 발생한다. `rename()`의 atomic visibility와 crash/power-loss durability는 별개이며, 후자까지 보장하려면 file `fsync()`와 경우에 따라 containing directory `fsync()`까지 고려해야 한다. ([man7.org](https://man7.org/linux/man-pages/man2/rename.2.html))
- **Interpretation — RD-17a/RD-17b** — 파일과 metadata가 filesystem + MySQL처럼 서로 다른 저장소에 있으면 하나의 평범한 DB transaction으로 둘을 동시에 commit할 수 없다. 따라서 어떤 후보를 택해도 `file exists / row missing`, `row exists / file missing`, `IN_PROGRESS 상태에서 crash` 같은 중간상태를 다루는 protocol이 필요하다.
- **Verified fact** — 현재 Starlette 1.7.0의 multipart file은 `SpooledTemporaryFile(max_size=1,048,576)`를 사용한다. 즉 기본적으로 file part마다 최대 **1 MiB까지 memory spool**, 그 이상은 Python temporary file로 rollover된다. 이 값은 **library default**일 뿐 대신고 업로드 한도가 아니다. ([github.com](https://github.com/Kludex/starlette/blob/main/starlette/formparsers.py))
- **Verified fact** — 현재 `request.form(max_part_size=...)`의 `max_part_size`는 업로드된 **file part의 최대 크기가 아니다**. Starlette 1.7.0 문서와 source 모두 file part는 이 검사에서 제외되고 temporary storage로 spool된다고 명확히 한다. 전체 영상 크기 제한은 별도의 total request-body limit이 필요하다. ([starlette.io](https://www.starlette.io/requests/))
- **Verified fact** — FastAPI에서 `File`/`UploadFile` dependency를 선언한 일반 endpoint는 FastAPI가 먼저 `await request.form()`을 끝낸 뒤 dependency 해결과 endpoint 실행으로 넘어간다. 따라서 큰 영상은 endpoint 함수에 진입하기 전에 이미 Starlette temp storage에 전부 수신·파싱된 상태가 된다. 단, 이는 “전부 RAM에 적재”된다는 뜻은 아니다. large file은 spool disk로 내려간다. ([raw.githubusercontent.com](https://raw.githubusercontent.com/fastapi/fastapi/0.142.2/fastapi/routing.py))
- **Daesingo implication — RD-05e** — 이 표준 경로에서 수신 완료 후 `UploadFile`을 managed source 위치로 다시 복사한다면, 큰 영상은 구조적으로 **Starlette temp disk write → managed source disk write**의 두 단계가 된다. 앞에 Nginx처럼 request buffering을 하는 proxy가 있다면 proxy temp write가 하나 더 생길 수 있다.
- **Verified fact** — Starlette는 1.6.0부터 total raw request body를 제한하는 `max_body_size`/`RequestBodyLimitMiddleware`를 제공한다. 반면 FastAPI 0.142.2의 `FastAPI()` 생성자는 이를 직접 노출하지 않으며, 알 수 없는 keyword는 `extra`에 저장되고 FastAPI에서 사용되지 않는다. Starlette middleware 자체는 FastAPI 같은 ASGI app에 명시적으로 적용할 수 있다. ([starlette.io](https://www.starlette.io/release-notes/))
- **Interpretation — resource pressure** — 업로드 크기 분포가 아직 없으므로 “RAM이 먼저” 또는 “disk가 먼저”라고 외부 조사만으로 단정할 수 없다. 대신고에서는 Worker가 이미 영상 bytes를 RSS에 쌓는다는 관측이 있으므로 **Worker RSS/OOM 위험과 API upload temp/final disk 위험을 독립 지표로 관찰**해야 한다.

---

## 2. Questions Investigated

### Part A — RD-17a · RD-17b

조사 범위는 다음까지 포함했다.

1. bind mount / named volume의 host 노출, 초기 content copy, lifecycle, `down -v`, container recreation.
2. non-root container의 UID/GID와 host ownership 관계, user namespace가 켜진 경우의 차이.
3. partial file visibility, same-filesystem rename, `fsync`.
4. 동일 filesystem에 대한 `flock()`/file-lock semantics.
5. delete-while-open, stale reference, orphan file.
6. process/container/host restart 시 파일과 metadata가 각각 받는 영향.
7. MySQL + shared filesystem, sidecar, shared SQLite, Object Storage + DB의 persistence 패턴.
8. 파일과 metadata가 서로 다른 저장소일 때의 split-success failure.
9. S3를 선택 결론 없이 비교 대상으로만 검토.

### Part B — RD-05e · RD-17a

1. FastAPI → Starlette → `python-multipart`의 실제 multipart 처리 경로.
2. `SpooledTemporaryFile` threshold와 temp directory.
3. endpoint 진입 전 parsing 여부.
4. `request.stream()` raw streaming과 직접 multipart parser 사용.
5. Starlette/FastAPI/Uvicorn/Nginx/Caddy의 request-size 제한 층.
6. disconnect/error 시 temporary file cleanup.
7. single EC2에서 RAM/temp/final-source/Worker 사이의 resource competition.
8. one-shot upload, upload-session/finalize, checksum, tus, S3 presigned direct upload 패턴.

---

## 3. Verified Technical Facts

| Fact | Version / Condition | Evidence |
|---|---|---|
| **Verified fact** — bind mount는 Docker host의 특정 file/directory를 container path에 mount한다. 기본은 writable이며 `ro` 가능하다. Host directory 구조에 직접 의존한다. | 현재 Docker Engine docs | ([docs.docker.com](https://docs.docker.com/engine/storage/bind-mounts/)) |
| **Verified fact** — named volume은 Docker가 생성·관리하며 container writable layer와 lifecycle이 분리된다. 여러 container가 동시에 동일 volume을 mount할 수 있다. | 현재 Docker Engine docs | ([docs.docker.com](https://docs.docker.com/engine/storage/volumes/)) |
| **Verified fact** — empty named volume을 image 안의 non-empty directory 위에 처음 mount하면 기존 contents가 기본적으로 volume에 copy된다. `nocopy`로 막을 수 있다. 기존 non-empty volume은 image 내용을 가린다. | Docker local volume | ([docs.docker.com](https://docs.docker.com/engine/storage/volumes/)) |
| **Verified fact** — `docker compose down` 기본 동작은 named volume을 없애지 않는다. `down -v`는 Compose가 선언한 named volume과 attached anonymous volume을 제거한다. `external` volume은 제거하지 않는다. | Docker Compose | ([docs.docker.com](https://docs.docker.com/reference/cli/docker/compose/down/)) |
| **Verified fact** — named volume contents는 container가 삭제되어도 유지된다. Docker는 unused volume을 자동으로 삭제하지 않는다. | Docker Engine | ([docs.docker.com](https://docs.docker.com/engine/storage/volumes/)) |
| **Verified fact** — bind mount를 container의 기존 directory 위에 올리면 image에 있던 contents는 copy되지 않고 단순히 가려진다. | Docker Engine | ([docs.docker.com](https://docs.docker.com/engine/storage/bind-mounts/)) |
| **Verified fact** — named volume은 Docker CLI/API로 관리하며 Docker docs는 별도 container를 통해 tar backup/restore하는 절차를 제공한다. Bind mount는 host path 자체가 운영자에게 직접 노출된다. | current docs | ([docs.docker.com](https://docs.docker.com/engine/storage/volumes/)) |
| **Verified fact** — Docker는 image user에 명시적 UID/GID를 둘 수 있고, user namespace/rootless를 사용하면 container UID/GID와 host UID/GID가 remap된다. Bind-access permission은 이 mapping의 영향을 받는다. | Linux Docker Engine | ([docs.docker.com](https://docs.docker.com/engine/security/rootless/uid-gid-mapping/)) |
| **Verified fact** — Compose volume syntax에는 일반 named volume의 content ownership을 자동으로 API/Worker user에 맞춰주는 portable `uid`/`gid` 옵션이 없다. `read_only`와 `nocopy`는 제공된다. | Compose Specification | ([docs.docker.com](https://docs.docker.com/reference/compose-file/services/)) |
| **Verified fact** — Linux `rename()`은 target이 존재해도 atomic replacement를 제공하지만 source/target이 서로 다른 mounted filesystem이면 `EXDEV`로 실패한다. | Linux man-pages 6.19 | ([man7.org](https://man7.org/linux/man-pages/man2/rename.2.html)) |
| **Verified fact** — `fsync(file)`은 file data/metadata durability를 다루지만 directory entry의 persistence까지 반드시 보장하지는 않는다. Directory 자체에 별도 `fsync()`가 필요할 수 있다. | Linux | ([man7.org](https://www.man7.org/linux/man-pages/man2/fsync.2.html)) |
| **Verified fact** — Unix `unlink()` 후에도 누군가 그 file descriptor를 열고 있다면 기존 opener는 계속 파일을 사용할 수 있고 storage는 마지막 descriptor가 닫힐 때 해제된다. | Linux | ([man7.org](https://man7.org/linux/man-pages/man2/unlink.2.html)) |
| **Verified fact** — `flock()`은 advisory lock이다. cooperating process가 lock을 지켜야 의미가 있고 Linux local filesystem에서는 `flock`과 POSIX `fcntl` record lock은 서로 다른 locking 계열이다. | Linux | ([man7.org](https://www.man7.org/linux/man-pages/man2/flock.2.html)) |
| **Verified fact** — SQLite는 별도 process의 동시 접근을 지원하지만 rollback-journal mode에서는 locking을 사용하고 충돌 시 `SQLITE_BUSY`가 날 수 있다. | SQLite 3 | ([sqlite.org](https://www.sqlite.org/lockingv3.html)) |
| **Verified fact** — SQLite WAL은 reader와 writer를 병행할 수 있지만 writer는 한 번에 하나이며 WAL shared-memory 때문에 서로 다른 host의 network filesystem 사용을 지원하지 않는다. | SQLite WAL | ([sqlite.org](https://sqlite.org/wal.html)) |
| **Verified fact** — S3는 successful PUT 이후 strong read-after-write consistency를 제공하고 single object key update는 atomic하다. | current AWS S3 | ([docs.aws.amazon.com](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html)) |
| **Verified fact** — Starlette `UploadFile.file`은 `SpooledTemporaryFile`이다. 현재 `MultiPartParser.spool_max_size` 기본값은 `1024*1024` bytes다. | Starlette 1.7.0 | ([starlette.io](https://www.starlette.io/requests/)) |
| **Verified fact** — `SpooledTemporaryFile`은 threshold 초과 또는 `fileno()` 호출 시 on-disk `TemporaryFile`로 rollover한다. | Python 3.12 | ([docs.python.org](https://docs.python.org/ko/3.12/library/tempfile.html)) |
| **Verified fact** — Starlette는 `SpooledTemporaryFile` 생성 시 `dir=`를 지정하지 않는다. 따라서 Python temp directory selection을 따른다. `TMPDIR`, `TEMP`, `TMP`, 그 후 Unix에서는 `/tmp`, `/var/tmp`, `/usr/tmp`, 마지막으로 cwd 순이다. | Python 3.12 + Starlette 1.7 | ([docs.python.org](https://docs.python.org/ko/3.12/library/tempfile.html)) |
| **Verified fact** — `max_part_size`는 현재 multipart **non-file field**에만 적용되며 uploaded file bytes는 이 check를 통과하지 않는다. | Starlette 1.7.0 | ([starlette.io](https://www.starlette.io/requests/)) |
| **Verified fact** — Starlette parser는 network stream을 chunk 단위로 `python-multipart` parser에 공급하고 file chunks를 `UploadFile.write()`로 spool한다. | Starlette 1.7.0 | ([github.com](https://github.com/Kludex/starlette/blob/main/starlette/formparsers.py)) |
| **Verified fact** — `python-multipart` 자체는 callback 기반 streaming parser이며 parser-level `max_size`의 기본은 unbounded다. Starlette의 현재 `MultiPartParser` 생성 코드는 이 `max_size`를 넘기지 않는다. | python-multipart 0.0.32 + Starlette 1.7 | ([multipart.fastapiexpert.com](https://multipart.fastapiexpert.com/api/)) |
| **Verified fact** — `Request.stream()`은 entire body를 memory에 저장하지 않고 ASGI body chunks를 전달한다. 이후 `.body()`, `.form()`, `.json()`을 사용할 수 없다. | Starlette 1.7 | ([starlette.io](https://www.starlette.io/requests/)) |
| **Verified fact** — 반대로 `Request.body()`는 chunks를 모아서 `b"".join()`한다. 즉 large raw request에서 이를 사용하면 complete body materialization이 가능하다. | Starlette source | ([github.com](https://github.com/Kludex/starlette/blob/main/starlette/requests.py)) |
| **Verified fact** — client disconnect가 stream에 전달되면 `Request.stream()`은 `ClientDisconnect`를 raise한다. Multipart parser는 parsing/stream exception 경로에서 생성한 spooled temporary files를 close한다. | Starlette current source | ([github.com](https://github.com/Kludex/starlette/blob/main/starlette/requests.py)) |
| **Verified fact** — `TemporaryFile`은 Unix에서 directory entry를 만들지 않거나 생성 직후 unlink하며 close되면 storage가 정리된다. `SpooledTemporaryFile` rollover 이후 이 semantics를 따른다. | Python tempfile | ([docs.python.org](https://docs.python.org/3.16/library/tempfile.html)) |
| **Verified fact** — Starlette 1.6.0부터 total raw request body bytes를 제한하는 `max_body_size`가 추가됐으며 `RequestBodyLimitMiddleware`는 Content-Length를 이용한 early rejection과 실제 수신 byte counting 모두 수행한다. 초과 시 413이다. | Starlette ≥1.6 | ([starlette.io](https://www.starlette.io/release-notes/)) |
| **Verified fact** — FastAPI 0.142.2의 unknown `FastAPI(...)` keyword는 `extra`에 저장되고 FastAPI에서 사용되지 않는다. 따라서 `FastAPI(max_body_size=...)`를 Starlette 설정과 동일한 것으로 취급할 수 없다. | FastAPI 0.142.2 | ([github.com](https://github.com/fastapi/fastapi/blob/master/fastapi/applications.py)) |
| **Verified fact** — Uvicorn은 buffered request body가 high-water mark에 도달하면 transport reading을 pause하고 application이 `receive()`할 때 resume하는 read flow control을 사용한다. | Uvicorn current docs | ([uvicorn.org](https://www.uvicorn.org/server-behavior/)) |
| **Verified fact** — Uvicorn current settings의 `--h11-max-incomplete-event-size`는 **h11 incomplete event buffer** 제한이며 upload/request total-body limit이 아니다. | Uvicorn 0.54 docs | ([uvicorn.org](https://www.uvicorn.org/settings/)) |

### Version-sensitive note

Starlette upload protection은 최근에 꽤 바뀌었다. `max_part_size`는 0.40.0에서 security fix로 들어왔고, 이후 request API 노출과 form-limit 수정이 이어졌으며, **total request-body limit은 1.6.0(2026-08-08)** 에 추가됐다. 따라서 2024~2025 예제를 현재 동작으로 그대로 가져오면 안 된다. ([starlette.io](https://www.starlette.io/release-notes/))

---

## 4. Options / Patterns

### 4.1 파일 공유 경계 — RD-17a

| 후보 | 확인된 성질 | Trade-off |
|---|---|---|
| **Bind mount** | **Verified fact:** API와 Worker가 같은 host directory를 mount할 수 있다. Worker 측을 `ro`로 mount하는 것도 가능하다. ([docs.docker.com](https://docs.docker.com/engine/storage/bind-mounts/)) | **Interpretation:** host에서 파일·용량을 직접 확인/backup하기 쉽다. 반면 deploy host directory 구조와 ownership/permission을 운영 계약 일부로 만든다. |
| **Named volume** | **Verified fact:** Docker가 저장 위치/lifecycle을 관리하며 두 service가 같은 volume을 사용할 수 있다. Container recreation과 분리된다. ([docs.docker.com](https://docs.docker.com/reference/compose-file/volumes/)) | **Interpretation:** Compose 쪽 abstraction은 높지만 host에서 media directory를 직접 다루는 운영은 bind보다 간접적이다. `down -v`나 volume prune 계열의 운영 실수도 별도 failure mode다. |
| **Object Storage adapter** | **Verified fact:** successful S3 PUT 뒤 다른 process가 같은 key를 읽을 수 있고 single-key visibility가 atomic하다. ([docs.aws.amazon.com](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html)) | **Interpretation:** local shared pathname 자체가 없어지고 Worker 처리 전에 local materialization/cache 또는 다른 I/O integration이 필요하다. Storage/request/network/IAM 비용·실패가 새 축으로 생긴다. |

**Daesingo implication — RD-17a:** Worker는 현재 원본을 `ffmpeg`/`ffprobe` local path로 읽는 구조이므로 bind/named volume은 “같은 local path abstraction”을 유지할 수 있다. Object Storage는 storage adapter에서 “object reference → Worker-local readable artifact” 경계를 추가한다.

---

### 4.2 UID/GID · permission pattern

**Interpretation:** 일반 Linux Docker 환경에서는 username 문자열보다 실제 numeric UID/GID와 filesystem mode가 중요하다. API가 UID 1000으로 만든 파일을 Worker UID 1001이 읽으려면 file/directory mode 또는 group membership이 이를 허용해야 한다. User namespace/rootless가 켜지면 host-side ID mapping까지 달라진다. ([docs.docker.com](https://docs.docker.com/engine/security/rootless/uid-gid-mapping/))

일반적인 pattern은 API와 Worker가 공통 supplemental group을 가지며 shared directory를 그 group 소유로 두고, setgid directory + cooperative umask를 사용하는 형태다. 이 패턴은 **선택 결론이 아니라 permission coordination option**이다.

**Unverified detail:** fresh named volume의 root directory ownership을 모든 Docker/driver/image 조합에서 어떤 UID/GID로 초기화한다고 Compose specification이 portable하게 보장하지는 않는다. Empty-volume prepopulation이 개입하면 image-side ownership도 영향을 준다. 따라서 실제 image의 `USER`, volume 생성 방식, 첫 mount 직후 `stat` 결과는 spike 항목이다.

---

### 4.3 완성 파일 publish pattern

**Verified fact:** 같은 filesystem 안에서

`hidden/staging file → close/write completion → rename(final)`

형태는 consumer가 final pathname에서 partial file을 발견하는 시간을 없앨 수 있다. `rename()`은 same mounted filesystem 조건이 필요하다. ([man7.org](https://man7.org/linux/man-pages/man2/rename.2.html))

**Interpretation:** container `/tmp/upload-xyz`에서 shared volume `/media/source.mp4`로 rename하면 `/tmp`와 `/media`가 별도 mount일 가능성이 높아 `EXDEV`가 날 수 있다. 이 경우 library가 copy+unlink로 fallback하면 그 copy 자체는 atomic publish가 아니다.

따라서 이 pattern을 후보로 실험하려면 **staging과 final이 같은 shared filesystem에 있는지**가 핵심 조건이다.

**Interpretation:** `rename()`은 “다른 process가 partial final name을 보지 않는다”는 visibility 문제와 관련 있고, “EC2가 바로 crash해도 마지막 bytes와 directory entry가 반드시 durable하다”는 문제는 `fsync` 계층의 별도 선택이다. ([man7.org](https://www.man7.org/linux/man-pages/man2/fsync.2.html))

---

### 4.4 metadata persistence — RD-17b · RD-17c · RD-17d

#### A. MySQL metadata + shared filesystem media

**Interpretation:** 기존 MySQL에 예를 들어 opaque ref, internal storage key/relative locator, media type, size/checksum, registration state, timeline metadata 등을 두고 media bytes는 shared filesystem에 둘 수 있다.

장점은 이미 API와 Worker 모두 접근 가능한 DB가 persistent ref lookup point가 된다는 것이다. `sa_*`/`ms_*`를 row identity로 보존하면 restart 뒤 동일 ref를 다시 생성할 필요 없이 **same ref → same stored locator** mapping을 읽을 수 있다.

그러나 filesystem write와 MySQL transaction은 한 저장소 transaction이 아니다.

가능한 crash window는:

`file 완성 → DB 등록 전 crash` → **orphan file**

`DB row READY → file publish 실패/삭제` → **stale reference**

`PENDING row 생성 → upload 중 crash` → **stuck/incomplete registration**

이다.

일반 대응 pattern은 `PENDING/UPLOADING → FINALIZING → READY` 같은 persistent state, idempotent finalize, file existence/size/checksum validation, system-managed orphan reconciliation 등이다. 이는 특정 schema 추천이 아니라 cross-store inconsistency를 visible state로 표현하는 방식이다.

---

#### B. file + sidecar metadata

예: `source.bin` 옆에 `source.meta.json`.

**Interpretation:** backup이나 directory inspection 때 media와 metadata가 한 장소에 모이고 restart 때 scan하여 registry를 재구성할 수 있다.

반대로 media와 sidecar는 여전히 별도 directory entry라 두 파일을 하나의 atomic transaction으로 commit할 수 없다. Directory scan/index 비용, concurrent update, schema migration, ref lookup을 application이 직접 처리한다.

RD-17d에서 stable `sa_*`/`ms_*`를 sidecar 안에 저장하는 것은 가능하지만, 동일 ref duplicate와 file/sidecar mismatch 처리 규칙이 추가로 필요하다.

---

#### C. shared volume의 SQLite metadata DB

**Verified fact:** 같은 host의 별도 process가 SQLite file을 열 수 있고 locking을 통해 concurrency를 조정한다. WAL mode에서도 writer는 하나다. ([sqlite.org](https://www.sqlite.org/lockingv3.html))

**Interpretation:** 현재처럼 API 1 process + Worker 1 process, single host라면 기술적으로 가능한 후보지만 이미 MySQL이 process-shared persistence 역할을 하고 있으므로 별도 metadata database를 한 개 더 운영하는 trade-off가 생긴다.

WAL을 사용한다면 database file뿐 아니라 `-wal`/`-shm` semantics와 backup/recovery를 함께 이해해야 한다. 이후 network filesystem이나 multi-host로 topology가 바뀌면 WAL의 same-host 전제가 다시 검토 대상이다. ([sqlite.org](https://sqlite.org/wal.html))

---

#### D. Object Storage + MySQL metadata

**Verified fact:** S3 successful PUT 뒤 GET/HEAD에서 최신 object를 볼 수 있고 single key replacement는 partial object를 노출하지 않는다. ([docs.aws.amazon.com](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html))

**Interpretation:** 이것은 local filesystem의 partial-write/rename 문제를 object-key completion semantics로 바꾸지만, **S3 PUT + MySQL row**가 단일 transaction이 되는 것은 아니다. 따라서 object orphan과 stale DB row라는 cross-store 문제는 그대로 존재한다.

**Daesingo implication:** 현재 Worker가 local path를 요구한다면 저장소가 S3일 때도 결국 Worker side에서 download/materialization 공간이 필요할 가능성이 있다. 즉 root disk pressure가 완전히 사라진다고 외부 조사만으로 말할 수 없다.

---

### 4.5 FastAPI standard multipart `UploadFile`

현재 경로는 개념적으로 다음과 같다.

`client → Uvicorn receive chunks → Starlette MultiPartParser → SpooledTemporaryFile → FastAPI endpoint → application-managed final source`

**Verified fact:** 처음부터 전체 file bytes를 Python `bytes` 한 덩어리로 보관하지는 않는다. Starlette가 streaming parser를 사용한다. 다만 file 전체가 parse 완료될 때까지 `UploadFile` backing storage에 들어간다. ([github.com](https://github.com/Kludex/starlette/blob/main/starlette/formparsers.py))

**Verified fact:** 기본 threshold를 넘은 file은 temp disk로 rollover한다.

**Daesingo implication:** endpoint 안에서 다시 다음처럼 전체를 읽는다면:

`data = await upload.read()`

그 시점에는 별도로 **전체 file bytes를 API process memory에 materialize**할 수 있다. 반면 fixed-size chunk copy는 managed destination으로 옮기는 동안 full-size RAM copy를 피할 수 있다.

---

### 4.6 Raw `request.stream()`

**Verified fact:** raw stream은 body chunks를 전체 memory 저장 없이 endpoint에 전달한다. ([starlette.io](https://www.starlette.io/requests/))

**Interpretation:** body가 영상 raw bytes 자체라면 application이 수신 chunk를 곧바로 managed staging file에 기록하고 byte count/checksum을 동시에 갱신할 수 있다. 이 경우 Starlette `UploadFile` spool을 거치지 않아 **application-level temp → final duplicate copy**를 줄일 여지가 있다.

반대로 request가 `multipart/form-data`라면 `request.stream()`에 나오는 것은 영상만이 아니라 multipart boundary/header까지 포함된 raw protocol body다. 따라서 file extraction을 직접 구현하거나 streaming multipart parser를 사용해야 한다. `python-multipart`는 callback 기반 streaming parser를 제공한다. ([multipart.fastapiexpert.com](https://multipart.fastapiexpert.com/api/))

**Trade-off:** 직접 parser를 사용하면 spool 위치·size counting·checksum·staging destination을 통제할 수 있지만 file-count/field-size/body-size enforcement, malformed multipart handling, disconnect cleanup 같은 책임도 application 쪽으로 이동한다.

---

### 4.7 Request body size limit을 걸 수 있는 층

| 층 | 현재 확인 결과 |
|---|---|
| **Starlette** | **Verified fact:** 1.6+에는 total raw body limit이 있다. `RequestBodyLimitMiddleware`는 `Content-Length`로 가능한 경우 일찍 거부하고 실제 ASGI bytes도 count하므로 header가 없거나 축소된 경우에도 enforcement한다. 413 반환. ([starlette.io](https://www.starlette.io/middleware/)) |
| **Starlette multipart `max_part_size`** | **Verified fact:** file-size limit이 아니다. 현재는 non-file field limit이다. ([starlette.io](https://www.starlette.io/requests/)) |
| **FastAPI 0.142.2** | **Verified fact:** `FastAPI(max_body_size=...)`는 Starlette 설정 전달로 취급할 수 없다. explicit Starlette middleware를 ASGI middleware로 사용하는 것은 가능하다. ([github.com](https://github.com/fastapi/fastapi/blob/master/fastapi/applications.py)) |
| **application raw stream** | **Interpretation:** 수신 bytes를 직접 세어 threshold 초과 시 중단할 수 있다. `Content-Length`는 early hint로 활용할 수 있지만 streaming byte count가 실제 enforcement boundary가 된다. |
| **Uvicorn 0.54** | **Interpretation based on official settings:** current settings에 general HTTP total-body-size option이 문서화되어 있지 않다. `--h11-max-incomplete-event-size`는 upload limit이 아니다. Uvicorn flow control은 buffer explosion을 억제하지만 total accepted bytes를 제한하지 않는다. ([uvicorn.org](https://www.uvicorn.org/server-behavior/)) |
| **Nginx, 둔다면** | **Verified fact:** `client_max_body_size`가 request size limit을 제공한다. `client_body_buffer_size`를 넘는 body는 whole/part가 temp file로 갈 수 있다. `proxy_request_buffering on`이면 upstream 전송 전에 request body를 먼저 읽는다. **Nginx default 숫자는 대신고 baseline이 아니다.** ([nginx.org](https://nginx.org/en/docs/http/ngx_http_core_module.html)) |
| **Caddy, 둔다면** | **Verified fact:** `request_body { max_size ... }`가 read limit과 413을 제공한다. `reverse_proxy request_buffers`를 설정하면 지정 크기까지 upstream 전 request buffering을 한다. Docs상 이것은 별도 옵션이며 Caddy proxy의 일반 필수 동작이 아니다. ([caddyserver.com](https://caddyserver.com/docs/caddyfile/directives/request_body)) |

---

### 4.8 Upload 완료 ↔ Source 등록 관계

#### Pattern 1 — single request: receive → validate → register

**Interpretation:** 가장 단순한 API surface다. 수신이 전부 성공한 뒤 validation, publish, DB metadata registration을 수행한다.

Trade-off는 장시간 request lifecycle과 crash window다. Standard `UploadFile`을 쓰면 application logic이 시작될 때에는 이미 full multipart reception/spooling이 끝났다는 특성이 있다.

---

#### Pattern 2 — upload session → upload → finalize

**Interpretation:** 먼저 persistent upload/session identity를 만들고 bytes를 staging 위치에 기록한 후 finalize에서 size/checksum/media validation과 `SourceAsset` registration을 완료한다.

Part A의 `PENDING → READY` persistent state와 자연스럽게 연결되며 abandoned upload가 명시적인 상태가 된다. 반대로 API/state transition과 cleanup case가 늘어난다.

---

#### Pattern 3 — checksum

Checksum은 **content identity/integrity 확인 도구**이지 filesystem/DB atomicity 자체를 제공하지는 않는다.

**Interpretation:** file size + checksum을 metadata에 저장하면 restart/reconciliation 때 “row의 file이 실제 예상 bytes인가”를 확인하는 근거가 생긴다. 계산을 upload stream 중 병행할 수도 있고 완료 후 읽어서 계산할 수도 있으며 후자는 추가 disk read를 만든다.

---

#### Pattern 4 — tus/resumable

**Verified fact:** tus core protocol은 `HEAD`로 current `Upload-Offset`을 확인하고 `PATCH`로 그 offset부터 이어 보내는 방식이다. Creation, maximum size, expiration, checksum 같은 extensions도 정의돼 있다. ([tus.io](https://tus.io/protocols/resumable-upload))

**Interpretation:** upload-session/state persistence와 잘 맞지만 protocol implementation과 incomplete-session cleanup이라는 추가 범위를 가져온다.

---

#### Pattern 5 — Object Storage presigned upload

**Verified fact:** S3 presigned URL은 client에 AWS credential 자체를 제공하지 않고 특정 object에 일정 시간 PUT 권한을 줄 수 있으며 checksum도 사용할 수 있다. 동일 key를 PUT하면 기존 object를 replace한다. ([docs.aws.amazon.com](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html))

**Interpretation:** API server의 multipart spool/root-disk write를 우회할 수 있는 후보지만 storage boundary 자체가 Object Storage로 바뀌며, finalize 때 object 존재/checksum 확인 및 DB registration이 필요하다.

---

## 5. Failure Modes / Operational Risks

| Failure mode | 발생 조건 | 영향 | 완화 가능성 |
|---|---|---|---|
| **Interpretation — partial read** | API가 Worker-visible final pathname에 직접 쓰는 동안 Worker가 open | Worker가 incomplete media를 ffprobe/ffmpeg에 전달할 수 있음 | staging pathname + completion publish, DB state gate 등의 protocol |
| **Verified/Interpretation — cross-mount rename failure** | `/tmp` → shared volume 등 다른 mount | `rename()`이 `EXDEV`; copy fallback이면 atomic publish 상실 | staging을 같은 filesystem에 두는 variant를 spike로 검증 ([man7.org](https://man7.org/linux/man-pages/man2/rename.2.html)) |
| **Interpretation — stale reference** | metadata READY commit 후 file publish 실패/운영 삭제/disk 손실 | `sa_*`는 존재하지만 locator target 없음 | lookup 시 existence/integrity check, persistent error state, reconciliation |
| **Interpretation — orphan file** | file publish 성공 후 DB registration 전 crash | disk 사용량 증가, 어떤 ref에도 연결되지 않음 | staging/final naming convention, age/status scan, managed-artifact reconciliation |
| **Interpretation — stuck upload** | PENDING/session row 후 client/process crash | 영구 IN_PROGRESS record, staging bytes 잔존 | timeout/age-based reconciliation policy |
| **Verified fact — delete while Worker reads** | managed file unlink 중 Worker가 이미 FD open | 기존 Worker는 계속 읽을 수 있으나 새 opener는 path를 못 찾음; disk space는 FD close까지 회수되지 않음 | lifecycle/ref-count/job-state coordination ([man7.org](https://man7.org/linux/man-pages/man2/unlink.2.html)) |
| **Interpretation — concurrent writers** | 동일 final name에 두 writer | last rename/overwrite semantics 또는 mixed lifecycle | immutable/unique storage key, no-replace semantics, DB uniqueness |
| **Interpretation — permission denial** | API/Worker UID/GID 또는 host remapping 불일치 | create/open/rename/delete `EACCES` | image UID/GID와 mount permission integration test |
| **Verified fact — accidental named-volume removal** | `docker compose down -v` | media volume 삭제 | lifecycle choice와 deployment command guard가 분리된 운영 결정 ([docs.docker.com](https://docs.docker.com/reference/cli/docker/compose/down/)) |
| **Verified fact — Docker disk accumulation** | unused images/container layers/build cache를 계속 유지 | same host disk 소비 | Docker provides explicit prune/usage mechanisms; volume pruning은 데이터 위험과 별개 ([docs.docker.com](https://docs.docker.com/engine/manage-resources/pruning/)) |
| **Interpretation — temp disk exhaustion** | large/multiple standard multipart uploads | Starlette spooled temp가 root disk를 채움 | total body/concurrency limit, temp usage observation, alternate receive path 등의 선택지 |
| **Interpretation — duplicate disk write** | standard `UploadFile` rollover 후 final source copy | 대략 temp payload write + final payload write | raw streaming/direct storage 등과 비교 실험 |
| **Interpretation — proxy duplicate buffering** | Nginx request buffering + Starlette spool + final copy | proxy temp + application temp + final source까지 동일 root disk에 쓰일 수 있음 | proxy 설정까지 포함한 I/O trace |
| **Verified fact — client disconnect** | upload 중 network/client 종료 | Starlette stream에서 `ClientDisconnect`; parser-owned spool files close | app-managed staging을 만들었다면 그 file의 cleanup은 application lifecycle 문제 ([github.com](https://github.com/Kludex/starlette/blob/main/starlette/requests.py)) |
| **Interpretation — hard process/container termination** | app가 named staging file에 쓰다가 kill | shared mount의 partial staging file이 restart 뒤 남을 수 있음 | staging namespace + startup/periodic reconciliation |
| **Interpretation — RAM pressure** | Worker가 analysis/clip bytes를 계속 보유 + API concurrent work | host OOM 또는 process kill 가능 | API/Worker RSS를 분리 측정 |
| **Interpretation — disk/I/O contention** | upload write + ffmpeg read/write + MySQL + Docker/log I/O 동시 | latency 증가, disk queue 증가, 최악의 경우 ENOSPC가 여러 service로 전파 | root disk/free space + I/O latency/queue 관찰 |
| **Verified fact — SQLite writer contention** | sidecar DB 후보에서 동시 writes | `SQLITE_BUSY`, WAL도 writer 1개 | timeout/retry/write serialization 선택지가 있으나 실측 필요 ([sqlite.org](https://www.sqlite.org/wal.html)) |
| **Interpretation — S3/DB split success** | object PUT 성공·DB 실패 또는 반대 | object orphan / stale DB metadata | finalize state + object/row reconciliation |

### Restart별 정리

| 사건 | Shared bind/named file | process-memory metadata | persistent DB metadata | 진행 중 write |
|---|---|---|---|---|
| API process restart | **Interpretation:** completed shared file 유지 | 소실 | 유지 | app-owned shared staging은 partial로 남을 수 있음 |
| Worker process restart | 유지 | Worker-local cache 소실 | 유지 | Worker temp 위치에 따라 소실/잔존 |
| container recreation | bind/attached named volume은 container writable layer와 별개 | 소실 | DB storage가 persistent하다는 전제에서 유지 | container writable layer의 temp는 사라질 수 있고 shared mount temp는 남을 수 있음 |
| host reboot | **Interpretation:** persistent EBS filesystem 위 bind/local volume은 정상 filesystem recovery 후 남는 구조 | 소실 | underlying DB durability 설정에 따름 | 마지막 write의 crash durability는 filesystem/`fsync` semantics와 연관 |
| `compose down -v` | bind source는 Compose가 삭제하지 않음; declared named volume은 삭제 대상 | 소실 | MySQL volume도 `-v` 대상인지 Compose 정의에 따라 위험 | 해당 volume 안 file도 함께 영향 |

Docker docs가 volume을 container lifecycle 밖 persistence로 정의하지만, **host reboot 자체를 application-level durability guarantee로 해석하면 안 된다**. EBS/filesystem 손상·instance loss·backup 정책은 별도 운영 영역이다. ([docs.docker.com](https://docs.docker.com/engine/storage/volumes/))

---

## 6. Daesingo-specific Implications

### RD-17a — API ↔ Worker file sharing boundary

**Daesingo implication:** 현재의 직접 원인은 “API container가 쓴 file을 Worker container에 mount하지 않았다”와 “file ref mapping이 process-local”의 두 문제다. 따라서 RD-17a에서 filesystem 경계를 고르더라도 RD-17b를 같이 닫지 않으면 요구가 충족되지 않는다.

API가 원본을 쓰고 Worker는 원본을 읽기만 한다는 현재 역할을 이용하면, filesystem 후보에서는 **API RW / Worker RO** 형태도 semantic candidate가 된다. Docker는 bind와 named volume 모두 read-only mount를 지원한다. ([docs.docker.com](https://docs.docker.com/engine/storage/bind-mounts/))

원본과 Worker 파생 assets를 같은 volume에 둘지 나눌지는 외부 기술 사실로 결정되지 않는다. 다만 같은 root EBS라면 logical volume/path를 나눠도 physical disk-capacity와 I/O budget은 공유한다.

---

### RD-17b — persistent recording metadata

**Daesingo implication:** restart 뒤 같은 `sa_*`/`ms_*`를 의미 있게 사용하려면 최소한 다음 mapping 중 필요한 부분이 process 밖에 존재해야 한다.

`opaque ref → asset kind → internal storage identity/locator → integrity/state → required media/timeline metadata`

locator를 외부 API에 노출할 필요는 없다. Public ref와 internal storage locator를 분리할 수 있다.

현재 MySQL은 이미 API와 Worker 모두 접근 가능한 process-external persistence이므로 **MySQL을 후보에서 평가할 수 있는 기술적 전제는 존재**한다. 그것이 최종 선택이라는 결론은 외부 조사 범위를 넘는다.

---

### RD-17c — process boundary를 넘어야 할 recording state

**Daesingo implication:** 모든 recording object를 그대로 persistent object graph로 옮길 필요가 있는지는 내부 설계 문제다. 외부 조사로 확인되는 최소 조건은 Worker/restart 뒤 필요한 데이터를 메모리-only로 두면 안 된다는 것이다.

즉 후보 boundary는 다음 질문으로 좁혀진다.

`Worker job이 sa_*/ms_*만 가지고 시작했을 때, 어떤 persistent fields만 읽으면 원본을 안전하게 open하고 timeline 의미를 복원할 수 있는가?`

이는 schema 설계 spike에서 확인할 영역이다.

---

### RD-17d — stable opaque ref

**Daesingo implication:** 지금처럼 `register()` 할 때마다 random ref를 새로 만들고 그 mapping을 process dict에만 둔다면 filesystem durability만 추가해도 restart 복원은 되지 않는다.

반대로 ref 값과 mapping 자체를 persistent store에 기록한다면 restart 뒤에는 **re-register로 새 ref를 만드는 대신 existing record를 load**하는 model이 가능하다.

같은 physical file을 중복 registration했을 때 같은 ref를 재사용할지, 새 logical asset을 만들지는 외부 저장기술이 정할 수 없는 domain identity 결정이다.

---

### RD-05e — standard multipart의 resource model

약 3.7 GiB usable RAM / 50 GiB root disk 환경에 현재 library behavior를 적용하면 다음 구조가 된다.

**표준 `UploadFile`, large file, reverse proxy buffering 없음:**

`network → Starlette memory spool window → Starlette temp disk → endpoint → final source disk`

따라서 large file 하나가 최종 source가 될 때 application path상 대략:

- memory: spool threshold + transient parser/network buffers,
- temp disk: 거의 한 file payload 규모,
- final source: 한 file payload 규모,
- copy 시 temp disk read,
- 이후 Worker: 원본 read + ffmpeg temp/derivative write,

라는 구조가 된다.

이는 “항상 정확히 2× size만큼 peak disk를 쓴다”는 공식이 아니다. temp와 final의 생존 구간, proxy, filesystem page cache, failure staging, derivative 생성 시점에 따라 peak가 달라진다.

---

### RAM과 disk 중 무엇이 먼저 찰까?

**Daesingo implication:** 현재 정보만으로 하나를 선택할 수 없다.

Standard large `UploadFile` 자체는 1 MiB 이후 disk로 spool하므로 file size 전체가 API RAM으로 증가하지는 않는다. 하지만:

- 동시 upload마다 memory spool/parser overhead가 생기고,
- application이 `await upload.read()` 전체 읽기를 하면 full-size RAM copy가 추가되며,
- 현재 Worker가 analysis/clip bytes를 RSS에 쌓는다는 별도 구조가 있다.

따라서 Worker RSS가 먼저 임계에 닿을 수도 있고, 큰/동시 upload가 늘어 root disk가 먼저 임계에 닿을 수도 있다.

---

### 관찰 지표

실제 upload-size baseline을 만들기 전에는 최소 다음 종류를 분리해 기록할 가치가 있다.

- **RAM:** API RSS/PSS, Worker RSS/PSS, container memory usage/events, host `MemAvailable`, OOM event.
- **Disk capacity:** root filesystem free bytes/inodes, upload temp directory bytes, managed source bytes, derivative/temp/clip bytes, MySQL data, Docker images/build cache.
- **Disk I/O:** read/write bytes, latency, queue depth/utilization, I/O wait.
- **Upload:** active upload count, received bytes, duration, client disconnect, 413, spool/finalize failure, staging bytes and age.
- **Persistence consistency:** `PENDING` age, stale reference count, orphan count, checksum/size mismatch.
- **Worker:** job phase, source read bytes, derivative output bytes, Worker RSS.

`docker system prune`/`docker buildx prune` 등은 build/cache 관찰 후 사용할 수 있는 운영 수단이지만 media persistence policy와 혼동하면 안 된다. 특히 volume cleanup은 별도 데이터 삭제 의미를 가진다. ([docs.docker.com](https://docs.docker.com/engine/manage-resources/pruning/))

---

## 7. What External Research Cannot Decide

### 대신고 내부 합의가 필요한 것

1. RD-17a에서 bind mount, named volume, Object Storage adapter 중 어떤 boundary를 채택하는지.
2. 원본과 derivative/temp/clip을 같은 storage namespace에 둘지 나눌지.
3. 어떤 자산만 immutable인지, 어떤 system-managed artifact가 cleanup 대상인지.
4. RD-17b에서 MySQL row의 구체 schema와 locator 표현.
5. `sa_*` / `ms_*` identity가 physical file identity와 1:1인지, logical registration identity인지.
6. file publish 성공과 DB `READY` 상태의 ordering.
7. stale/orphan을 자동 복구할지, 실패 상태로 남길지.
8. crash-durability 요구가 `rename` visibility 수준인지, explicit `fsync`까지 필요한 수준인지.
9. upload endpoint가 one-shot인지 session/finalize인지.
10. multipart metadata가 실제 필요해서 standard multipart를 유지하는지, raw body로 충분한지.
11. upload 크기 limit과 simultaneous-upload 정책의 실제 숫자.
12. reverse proxy를 사용하는지, 사용한다면 request buffering policy.

### 실험이 필요한 것

- 실제 영상 크기/길이 분포.
- Worker current RSS와 영상 크기의 관계.
- standard `UploadFile`에서 temp/final copy 중 실제 peak disk usage.
- API + Worker 동시 처리 시 EBS latency.
- 실제 Docker image의 UID/GID 및 bind/named volume permission.
- same-volume `rename()` 성공 여부.
- container kill/restart 뒤 staging artifacts.
- FastAPI 0.142.2에 explicit Starlette body-limit middleware를 넣었을 때 multipart endpoint의 실제 413 timing.
- proxy가 포함된 실제 deployment에서 temp file copy 횟수.

### External Input이 필요한 것

향후 카테캠/AWS 운영 측에서 disk 증설·별도 volume·S3 비용/권한 등 추가 제약을 제공하면 RD-17a 비교축이 달라질 수 있다. 현재 조사에서는 그 자원을 가정하지 않았다.

---

## 8. Suggested Pre-implementation Checks

아래는 **결정안이 아니라 후보를 사실화하기 위한 작은 spike 목록**이다.

### Spike A — shared filesystem semantics

Compose에 API/Worker 두 container를 띄우고 동일 source directory를 bind mount와 named volume 각각으로 바꿔 가며:

1. API user로 file 생성.
2. Worker user로 read/ffprobe.
3. API restart → read.
4. API container recreate → read.
5. Worker recreate → read.
6. host reboot 후 read.
7. `stat`으로 UID/GID/mode 기록.
8. Worker mount를 `ro`로 설정했을 때 read 가능/modify 불가 확인.

이 결과가 RD-17a의 concrete infrastructure evidence가 된다.

---

### Spike B — atomic publish

shared filesystem 안에서:

`asset.partial → write → close → rename asset.mp4`

를 수행하고 Worker가 final pathname만 polling/open하게 한다.

비교 대상으로 container `/tmp → shared mount` rename도 실행해 `EXDEV` 여부를 기록한다. 이를 통해 “temp dir을 어디에 둘 때 atomic rename을 쓸 수 있는가”를 실제 baseline에서 확인할 수 있다. ([man7.org](https://man7.org/linux/man-pages/man2/rename.2.html))

---

### Spike C — persistent ref recovery

최소 field만 저장하는 임시 persistence implementation으로:

`upload/register → sa_*/ms_* 발급 → API process kill → restart → same ref lookup → Worker ffprobe`

한 경로를 end-to-end로 확인한다.

여기서 목적은 schema를 확정하는 것이 아니라 **현재 process-memory dependency를 정확히 찾아내는 것**이다.

---

### Spike D — split-store crash matrix

아래 지점마다 강제 process termination:

1. staging file 생성 전
2. file write 중
3. file close 후
4. final rename 후
5. metadata insert 후
6. READY transition 전
7. READY 후

각 시점에 DB state, source file, staging file이 무엇으로 남는지 기록한다.

이 결과가 orphan/stale/recovery protocol의 실제 input이 된다.

---

### Spike E — upload resource trace

대표 크기를 임의 production limit으로 정하지 말고, 여러 test file size에서:

- API RSS
- Worker RSS
- `/tmp` 또는 `TMPDIR` usage
- final media bytes
- root free bytes
- disk write bytes
- endpoint 함수 진입 시점
- upload 종료 시 temp cleanup 시점

을 기록한다.

특히 standard `UploadFile` 경로와 raw `request.stream()` staging 경로를 같은 측정 방식으로 비교하면 RD-05e의 trade-off evidence가 된다.

---

### Spike F — interrupted upload

1. standard multipart upload 중 client connection abort
2. application process SIGTERM
3. hard kill
4. container recreation

각각에서:

- Starlette temp file,
- app-owned staging file,
- metadata row,
- emitted ref

상태를 기록한다.

Starlette parser 자체는 parsing error/disconnect 시 owned spool files를 close하지만, application이 만든 persistent staging file까지 자동으로 지우지는 않는다. ([github.com](https://github.com/Kludex/starlette/blob/main/starlette/formparsers.py))

---

### Spike G — total-body limit

현재 FastAPI 0.142.2 기준으로:

- `FastAPI(max_body_size=...)`가 limit으로 작동하지 않음을 regression test로 고정,
- explicit `RequestBodyLimitMiddleware`,
- Content-Length 있음/없음,
- streaming/chunked request,
- multipart large file

를 각각 보내 413 timing과 temp disk growth를 관찰할 수 있다. Starlette middleware는 실제 수신 byte counting을 한다. ([starlette.io](https://www.starlette.io/middleware/))

---

## 9. Unresolved / Unverified

1. **Named volume의 fresh ownership 초기값**\
   Docker docs는 volume lifecycle과 prepopulation은 명확히 설명하지만, 대신고가 사용할 Docker Engine/local driver/image `USER` 조합에서 mount root가 어떤 numeric UID/GID로 보일지 portable contract로 고정하지 않는다. 실제 `stat`이 필요하다.

2. **Cross-container `flock` 실제 동작**\
   **Interpretation:** 동일 Linux host의 동일 underlying inode를 두 container가 local bind/named volume으로 열면 kernel advisory lock을 공유하는 구조이므로 cooperating `flock()`은 작동하는 것으로 기대된다. Linux lock은 process/container API가 아니라 underlying file description에 적용된다. ([man7.org](https://www.man7.org/linux/man-pages/man2/flock.2.html))\
   그러나 Docker volume driver/user namespace가 실제 baseline에 어떤 방식으로 구성될지는 spike에서 확인하는 편이 정확하다. 향후 network filesystem이면 semantics가 달라질 수 있다.

3. **Starlette `spool_max_size` public configuration surface**\
   현재 source에는 class attribute가 있고 `SpooledTemporaryFile(max_size=...)`에 사용되지만 `Request.form()`의 documented parameter에는 spool threshold나 temp directory가 없다. 즉 `max_part_size`와 spool threshold를 같은 설정으로 취급하면 안 된다. ([starlette.io](https://www.starlette.io/requests/))

4. **Starlette temp directory 직접 지정**\
   current parser는 `dir=`를 넘기지 않으므로 Python default temp selection을 따른다. `TMPDIR` 등 환경변수로 process-wide default를 바꿀 수 있지만, Starlette public request API에서 upload별 temp directory를 지정하는 parameter는 확인되지 않았다. ([docs.python.org](https://docs.python.org/ko/3.12/library/tempfile.html))

5. **FastAPI per-route `max_body_size`**\
   Starlette는 route/application 수준 기능을 갖지만 FastAPI 0.142.2 path-operation API에는 동일 옵션이 직접 노출되지 않은 상태다. 2026-09-09에도 이 차이를 다루는 FastAPI discussion이 열려 있었다. Global/ASGI middleware 적용은 확인되지만 대신고가 per-route enforcement를 원한다면 exact integration을 spike로 고정할 필요가 있다. ([github.com](https://github.com/fastapi/fastapi/discussions/16339))

6. **Uvicorn total request-body limit**\
   current official settings에서 generic HTTP body-size limit은 확인되지 않았다. 이것은 “Uvicorn에 영원히 구현이 없다”는 주장이 아니라 **0.54.0 공식 configuration surface에서 확인되지 않았다**는 의미다. ([uvicorn.org](https://www.uvicorn.org/settings/))

7. **Caddy request buffering의 disk spill semantics**\
   Caddy docs는 `request_buffers`가 memory/delay overhead를 만드는 buffering option이라는 점은 설명하지만, 조사한 공식 문서에서 그 buffer가 특정 크기에서 Nginx처럼 temp disk로 spill된다고 명시하지 않았다. 따라서 이를 Nginx와 동일한 disk-temp copy로 계산하지 않았다. ([caddyserver.com](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy))

8. **Host crash 직전 write durability 수준**\
   Linux `fsync()` semantics는 확인됐지만 EBS/filesystem/Docker/application 조합에서 대신고가 어느 수준까지 crash-durability를 요구할지는 내부 결정이다.

9. **실제 peak copy factor**\
   `UploadFile` standard path가 temp + final storage라는 구조는 확인됐지만 peak disk multiplier는 upload concurrency, cleanup timing, proxy, finalization, derivative processing이 겹치는 정도에 의존한다. 현재 영상 분포 없이 숫자로 고정하지 않았다.

---

## 10. Sources

확인일은 별도 표기가 없는 경우 **2026-10-03**이다.

- Docker Docs — **Bind mounts**. Host-path semantics, read-only mounts, obscuring image contents. [Docker — Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
- Docker Docs — **Volumes**. Lifecycle, multi-container use, prepopulation/`volume-nocopy`, backup/restore. [Docker — Volumes](https://docs.docker.com/engine/storage/volumes/)
- Docker Docs — **docker compose down**. `-v` deletion semantics. [Docker Compose — down](https://docs.docker.com/reference/cli/docker/compose/down/)
- Docker Docs — **Compose services / volumes**. `read_only`, `nocopy`, bind options. [Docker Compose — Services volumes](https://docs.docker.com/reference/compose-file/services/)
- Docker Docs — **Prune unused Docker objects**. Images, build cache, volume cleanup semantics. [Docker — Pruning](https://docs.docker.com/engine/manage-resources/pruning/)
- Docker Docs — **UID/GID mapping** 및 **userns-remap**. [Docker — UID/GID mapping](https://docs.docker.com/engine/security/rootless/uid-gid-mapping/) [Docker — userns-remap](https://docs.docker.com/engine/security/userns-remap/)
- Linux man-pages 6.19 — `rename(2)`, `fsync(2)`, `unlink(2)`, `flock(2)`. [Linux rename(2)](https://man7.org/linux/man-pages/man2/rename.2.html) [Linux fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html) [Linux unlink(2)](https://man7.org/linux/man-pages/man2/unlink.2.html) [Linux flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html)
- SQLite — **File Locking And Concurrency in SQLite Version 3**, **Write-Ahead Logging**. [SQLite locking](https://www.sqlite.org/lockingv3.html) [SQLite WAL](https://www.sqlite.org/wal.html)
- Python 3.12 — **tempfile**. `SpooledTemporaryFile`, default temp directory selection. [Python 3.12 tempfile](https://docs.python.org/3.12/library/tempfile.html)
- Starlette **1.7.0**, released 2026-09-23. [PyPI](https://pypi.org/project/starlette/1.7.0/) [Starlette Requests](https://www.starlette.io/requests/)
- Starlette — **RequestBodyLimitMiddleware** and current middleware documentation. [Starlette Middleware](https://www.starlette.io/middleware/)
- Starlette current `formparsers.py` / `requests.py` source, inspected against the current 1.7.0 release line. `spool_max_size`, file/non-file `max_part_size`, parser cleanup, `ClientDisconnect`. [GitHub](https://github.com/Kludex/starlette/blob/main/starlette/formparsers.py)
- FastAPI **0.142.2**, released 2026-09-30, release commit `78c4324`. [PyPI](https://pypi.org/project/fastapi/0.142.2/)
- FastAPI `applications.py` — extra constructor kwargs are stored but unused; source inspection for `max_body_size` behavior. [GitHub](https://github.com/fastapi/fastapi/blob/master/fastapi/applications.py)
- `python-multipart` **0.0.32**, released 2026-06-04, provenance commit `238ead62a0bb6f6cdfe122708faa13812f59f9a6`. [PyPI](https://pypi.org/project/python-multipart/0.0.32/) [API](https://multipart.fastapiexpert.com/api/)
- Uvicorn **0.54.0**, released 2026-09-25. [PyPI](https://pypi.org/project/uvicorn/0.54.0/) [Server Behavior](https://www.uvicorn.org/server-behavior/) [Settings](https://www.uvicorn.org/settings/)
- Nginx — `client_max_body_size`, `client_body_buffer_size`, `client_body_temp_path`, `proxy_request_buffering` official directives. [HTTP core module](https://nginx.org/en/docs/http/ngx_http_core_module.html) [Proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- Caddy — `request_body max_size`, `reverse_proxy request_buffers`. [request_body](https://caddyserver.com/docs/caddyfile/directives/request_body) [reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- AWS S3 — strong consistency, atomic single-key update, presigned upload/checksum. [What is Amazon S3?](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) [Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
- tus — **Resumable Upload Protocol 1.0.x**. [tus protocol specification](https://tus.io/protocols/resumable-upload)

**조사 완료 기준에 대한 판정:** RD-17a의 bind/named volume semantics, RD-17b의 metadata persistence 후보와 split-store failure, RD-05e의 현재 multipart buffering·body-limit·disconnect/cleanup 동작까지 외부 근거로 구분 가능하다. 남은 핵심 불확실성은 기술 문서 부족이 아니라 **대신고 실제 Docker UID/GID, 영상 크기 분포, Worker RSS, root-disk I/O, crash 시점별 잔존 상태**이므로, 다음 단계에서는 위 Spike A–G가 Decision 입력을 생산하는 영역이다.
