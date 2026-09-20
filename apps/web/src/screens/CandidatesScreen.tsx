import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { CandidateCard } from '../components/CandidateCard'
import { HintRecall } from '../components/HintRecall'
import { Panel } from '../components/Panel'

// 후보를 세로로 쌓지 않고 나란히 놓는다(core-user-flow.md §8-2). 배열 순서를
// 그대로 그린다 — 정렬·순위 재계산은 case가 소유한 판정이다.
//
// 기억 단서는 후보 위에 한 번 놓는다. 대조는 하지 않는다(HintRecall 주석).
export function CandidatesScreen(props: { view: CaseView }): JSX.Element {
  return (
    <Panel title="찾은 장면">
      <HintRecall hints={props.view.hints} />
      <div className="cands">
        {props.view.candidates.map((c, i) => (
          <CandidateCard key={c.candidate_id} candidate={c} ordinal={i + 1} />
        ))}
      </div>
    </Panel>
  )
}
