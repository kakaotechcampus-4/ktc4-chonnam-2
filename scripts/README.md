# scripts

팀 공용 스크립트 자리. 아직 비어 있다.

첫 후보는 **모듈 경계 점검** — `docs/management/ownership.md` §6의 grep 목록(`case/`에 `130MB`·`기한`·`프롬프트`가 0건인가 등)을 한 번에 돌리는 스크립트. 주간 회의 전에 수동으로 실행한다.

**CI 자동 실행이 가능하다** — 운영진 CODEOWNERS 개정으로 `.github/workflows/`에 팀 워크플로를 추가할 수 있다(운영진 소유는 파일 4개뿐). **다만 아직 스크립트가 없어서 workflow도 없다.** 스크립트를 먼저 쓰고 그 다음 workflow를 붙인다. 점검 항목의 명세는 `docs/management/ownership.md` §6이다.
