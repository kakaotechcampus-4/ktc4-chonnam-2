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
//
// 건수는 지금 신고자료 기준(`selected`)을 뺀 나머지만 센다. 나머지가 없으면
// 열어도 같은 후보만 나오므로 출구를 두지 않는다. 펼친 그리드에는 기준 후보도
// 함께 둔다 — 나란히 놓아야 비교가 된다.
export function OtherCandidates(props: { view: CaseView }): JSX.Element | null {
  const others = props.view.candidates.filter((c) => !c.selected).length
  if (others === 0) return null
  return (
    <details className="other-cands">
      <summary>다른 후보 보기 ({others}건)</summary>
      <div className="other-cands-body">
        <CandidatesScreen view={props.view} />
      </div>
    </details>
  )
}
