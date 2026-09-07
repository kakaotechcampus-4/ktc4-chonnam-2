# tests

표준 라이브러리 `unittest` 기반의 1차 Mock 통합 테스트다.

- **모듈 내부 테스트**는 각 모듈 Owner가 자기 모듈에 대해 쓴다. `evidence`는 순수 함수라 JSON 입출력만으로 초기 테스트 케이스 7·9·10을 1초에 돌릴 수 있어야 한다(`docs/management/ownership.md` §3 김준영 ⑤).
- **계약이 맞물리는지**는 `case` Owner가 목데이터 1차 통합에서 확인한다(`docs/management/ownership.md` §7-④).
- **경로가 맞았는지**는 코드 테스트가 아니라 `docs/management/tool-trajectory-review.md`가 본다.
- 평가(채점)는 여기가 아니라 `eval/`이다.

## 현재 실행

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/validate_evidence_impl.py
```

`test_evidence_integration.py`는 공용 Happy/Partial fixture를 실제 Evidence 공개
API에 넣는다. `test_common_runtime.py`는 JobExecution/UsageRecord 원장 정합과
마스킹을 검증한다. 팀 공용 정적 Mock 검증은 `validate_mock_pack.py`, 실제
Evidence 출력과 fixture의 회귀 비교는 `validate_evidence_impl.py`가 맡는다.
