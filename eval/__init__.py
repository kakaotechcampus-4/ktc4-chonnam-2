"""대신고 오프라인 채점 하니스.

제품 런타임이 아니다. `case`·`evidence`·`web`을 알지 못하며,
`search`/`readout`의 공개 함수가 기본 경계다. 시점별 Search 비교를 위한
`runners/impls/search_pipeline.py`와 `tools/evaluate_aihub_*`는 예외적으로
Search의 설정·프롬프트·provider를 직접 가져온다
(`docs/architecture/module-architecture.md` §4-모듈7).
"""

__version__ = "0.1.0"
