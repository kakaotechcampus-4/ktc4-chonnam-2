# case

**Owner:** 유소연

이 폴더는 `case` 모듈의 세부 문서 작업공간이다. 모듈 경계의 기준 문서는 `docs/architecture/module-architecture.md`, 역할은 `docs/management/ownership.md`를 따른다.

## 한눈에 보기

- **하는 일:** 사용자의 신고 건(case) 하나의 진행 단계와 선택을 들고, 어떤 작업(Job)을 언제 맡길지 정한다.
- **입력 1 — 사용자 command:** web이 API로 보낸다(분석 시작 · 중단 · 설명 고치기 · 다른 후보 선택 · 상황 응답 · 번호판/시각 직접 입력 · notice 버튼 · 최종 확인 등). 진입점은 `command.py` `execute_command()`, 종류와 규칙은 [case-command 계약](contracts/contract-case-command.md).
- **입력 2 — Worker 작업 결과:** 끝난 Job 결과를 `reflection.py` `reflect_execution()`이 case에 반영한다.
- **출력 1 — CaseView:** web이 읽는 화면용 값. `service.py` `get_view()`가 만든다. 모양은 [JobRecord + CaseView 계약](../../architecture/contracts/contract-job-record-case-view.md).
- **출력 2 — JobRecord:** 다른 모듈에 맡길 작업의 발주 기록. 같은 계약 A절.
- **코드:** `src/daesingo/case/`. API 라우트는 `src/daesingo/api/routes_*.py`, DB 저장은 `store_mysql.py` + `migrations/case/`.
- **테스트:** `python -m pytest tests/case -q`. `DAESINGO_MYSQL_URL`이 없으면 MySQL 테스트는 skip된다(`tests/case/conftest.py`). 값을 주면 DB 이름에 `test`가 들어 있어야 한다 — 아니면 pytest가 시작 전에 멈춘다(`tests/mysql_harness.py`). 아래 「MySQL 통합 테스트」 참고.
- **결정 기록:** [decisions/README.md](decisions/README.md).

## 다루는 범위

- Case State와 사용자 선택
- 자연어 intent를 작업으로 매핑
- 작업 발주/재실행 정책
- 진행 상태와 E2E orchestration

## 다루지 않는 범위

- 신고요건 계산
- 시각 출처 우선순위
- 프롬프트/OCR 파라미터
- 확정 Evidence 값을 복사해 따로 들고 있기
## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `architecture/contracts/`로 승격
- `case-edge-cases.md`: case가 만나는 경계 상황(반복 행동 · 동시성 · 실패 · 빈 입력 · LLM) 목록 — 현재 동작 · 근거 · 다음 할 일

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.

### MySQL 통합 테스트 (opt-in)

case 저장소의 MySQL 구현은 `DAESINGO_MYSQL_URL`이 있을 때만 테스트한다(로컬은 opt-in). CI는 `.github/workflows/python-tests.yml`이 MySQL 8.4 service와 `DAESINGO_REQUIRE_MYSQL=1`로 돌려 skip을 실패로 본다(RT-02a #319 — Runtime 구현 Task RT-02 「DB · Alembic · 테스트 harness · CI」의 (a) 단계).

    docker run -d --rm --name daesingo-mysql -e MYSQL_ROOT_PASSWORD=devpw -e MYSQL_DATABASE=daesingo_test -p 3306:3306 mysql:8.4
    DAESINGO_MYSQL_URL="mysql+pymysql://root:devpw@127.0.0.1:3306/daesingo_test" python -m pytest tests/case -q

3306이 이미 쓰이고 있으면 `-p 3307:3306`처럼 다른 포트를 쓰고 URL의 포트를 맞춘다.

**격리 요건:** MySQL 저장소를 쓰는 transaction은 READ COMMITTED여야 한다(`create_engine(url, isolation_level="READ COMMITTED")`, #250 01b — Runtime 결정 이슈 #250(RD-01)의 01b 항목). 아니면 `load(lock="update")`가 첫 읽기여야 한다 — REPEATABLE READ에서는 잠금 없는 record 테이블 읽기가 낡을 수 있다(`store_mysql.py` docstring).

테스트 fixture가 시작할 때 case 테이블을 지우고 migration을 다시 올린다 — **테스트 전용 DB만** 가리킨다. DB 표 만들기(migration — case 전용 위치 `migrations/case/`, 처음엔 임시안이었고 Runtime 계획 P-1이 모듈별 배치로 채택): `PYTHONPATH=src DAESINGO_MYSQL_URL=... alembic -c migrations/case/alembic.ini upgrade head`.
