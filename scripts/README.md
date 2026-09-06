# scripts

팀 공용 스크립트 자리.

## `check_boundaries.py` — 모듈 경계 · 계약 정합성 점검

```bash
python scripts/check_boundaries.py                  # 전체
python scripts/check_boundaries.py --only=contracts  # 계약만
python scripts/check_boundaries.py --only=boundaries # 모듈 경계만
```

**규칙을 여기서 정하지 않는다.** 아래는 현재 스크립트가 실제 구현한 검사 범위다. 전체 의미 검증과 다르다.

| 검사 | 명세 원문 |
| --- | --- |
| 모듈 경계 금지 문자열 | `docs/management/ownership.md` §6 |
| 헤더 3개(Status/Architecture Contract/Contract Version)의 첫 1,500자 내 존재 · 제목의 번호 · 타입 언급/제목 coverage | `docs/architecture/module-architecture.md` §5-1 |
| 위반유형 baseline enum | `docs/architecture/module-architecture.md` §3-5 |
| 보정 이력 | `docs/architecture/contracts/adr/adr-consistency-2026-09.md` |

`FAIL`은 위반이고 `NOTE`는 확인 대상이다. 골격 단계에서 코드가 없는 모듈은 `NOTE`로만 나온다.

`enum` 검사의 변형 목록(`LANE_CHANGE` → `SOLID_LINE_LANE_CHANGE` 등)은 실제로 드리프트가 발생한 값만 넣는다. 현재는 baseline 줄과 SOLID_LINE_LANE_CHANGE의 존재 및 LANE_CHANGE 변형을 검사한다. 다른 임의 enum 오타를 모두 검출하지 않는다.

**알려진 한계:** 포인터가 올바른 행인지, Accepted/Related ADR, JSON 직렬화·nullable·참조 연결·gate 의미는 검사하지 않는다. 번호/coverage 범위는 아직 ①~⑫이며 ⑬을 놓친다. AnalysisSource는 제목 언급 때문에 coverage NOTE에서 빠질 수 있다. 검사 대상 코드가 0개인 경로는 boundary NOTE를 출력한다. 현재 골격에서는 7개 boundary NOTE와 5개 coverage NOTE가 나오며, PASS를 E2E·Owner 수락 증거로 쓰지 않는다.

## CI

`.github/workflows/boundary-check.yml`이 PR과 `develop` push에서 이 스크립트를 돌린다.

**운영진 소유 4개 파일은 건드리지 않는다** — `workflows/{assign-mentor,notify-discord,convention-check}.yml`과 `CODEOWNERS`. 그 밖의 `.github/` 추가는 CODEOWNERS 개정으로 허용됐다.
