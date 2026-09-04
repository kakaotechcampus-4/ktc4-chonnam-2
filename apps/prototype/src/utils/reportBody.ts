import type { CaseState } from '../types';

/**
 * 최종 리뷰 fix wave finding #3 — 신고문 본문 조립 로직.
 *
 * ReviewScreen.tsx의 "안전신문고에 붙여넣을 신고문" 편집이 예전에는 `title` 필드를 그대로
 * 덮어써서, HandoffScreen의 제목(title.value)과 신고 내용(reportBodyFor 결과)이 편집 후 완전히
 * 같은 문자열이 되어버리는 문제가 있었다. 이제 `CaseState.reportBody`가 이 문단 전용 필드이므로,
 * `title`은 더 이상 이 함수들이 건드리지 않는다.
 *
 * ReviewScreen.tsx와 HandoffScreen.tsx가 같은 소스를 쓰도록 여기 한 곳에만 둔다(Task 16이
 * `reportBodyFor`를 ReviewScreen.tsx에서 export해 공유했던 것과 같은 이유 — 두 화면이 갈라지면
 * 안 된다).
 */
function buildReportParagraph(c: Pick<CaseState, 'occurredAt' | 'location' | 'plate' | 'situation' | 'clip'>): string {
  const occurred = c.occurredAt.value ?? '시각 미상';
  const location = c.location.value ?? '위치 미상';
  const plateText =
    c.plate.status === 'unknown' || !c.plate.value ? '번호를 확인하지 못한 차량' : `${c.plate.value} 차량`;
  const situation = c.situation.value ?? '위반이 의심되는 상황';
  return (
    // Task 17 fix: both branches of plateText end in "차량" (ㅇ batchim, consonant-final),
    // which takes the subject particle "이", never "가".
    `${occurred}경, ${location}에서 ${plateText}이 ${situation}. ` +
    `첨부한 영상 ${c.clip.duration} 구간에서 실제 장면을 확인하실 수 있습니다.`
  );
}

/** createInitialCase()가 `reportBody.value`의 초깃값을 채울 때도 이 그대로를 쓴다. */
export { buildReportParagraph };

// If the user has already edited+saved the report text, `reportBody` holds that edited
// paragraph (status flips to 'user-confirmed') and is the source of truth from then on —
// otherwise the paragraph is rebuilt fresh from the other fields each render, so plate/
// situation/etc. edits made back on PrepareScreen (via BACK) are reflected without a stale draft.
export function reportBodyFor(c: CaseState): string {
  return c.reportBody.status === 'user-confirmed' ? (c.reportBody.value ?? '') : buildReportParagraph(c);
}
