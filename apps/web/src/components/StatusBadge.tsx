import type { JSX } from 'react'
import type { InfoState } from '../contracts/caseView'
import { INFO_STATE_LABELS } from '../contracts/labels'

// 프로토타입 StatusBadge의 클래스를 그대로 쓴다. 값 이름만 InfoStatus 5종 →
// info_state 5종으로 바뀐다(web-stack.md 승계 표).
const BADGE_CLASS: Record<InfoState, string> = {
  INFO_SOURCE_VERIFIED: 'badge-confirmed',
  INFO_USER_CONFIRMED: 'badge-user-confirmed',
  INFO_AI_ESTIMATED: 'badge-estimated',
  INFO_NEEDS_REVIEW: 'badge-attention',
  INFO_UNKNOWN: 'badge-unknown',
}

export function StatusBadge(props: { state: InfoState }): JSX.Element {
  return (
    <span className={`badge ${BADGE_CLASS[props.state]}`}>
      <span className="dot" />
      <span>{INFO_STATE_LABELS[props.state]}</span>
    </span>
  )
}
