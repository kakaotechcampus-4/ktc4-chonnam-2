# src

제품 코드가 들어갈 자리. Python 패키지 하나(`daesingo/`)로 구성한 **모듈형 모놀리스**다 (`docs/architecture/module-architecture.md` §1-5).

```text
src/daesingo/
  recording/  search/  readout/  evidence/  case/   # 도메인 모듈 5개 (§4 모듈1~5)
  common/                                            # runtime 기반 — 도메인 모듈이 아니다 (§6-2)
  api/        worker/                                # composition root 2개 (FastAPI 1 + Worker 1)
```

- 브라우저 UI(`web`)는 여기 없다 → `apps/`. 평가 도구(`eval`)도 여기 없다 → 루트 `eval/`.
- 호출 방향과 금지 구조는 `docs/architecture/module-architecture.md` §6-1 · 부록 B를 따른다.
- 패키지 매니저·`pyproject.toml`·의존성은 코드를 시작할 때 Owner들이 정한다. 지금 정하지 않는다.
