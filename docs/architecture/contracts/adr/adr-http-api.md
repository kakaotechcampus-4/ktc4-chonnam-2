# ADR — HTTP API Contract (web ↔ api)

**Status:** Proposed — `contract-http-api.md` `Draft — Consumer Review`와 함께 둔다. web Consumer review와 case · recording boundary review가 끝나면 §5에 기록하고 Accepted로 바꾼다.

**Decider:** 김준영 (`api` composition root, HTTP API Contract Producer)
**Date:** 2026-10-04
**Contract:** `../contract-http-api.md`
**상위 결정:** [#247](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/247) RD-05 H-1 ~ H-6 (ACCEPTED 2026-10-04) · 입력 [#245](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/245) D-2 · D-3 · C-1 · C-3 · [#246](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/246) S-2 · S-4 · S-5

---

## 1. Context

#247은 HTTP 경계의 Owner · endpoint 집합 · 202/200 기준 · polling 정지 조건 · upload 방식 · 오류 status 표를 정했고, 계약 문서 작성은 다음 단계로 넘겼다(Runtime Tech Spec §13). web은 아직 fixture 기반이라 실연동 전에 경로 · body · status를 하나로 고정해야 했다.

## 2. Decision

**#247에서 정한 것은 그대로 옮기고, HTTP에만 있는 의미만 새로 정했다.** 계약 스키마는 계약 문서에만 둔다.

#247에서 그대로 온 것 — endpoint 8개 · job 상태 endpoint 없음 · domain action = command `kind` · JobRecord ≥ 1 발주면 `202`, 아니면 `200`(composition root가 append 목록으로 판단) · body = case-command 응답 그대로 · `running_jobs=[]`이면 polling 정지 · 1 request = 1 file · 응답 전 publish · 등록 완료 · H-6 status 표.

새로 정한 것:

- **오류 envelope = case-command 응답 모양.** case 실패와 transport 실패를 web이 같은 코드로 읽는다. case 실패는 case body 그대로, transport 실패는 `http.*` code와 `case_view=null`.
- **HTTP 층은 command body 모양을 검사하지 않는다.** case가 이미 모양 오류를 `invalid_payload`로 판정하므로(`src/daesingo/case/command.py`) 두 층이 같은 판단을 나눠 하지 않게 했다. 예외는 path와 body의 `case_id` 불일치 하나(transport 불일치).
- **422 = transport는 정상, 내용을 domain · capability가 거부.** 400 = transport 단계에서 읽을 수 없음. 415 = request `Content-Type`. 그래서 「등록할 수 없는 영상」은 415가 아니라 422(`http.source_rejected`)다.
- **resource isolation.** 다른 case의 ref는 존재 여부와 무관하게 `404 http.not_found`. 소유는 recording의 case↔asset 연결로 판단한다.
- **소유했지만 bytes가 없으면 `404 http.ref_unavailable`.**
- **asset 「생성 전」 응답을 두지 않는다.** ReportPackage는 신고용 영상이 있어야만 존재하므로(ReportPackage 계약 §8.1) `artifact_ref`가 보이는 시점에는 이미 생성돼 있다.
- **upload `filename`은 사용자 원본 파일명으로 recording에 넘긴다.** recording은 파일명에서 시각 출처(`FILENAME`)를 찾는다.

## 3. 기각한 안

- **`410 Gone`(asset 정리 뒤)** — `availability=UNAVAILABLE`은 「존재하지 않음」과 「접근 · decode 불가」를 함께 뜻해 영구성을 말할 근거가 없다. RFC 9110은 영구성을 모르면 404를 쓰라고 한다. purge 뒤 ref 의미(RD-10)가 정해지면 다시 본다.
- **asset 생성 전 `409`** — 생성 전에는 web이 가진 ref가 없으므로 쓰일 경로가 없다.
- **FrameRef 실패를 `500`** — S-4 보장 위반 가능성이 있지만 web에게는 재시도 대상이 아니다. 일시 실패만 `503`.
- **FastAPI 기본 422 `{"detail": ...}`** — envelope이 둘이 되고 case `invalid_payload`와 겹친다.
- **upload part 형식 · 확장자로 영상 판정** — client가 보낸 값이라 믿을 수 없고, 판정은 recording 등록의 일이다.

## 4. 남긴 것

계약 §9 표가 소유한다. 주요 선행 조건 — 빈 case 생성 진입점(case) · 202 응답의 `running_jobs`에 이번 발주 포함(case) · 등록 실패 분류 · 원본 파일명 전달 · ref 소유 조회 · DerivedAsset bytes 열기(recording) · FrameRef 이미지 경로 배치 승인(recording · case).

## 5. Consumer Review

| 검토자 | 범위 | 결과 |
| --- | --- | --- |
| 신유민 (`web`) | 필수 Consumer — 계약 §6 흐름 | 대기 |
| 유소연 (`case`) | command · CaseView · 빈 case · 202/200 | 대기 |
| 정철원 (`recording`) | upload · FrameRef · asset · ref 소유 | 대기 |
