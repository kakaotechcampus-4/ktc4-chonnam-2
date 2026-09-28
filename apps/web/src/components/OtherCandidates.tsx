import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { CandidatesScreen } from '../screens/CandidatesScreen'
import '../styles/candidates.css'

// 결과 화면의 「다른 후보 보기」(core-user-flow.md §8-1). 후보 비교는 기본
// 화면이 아니라 사용자가 현재 결과가 아니라고 볼 때만 여는 선택 경로다.
// 그래서 접힌 채로 시작한다.
//
// 결과 화면(EvidenceScreen·HandoffScreen)과 화면 선택(selectScreen)은 web
// Owner 소유라 여기서는 붙일 자리만 만든다.
//
// 이 후보로 새 초안을 만드는 버튼은 없다. 고른 후보를 보내는 경로가 계약에
// 없다(#106).
export function OtherCandidates(props: { view: CaseView }): JSX.Element | null {
  if (props.view.candidates.length === 0) return null
  return (
    <details className="other-cands">
      <summary>다른 후보 보기 ({props.view.candidates.length}건)</summary>
      <div className="other-cands-body">
        <CandidatesScreen view={props.view} />
      </div>
    </details>
  )
}
