import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { CandidateCard } from '../components/CandidateCard'
import { Panel } from '../components/Panel'

export function CandidatesScreen(props: { view: CaseView }): JSX.Element {
  return (
    <Panel title="찾은 장면">
      <div className="stack">
        {props.view.candidates.map((c) => (
          <CandidateCard key={c.candidate_id} candidate={c} />
        ))}
      </div>
    </Panel>
  )
}
