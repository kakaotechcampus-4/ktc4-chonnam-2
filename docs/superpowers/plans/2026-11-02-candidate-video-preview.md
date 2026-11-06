# Candidate Video Preview Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this approved plan inline. Steps use checkbox syntax.

**Goal:** 후보 수에 맞는 카드에서 상위 3개 후보의 구간 영상을 선택 변경 없이 요청하고 재생한다.

**Architecture:** Case가 미리보기 전용 intent와 후보·세대·span 결속을 소유한다. Worker는 기존 Recording 생성 기능을 별도 handler로 호출하고 T2는 미리보기만 기록한다. API는 현재 Case의 저장 clip을 inline/Range로 제공하며 Web은 기존 polling과 native video를 사용한다.

**Tech Stack:** 기존 Python/FastAPI/SQLAlchemy/Pydantic/FFmpeg, React/TypeScript/Vite/Vitest. 새 runtime 의존성 없음.

**Spec:** `docs/modules/case/decisions/candidate-video-preview.md`

## Global Constraints

- rank 1~3 최대 3개, 빈 카드와 4위 보충 없음.
- 재생 요청은 selection/report/Fine/OCR/export를 변경하지 않는다.
- generation/span 고정, 성공·진행 중 요청 재사용, 실패 후 명시적 재요청.
- decode는 transaction 밖, HTTP read는 저장 media만 사용.
- 기존 download API와 #532 thumb_ref 의미 유지.

## Review Focus

- 서로 다른 후보 요청이 기존 same-kind supersede 정책에 의해 취소되지 않아야 한다.
- preview 대기 때문에 선택 후보의 Fine 발주나 결과 화면이 막히지 않아야 한다.
- 재탐색 중 이전 세대 ref와 늦은 결과가 새 카드에 붙지 않아야 한다.
- 외부/다른 Case ref 및 파손 media는 안전한 404/503 envelope이어야 한다.
- HTTP Range와 브라우저 오류가 다른 카드 및 신고자료를 바꾸지 않아야 한다.

## Tasks

1. [x] Case intent/projection: `case/candidate_video.py`, command/jobs/observation/reflection/view. `tests/case/test_candidate_video.py`로 개수·멱등·세대·선택 독립성을 RED→GREEN 확인.
2. [x] Worker/Recording: `worker/candidate_video.py`, incident composition/deployment registry, Recording `open_incident_clip`. 입력 결속·소유권·실제 MP4 생성·T2/replay 경계 테스트.
3. [x] HTTP: `api/routes_candidate_videos.py`, composition/app 연결. 현재 Case ref 확인·detached media·200/206/416·오류 테스트.
4. [x] Web: CandidateVideo primitive, 카드/비교/API 연결, 화면 선택에서 preview job 제외. `DESIGN.md` 상태 명세 후 UI 수별·실패·선택 독립·단일 재생 테스트 및 build.
5. [x] 통합: 관련 backend suite·Web 전체·boundary/quality·실제 live HTTP와 browser playback/seek를 실행하고 증거 기록.

## Evidence

- 시작 상태: develop `b34714fc08bb46751b6dbbc5c53ee64ec3f17a7c`, clean checkout에서 `codex/candidate-video-preview` 분기.
- Web baseline: 14 files / 242 passed. 기존 VideoThumb jsdom `load` 미구현 진단 출력 있음.
- Ruling: 사용자가 실행을 승인했으므로 추가 계획 승인 없이 같은 checkout의 별도 브랜치에서 작업한다. 기존 환경/의존성을 유지하고 unrelated worktree는 건드리지 않는다.

- Task 1: 50 passed (preview + observation chain + reselect). Current timeline revision is supplied by Recording projection, not an aggregate attribute; use candidate stale state and projection override.

- Tasks 2–4: real FFmpeg MP4 + worker/API focused 36 passed; Web 253 passed, build exits 0. Case/media follow-up 751 passed / 32 MySQL skips. Six old canonical scenario snapshots required the additive UNAVAILABLE field; updated source fixtures without weakening comparisons. Runtime ruff/mypy Linux and Windows passed. Boundary check passed with PYTHONUTF8=1.

- Task 5 complete: focused68/Web254/build/quality/boundary pass; final real browser/curl QA and two visual reviewers PASS. Full suite13792pass/26fail/1229skip: registry mismatch fixed, remaining24 failures reproduced on unchanged baseline; upload disconnect intermittent. No full-suite-green claim. See docs/runtime/candidate-video-preview.md and .omo/evidence/candidate-video/review-evidence.md.
- Final: fixed deployment expected-handler list — existing registration test RED→GREEN; final focused68passed.
- Ruling: no new cross-generation cancellation policy; generation/span filtering prevents old refs/results from reaching new cards, but old work may finish. No live MySQL was available; do not infer durability acceptance from memory QA.
