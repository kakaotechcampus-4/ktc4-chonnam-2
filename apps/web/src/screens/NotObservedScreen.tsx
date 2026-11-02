import type { JSX } from 'react'
import { isAction, type Action, type CaseView } from '../contracts/caseView'
import { ACTION_LABELS, noticeMessage } from '../contracts/labels'
import { CandidatesScreen } from './CandidatesScreen'
import { HintForm } from './SubScreens'

// 음성 결과(#168 [A]) — 가장 유력한 후보에서 위반이 관찰되지 않았다. 결과 화면의
// 변형이라 값 칸은 그리지 않는다. 다음 후보를 자동으로 확인하지 않고, 남은 후보를
// 바로 펼쳐 사용자가 고르게 한다. onSelect가 없으면(개발용 화면) 후보를 펼치지 않는다.
//
// restyled면 새 모양(refresh.css .rs)을 입힌다 — 아래 후보 그리드도 다른 후보 화면과 같은 모양이다.
// 이 화면에는 신고자료가 없으므로 1순위 카드 태그는 「지금 신고자료 기준」 대신 「먼저 확인한 장면」이다.
export function NotObservedScreen(props: {
  view: CaseView
  onSelect?: (candidateId: string) => void
  restyled?: boolean
  /** 처음부터 다시 — 서버 action과 따로 언제나 두는 고정 출구다(#410) */
  onNewReport?: () => void
  /** notice가 실은 동작(`설명 고치기` = `EDIT_HINT`, #431)을 연다. 없으면(시연) 버튼을 그리지 않는다 */
  onAction?: (noticeCode: string, action: Action) => void
  canRun?: (action: Action) => boolean
  /** 다른 후보가 없으면 설명 입력란을 화면에 바로 두고, 여기로 고친 설명을 보낸다 */
  onEditHint?: (description: string) => void
}): JSX.Element {
  const others = props.view.candidates.filter((c) => !c.selected).length
  const r = props.restyled
  const code = 'evidence.visual_event_not_observed'
  const { onAction, canRun } = props
  const actions =
    onAction && canRun ? (props.view.notices.find((n) => n.code === code)?.actions.filter(isAction).filter(canRun) ?? []) : []
  // 주 출구는 「다른 후보 보기」(core-user-flow §6). 다른 후보가 없을 때만 첫 버튼을 강조해 막다른 화면을 피한다
  const cls = (i: number) => `rs-btn ${others === 0 && i === 0 ? 'pri' : 'sec'}`
  // 다른 후보가 없으면 설명 고치기가 사실상 유일한 다음 행동이라 한 번 더 누르지 않게 입력란을 바로 둔다
  const inline = others === 0 && actions.includes('EDIT_HINT') && props.onEditHint
  return (
    <div className="stack">
      {/* 기존 모양일 때 감싸는 div는 display: contents라 .stack 간격이 그대로다 */}
      <div className={r ? 'rs rs-screen state-page notobs' : 'notobs-legacy'}>
        {/* 새 모양은 분석 중단 화면처럼 상태 문구가 h1이다(#509 #3). 기존 모양은 그대로 둔다 */}
        {r ? <p className="state-context">신고자료</p> : <h1 className="page-title">신고자료</h1>}
        <section className={r ? 'state-card' : 'panel panel-p stack'}>
          {r ? (
            <h1 className="state-head">{noticeMessage('notice.visual_event_not_observed')}</h1>
          ) : (
            <h2 className="panel-t">{noticeMessage('notice.visual_event_not_observed')}</h2>
          )}
          <p className={r ? 'state-body' : 'kv-src'}>
            영상은 정상적으로 확인했습니다.
            {others > 0 && ' 다른 장면이었다면 아래 후보 중에서 골라 주세요.'}
          </p>
          {r && props.onNewReport && inline && (
            <div className="hint-page">
              <HintForm view={props.view} onSearch={inline} onHome={props.onNewReport} />
            </div>
          )}
          {r && props.onNewReport && !inline && (
            <div className="state-actions">
              {actions.map((a, i) => (
                <button key={a} type="button" className={cls(i)} onClick={() => onAction!(code, a)}>
                  {ACTION_LABELS[a]}
                </button>
              ))}
              <button type="button" className={cls(actions.length)} onClick={props.onNewReport}>
                처음으로
              </button>
            </div>
          )}
        </section>
      </div>
      {others > 0 && props.onSelect && (
        <div className={r ? 'rs notobs-cands' : undefined}>
          <CandidatesScreen view={props.view} onSelect={props.onSelect} selectedLabel="먼저 확인한 장면" />
        </div>
      )}
    </div>
  )
}
