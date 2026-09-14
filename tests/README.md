# tests

모듈별 smoke/contract test를 둔다.

- **모듈 내부 테스트**는 각 모듈 Owner가 자기 모듈에 대해 쓴다. `evidence`는 순수 함수라 JSON 입출력만으로 초기 테스트 케이스 7·9·10을 1초에 돌릴 수 있어야 한다(`docs/management/ownership.md` §3 김준영 ⑤).
- **계약이 맞물리는지**는 `case` Owner가 목데이터 1차 통합에서 확인한다(`docs/management/ownership.md` §7-④).
- **경로가 맞았는지**는 코드 테스트가 아니라 `docs/management/tool-trajectory-review.md`가 본다.
- 평가(채점)는 여기가 아니라 `eval/`이다.

## 실행

Python 3.10 이상에서 test 의존성을 설치한 뒤 실행한다.

```powershell
python -m pip install -e ".[test]"
python -m pytest
```
