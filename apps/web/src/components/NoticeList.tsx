import type { JSX } from 'react'
import type { Notice } from '../contracts/caseView'
import { isAction } from '../contracts/caseView'
import type { Action } from '../contracts/caseView'
import { ACTION_LABELS, noticeMessage } from '../contracts/labels'
import { DevExtra } from './DevExtra'

// notices[].actions[]는 닫힌 7종이고 미등록 값은 버튼을 렌더하지 않는다
// (계약 B절 §7 — label_key와 달리 fallback을 두지 않는다. 실행 경로가 없는
// 액션을 잘못 노출하는 쪽이 더 위험하다).
function ActionButtons(props: { actions: string[]; onAction: (action: Action) => void }): JSX.Element | null {
  const known = props.actions.filter(isAction)
  if (known.length === 0) return null
  return (
    <div className="btnrow" style={{ marginTop: 10 }}>
      {known.map((action) => (
        <button key={action} type="button" className="btn sm" onClick={() => props.onAction(action)}>
          {ACTION_LABELS[action]}
        </button>
      ))}
    </div>
  )
}

function NoticeItem(props: { notice: Notice; blocking: boolean; onAction: (action: Action) => void }): JSX.Element {
  const { notice } = props
  return (
    <div className={`panel panel-p tight ${props.blocking ? 'notice-blocking' : 'notice-info'}`}>
      <div className="sec-label">
        {props.blocking ? '진행할 수 없음' : '안내'} · {notice.severity}
      </div>
      <div className="kv-val">{noticeMessage(notice.message_key)}</div>
      <ActionButtons actions={notice.actions} onAction={props.onAction} />
    </div>
  )
}

/**
 * 어느 `code`가 어느 문구로 갔는지는 증빙에 필요하지만 **사용자에게 보일 값은 아니다**
 * (`evidence.reason_code`를 걷어낸 것과 같은 이유). 문구 옆에 두지 않고 목록 끝에 한 번
 * 접어 둔다 — 펼치면 매핑이 그대로 보이고, 접혀 있으면 화면이 제품 흐름과 같은 모양이 된다.
 */
function CodeMapping(props: { notices: Notice[] }): JSX.Element {
  return (
    <DevExtra label={`증빙용 — notice code ${props.notices.length}건`}>
      <div className="kv kv-rows">
        {props.notices.map((n) => (
          <div className="kv-row" key={n.code + n.message_key}>
            <span className="kv-k mono">{n.code}</span>
            <span className="kv-v">
              <span className="kv-val">{noticeMessage(n.message_key)}</span>
              <span className="kv-src mono">
                {n.message_key} · {n.severity} · {n.blocking ? 'blocking' : 'non-blocking'}
              </span>
            </span>
          </div>
        ))}
      </div>
    </DevExtra>
  )
}

/** blocking과 non-blocking을 다르게 렌더한다 — 섞어 한 목록으로 두지 않는다. */
export function NoticeList(props: {
  blocking: Notice[]
  info: Notice[]
  onAction: (action: Action) => void
}): JSX.Element | null {
  if (props.blocking.length === 0 && props.info.length === 0) return null
  return (
    <div className="stack">
      {props.blocking.map((n) => (
        <NoticeItem key={n.code + n.message_key} notice={n} blocking onAction={props.onAction} />
      ))}
      {props.info.map((n) => (
        <NoticeItem key={n.code + n.message_key} notice={n} blocking={false} onAction={props.onAction} />
      ))}
      <CodeMapping notices={[...props.blocking, ...props.info]} />
    </div>
  )
}
