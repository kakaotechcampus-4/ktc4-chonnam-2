import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { noticeMessage } from '../contracts/labels'

// 음성 결과(#168 [A]) — 가장 유력한 후보에서 위반이 관찰되지 않았다. 결과 화면의
// 변형이라 값 칸은 그리지 않고, 출구는 「다른 후보 보기」 하나다. 다음 후보를
// 자동으로 확인하지 않는다.
export function NotObservedScreen(props: { view: CaseView; onCandidates?: () => void }): JSX.Element {
  const others = props.view.candidates.filter((c) => !c.selected).length
  return (
    <div className="stack">
      <h1 className="page-title">신고자료</h1>
      <section className="panel panel-p stack">
        <h2 className="panel-t">{noticeMessage('notice.visual_event_not_observed')}</h2>
        <p className="kv-src">영상은 정상적으로 확인했습니다. 다른 장면이었다면 찾은 후보 중에서 골라 주세요.</p>
        {others > 0 && props.onCandidates && (
          <button type="button" className="btn pri cta" onClick={props.onCandidates}>
            다른 후보 보기 ({others}건)
          </button>
        )}
      </section>
    </div>
  )
}
