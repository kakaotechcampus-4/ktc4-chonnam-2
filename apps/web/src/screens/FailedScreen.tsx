import type { JSX } from 'react'
import { CircleAlert } from 'lucide-react'
import { isAction, type Action, type CaseView } from '../contracts/caseView'
import { ACTION_LABELS, noticeMessage } from '../contracts/labels'
import { CandidatesScreen } from './CandidatesScreen'

// 시스템 실패(core-user-flow §23). AI의 낮은 확신과 다르다 — 「후보 없음」으로 보여 주지
// 않는다(#197). 다시 시도는 처음부터가 아니라 실패한 단계부터 이어서 한다. 다시 시도가 없는 실패
// (분석 범위 초과 · 클립 · Fine, #481 · #482)는 다른 후보와 「처음으로」가 출구다.
// 빨강은 오류 아이콘과 짧은 핵심 안내에만 쓴다. 원인(notice 문구)과 다시 시도 안내는
// 기본 글자색으로 둔다.
export function FailedScreen(props: {
  view: CaseView
  onAction: (noticeCode: string, action: Action) => void
  /** 지금 연결된 동작만 버튼으로 연다 — 나머지는 사용 불가와 이유를 보인다 */
  canRun: (action: Action) => boolean
  /** 다시 하기가 없는 실패(클립 · Fine)의 출구 — 다른 후보로 옮긴다. 없으면(시연) 후보를 두지 않는다 */
  onSelect?: (candidateId: string) => void
  /** 처음부터 다시 — 분석 범위 초과처럼 다른 출구가 없을 때 막다른 화면을 피한다 */
  onNewReport?: () => void
}): JSX.Element {
  const blocking = props.view.notices.filter((n) => n.blocking)
  // 버튼은 한 줄에 모으되, 누르면 어느 notice의 동작인지(code)도 함께 넘긴다(RUN_NOTICE_ACTION).
  const actions = blocking.flatMap((n) => n.actions.filter(isAction).map((a) => ({ code: n.code, a })))
  const others = props.onSelect ? props.view.candidates.filter((c) => !c.selected).length : 0
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
        {actions.length > 0 && (
          <p className="state-body">지금까지 끝난 작업은 저장돼 있어요. 다시 시도하면 멈춘 곳부터 이어서 할게요.</p>
        )}
        {others > 0 && <p className="state-body">다른 장면이었다면 아래 후보 중에서 골라 주세요.</p>}
        {(actions.length > 0 || props.onNewReport) && (
          <div className="state-actions">
            {actions.map(({ code, a }) =>
              props.canRun(a) ? (
                <button key={`${code}-${a}`} type="button" className="rs-btn pri" onClick={() => props.onAction(code, a)}>
                  {ACTION_LABELS[a]}
                </button>
              ) : (
                <span key={`${code}-${a}`} className="res-action-off">
                  <button type="button" className="rs-btn sec" disabled aria-describedby={`off-${code}-${a}`}>
                    {ACTION_LABELS[a]}
                  </button>
                  <span id={`off-${code}-${a}`} className="res-off-why">
                    아직 이 화면에서 할 수 없어요
                  </span>
                </span>
              ),
            )}
            {props.onNewReport && (
              <button
                type="button"
                className={`rs-btn ${actions.length === 0 && others === 0 ? 'pri' : 'sec'}`}
                onClick={props.onNewReport}
              >
                처음으로
              </button>
            )}
          </div>
        )}
      </section>
      {others > 0 && (
        <div className="rs notobs-cands">
          <CandidatesScreen view={props.view} onSelect={props.onSelect!} selectedLabel="먼저 확인한 장면" />
        </div>
      )}
    </div>
  )
}
