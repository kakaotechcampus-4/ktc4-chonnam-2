import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { noticeMessage } from '../contracts/labels'
import { CandidatesScreen } from './CandidatesScreen'

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
  /** 처음부터 다시 — 이 화면에는 case가 실은 다시 찾기 동작이 없다(출구는 「다른 후보 보기」, core-user-flow §6).
   *  다른 후보가 없으면 막다른 화면이 되지 않게 주 버튼, 있으면 후보 고르기 다음 순위라 보조 버튼이다 */
  onNewReport?: () => void
}): JSX.Element {
  const others = props.view.candidates.filter((c) => !c.selected).length
  const r = props.restyled
  return (
    <div className="stack">
      {/* 기존 모양일 때 감싸는 div는 display: contents라 .stack 간격이 그대로다 */}
      <div className={r ? 'rs rs-screen state-page notobs' : 'notobs-legacy'}>
        <h1 className={r ? 'state-context' : 'page-title'}>신고자료</h1>
        <section className={r ? 'state-card' : 'panel panel-p stack'}>
          <h2 className={r ? 'state-head' : 'panel-t'}>{noticeMessage('notice.visual_event_not_observed')}</h2>
          <p className={r ? 'state-body' : 'kv-src'}>
            영상은 정상적으로 확인했습니다.
            {others > 0 && ' 다른 장면이었다면 아래 후보 중에서 골라 주세요.'}
          </p>
          {r && props.onNewReport && (
            <div className="state-actions">
              <button type="button" className={`rs-btn ${others > 0 ? 'sec' : 'pri'}`} onClick={props.onNewReport}>
                새 신고
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
