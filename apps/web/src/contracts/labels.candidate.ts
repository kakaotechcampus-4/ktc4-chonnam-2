// 후보 화면 전용 문구 — `labels.ts`에 합치는 것은 web Owner가 한다.
//
// 여기 있는 것은 계약의 `*_label_key`가 아니다. `CaseView.hints`의 필드 이름을
// 화면 문구로 바꾸는 표이고, 키는 계약이 아니라 이 파일이 소유한다
// (`SITUATION_LABELS`가 `labels.ts`에서 같은 취급을 받는 것과 같다 —
// value-state-display.md §5-3).

/** `CaseView.hints`의 네 필드 — 사용자가 말한 기억 단서 */
export const HINT_LABELS = {
  time: '시간대',
  vehicle: '차량',
  situation: '상황',
  location: '위치',
} as const

export type HintKey = keyof typeof HINT_LABELS

/** 표시 순서. 사용자가 말한 순서가 아니라 화면에서 읽기 좋은 순서다. */
export const HINT_ORDER: readonly HintKey[] = ['time', 'vehicle', 'situation', 'location']

export const HINT_NONE = '기억 단서를 남기지 않으셨습니다.'
