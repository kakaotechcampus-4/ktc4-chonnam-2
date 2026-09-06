# scripts

팀 공용 스크립트 자리.

## `check_boundaries.py` — 모듈 경계 · 계약 정합성 점검

```bash
python scripts/check_boundaries.py                  # 전체
python scripts/check_boundaries.py --only=contracts  # 계약만
python scripts/check_boundaries.py --only=boundaries # 모듈 경계만
```

**규칙을 여기서 정하지 않는다.** 명세는 두 문서가 소유하고 스크립트는 그것을 돌린다.

| 검사 | 명세 원문 |
| --- | --- |
| 모듈 경계 금지 문자열 | `docs/management/ownership.md` §6 |
| 계약 헤더 4개 · 번호 재삽입 금지 · 커버리지 | `docs/architecture/module-architecture.md` §5-1 |
| 위반유형 baseline enum | `docs/architecture/module-architecture.md` §3-5 |
| 보정 이력 | `docs/architecture/contracts/adr/adr-consistency-2026-09.md` |

`FAIL`은 위반이고 `NOTE`는 확인 대상이다. 골격 단계에서 코드가 없는 모듈은 `NOTE`로만 나온다.

`enum` 검사의 변형 목록(`LANE_CHANGE` → `SOLID_LINE_LANE_CHANGE` 등)은 실제로 드리프트가 발생한 값만 넣는다. v4 §3-5의 baseline이 바뀌면 스크립트가 스스로 실패한다.

## CI

`.github/workflows/boundary-check.yml`이 PR과 `develop` push에서 이 스크립트를 돌린다.

**운영진 소유 4개 파일은 건드리지 않는다** — `workflows/{assign-mentor,notify-discord,convention-check}.yml`과 `CODEOWNERS`. 그 밖의 `.github/` 추가는 CODEOWNERS 개정으로 허용됐다.
