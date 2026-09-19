# tests

모듈 내부 테스트 자리. 현재 `tests/readout/` 79건.

## 러너 — pytest

**실행 명령은 `python -m pytest <경로>`다.** 모듈별로는 `python -m pytest tests/readout`, 전체는 `python -m pytest tests`.

PR #51 리뷰에서 김준영 님이 제안한 공통 러너 통일이고(recording·search·eval·case가 이미 pytest), 통합 전에 실행 기준을 맞추려는 것이다. 기존 `unittest.TestCase` 기반 테스트는 pytest에서 그대로 수집되므로 **테스트 코드를 다시 쓰지 않는다.** 새로 쓰는 테스트만 pytest 스타일(`assert` · fixture)로 쓴다.

## `conftest.py`가 루트에 있는 이유 — 한시적

레포에 아직 패키지 설치 설정이 없어서 `daesingo`가 설치된 패키지로 잡히지 않는다. 그래서 루트 `conftest.py`가 `src/`를 import 경로에 올린다. 그전에는 테스트 파일마다 `sys.path.insert`를 적어 뒀는데 한 곳으로 모았다.

**`pyproject.toml`은 이 PR에서 만들지 않았다.** 지금 `feature/eval-harness` · `feature/recording-first-integration` · `feature/search-first-integration` 세 브랜치가 **각자 다른 root `pyproject.toml`을 들고 있다** — 패키지 이름(`daesingo-eval`·`daesingo`·`daesingo-backend`), `requires-python`(3.11·3.10·3.13), 빌드 백엔드(setuptools·hatchling), `testpaths`가 전부 다르다. 여기에 네 번째를 더하면 통합에서 4-way 충돌이 된다.

**통합에서 root `pyproject.toml` 하나로 수렴시켜야 한다.**

> **현재 기준(2026-09-19):** root `pyproject.toml` + Python 3.12 + `uv.lock`로 공통 환경을 수렴한다. 위 3.10/3.11/3.13 내용은 1차 Mock Merge 전에 왜 충돌이 발생했는지를 설명하는 이력이다. 그때 `[tool.pytest.ini_options]`에 `pythonpath = ["src"]`가 들어오면(또는 editable 설치로 가면) 이 `conftest.py`는 지운다.

> `pytest.ini`·`setup.cfg`로 설정을 두는 것도 피했다. 둘 다 `pyproject.toml`의 `[tool.pytest.ini_options]`보다 우선순위가 높아서, 통합 뒤에 다른 모듈의 설정을 **조용히 덮어쓴다.**

## 무엇을 어디서 보는가

- **모듈 내부 테스트**는 각 모듈 Owner가 자기 모듈에 대해 쓴다. `evidence`는 순수 함수라 JSON 입출력만으로 초기 테스트 케이스 7·9·10을 1초에 돌릴 수 있어야 한다(`docs/management/ownership.md` §3 김준영 ⑤).
- **계약이 맞물리는지**는 `case` Owner가 목데이터 1차 통합에서 확인한다(`docs/management/ownership.md` §7-④).
- **경로가 맞았는지**는 코드 테스트가 아니라 `docs/management/tool-trajectory-review.md`가 본다.
- 평가(채점)는 여기가 아니라 `eval/`이다.
