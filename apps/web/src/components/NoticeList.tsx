import type { JSX } from 'react'
import type { Notice } from '../contracts/caseView'
import { isAction } from '../contracts/caseView'
import { ACTION_LABELS, noticeMessage } from '../contracts/labels'

// notices[].actions[]는 닫힌 7종이고 미등록 값은 버튼을 렌더하지 않는다
// (계약 B절 §7 — label_key와 달리 fallback을 두지 않는다. 실행 경로가 없는
// 액션을 잘못 노출하는 쪽이 더 위험하다).
function ActionButtons(props: { actions: string[] }): JSX.Element | null {
  const known = props.actions.filter(isAction)
  if (known.length === 0) return null
  return (
    <div className="btnrow" style={{ marginTop: 10 }}>
      {known.map((action) => (
        <button key={action} type="button" className="btn sm">
          {ACTION_LABELS[action]}
        </button>
      ))}
    </div>
  )
}

function NoticeItem(props: { notice: Notice; blocking: boolean }): JSX.Element {
  const { notice } = props
  return (
    <div className={`panel panel-p tight ${props.blocking ? 'notice-blocking' : 'notice-info'}`}>
      <div className="sec-label">
        {props.blocking ? '진행할 수 없음' : '안내'} · {notice.severity}
      </div>
      <div className="kv-val">{noticeMessage(notice.message_key)}</div>
      <div className="kv-src mono">{notice.code}</div>
      <ActionButtons actions={notice.actions} />
    </div>
  )
}

/** blocking과 non-blocking을 다르게 렌더한다 — 섞어 한 목록으로 두지 않는다. */
export function NoticeList(props: { blocking: Notice[]; info: Notice[] }): JSX.Element | null {
  if (props.blocking.length === 0 && props.info.length === 0) return null
  return (
    <div className="stack">
      {props.blocking.map((n) => (
        <NoticeItem key={n.code + n.message_key} notice={n} blocking />
      ))}
      {props.info.map((n) => (
        <NoticeItem key={n.code + n.message_key} notice={n} blocking={false} />
      ))}
    </div>
  )
}
