import type { JSX } from 'react'
import { CircleAlert } from 'lucide-react'
import { isAction, type Action, type CaseView } from '../contracts/caseView'
import { ACTION_LABELS, noticeMessage } from '../contracts/labels'

// 시스템 실패(core-user-flow §23). AI의 낮은 확신과 다르다 — 「후보 없음」으로 보여 주지
// 않는다(#197). 다시 시도는 처음부터가 아니라 실패한 단계부터 이어서 한다.
// 빨강은 오류 아이콘과 짧은 핵심 안내에만 쓴다. 원인(notice 문구)과 다시 시도 안내는
// 기본 글자색으로 둔다.
export function FailedScreen(props: { view: CaseView; onAction: (noticeCode: string, action: Action) => void }): JSX.Element {
  const blocking = props.view.notices.filter((n) => n.blocking)
  // 버튼은 한 줄에 모으되, 누르면 어느 notice의 동작인지(code)도 함께 넘긴다(RUN_NOTICE_ACTION).
  const actions = blocking.flatMap((n) => n.actions.filter(isAction).map((a) => ({ code: n.code, a })))
  return (
    <div className="rs rs-screen state-page failed">
      <h1 className="state-context">신고자료</h1>
      <section className="state-card">
        <h2 className="failed-head">
          <CircleAlert size={26} strokeWidth={1.8} aria-hidden />
          영상을 살펴보다가 문제가 생겼어요.
        </h2>
        {blocking.map((n) => (
          <p key={n.code} className="state-cause">
            {noticeMessage(n.message_key)}
          </p>
        ))}
        <p className="state-body">지금까지 끝난 작업은 저장돼 있어요. 다시 시도하면 멈춘 곳부터 이어서 할게요.</p>
        {actions.length > 0 && (
          <div className="state-actions">
            {actions.map(({ code, a }) => (
              <button key={`${code}-${a}`} type="button" className="rs-btn pri" onClick={() => props.onAction(code, a)}>
                {ACTION_LABELS[a]}
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
