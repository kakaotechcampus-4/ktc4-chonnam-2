// `notices[].actions[]` → 발주 매핑.
//
// 계약 A절 §7의 「값→발주 매핑」 표를 그대로 옮긴다. web은 action 값을 해석하지
// 않고 이 표만 따른다. 아직 발주를 보낼 경로(case worker)가 없지만, **무엇을
// 보낼지는 계약이 이미 정해 뒀으므로** 여기까지는 지금 확정할 수 있다.
//
// 7종 중 3종만 새 JobRecord를 만들고, 4종은 발주 없이 web이 사용자 입력을
// 받는 동작이다. 이 구분을 코드에 박아 두지 않으면 나중에 「버튼 = 발주」로
// 뭉뚱그리게 된다.

import type { Action } from './caseView'

/** `JobRecord.kind` — 등재값 중 web이 발주할 수 있는 3종 (A절 §7) */
export type JobKind = 'PLATE_READ' | 'COARSE_SEARCH' | 'REPORT_VIDEO_EXPORT'

export type ActionIntent =
  | { type: 'JOB'; jobKind: JobKind; forceRerun: boolean; note: string }
  | { type: 'LOCAL_INPUT'; note: string }

export const ACTION_INTENT: Record<Action, ActionIntent> = {
  RETRY_PLATE_READ: {
    type: 'JOB',
    jobKind: 'PLATE_READ',
    // FAILED는 cache hit 대상이 아니라(A절 §7 캐시 재사용은 성공 결과에 한정)
    // 새 job_id만으로 재시도가 성립한다. EvidenceNeeds의 PLATE_REREAD 경로가
    // force_rerun=true를 붙이는 것과 다른 층위다 — 그건 case가 발주한다.
    forceRerun: false,
    note: '새 job_id로 번호판 재판독 발주',
  },
  RETRY_SEARCH: {
    type: 'JOB',
    jobKind: 'COARSE_SEARCH',
    forceRerun: false,
    note: '바뀐 단서 기준으로 재검색 발주',
  },
  GENERATE_REPORT_VIDEO: {
    type: 'JOB',
    jobKind: 'REPORT_VIDEO_EXPORT',
    forceRerun: false,
    note: '신고용 영상(DerivedAsset) 생성 발주',
  },
  EDIT_EVENT_TIME: { type: 'LOCAL_INPUT', note: '사용자 입력을 받아 시각 정정 — 발주 없음' },
  MANUAL_PLATE_INPUT: { type: 'LOCAL_INPUT', note: '사용자 입력을 받아 번호판 정정 — 발주 없음' },
  REVIEW_TIME: { type: 'LOCAL_INPUT', note: '시각 후보 중 선택/확인 — 발주 없음' },
  EDIT_HINT: { type: 'LOCAL_INPUT', note: '검색 단서 입력 — 발주 없음, 다음 재검색의 입력이 된다' },
}

export function describeIntent(action: Action): string {
  const intent = ACTION_INTENT[action]
  return intent.type === 'JOB'
    ? `JobRecord 발주 — kind=${intent.jobKind} · force_rerun=${intent.forceRerun} (${intent.note})`
    : `발주 없음 — ${intent.note}`
}
