import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { CandidatesScreen } from '../screens/CandidatesScreen'
import '../styles/candidates.css'

// 결과 화면의 「다른 후보 보기」(core-user-flow.md §8-1). 후보 비교는 기본
// 화면이 아니라 사용자가 현재 결과가 아니라고 볼 때만 여는 선택 경로다.
// 그래서 접힌 채로 시작한다.
//
// 지금은 `?dev` 스냅샷 보기(CaseScreen · EvidenceScreen · HandoffScreen)에서만 쓴다.
// 그래서 고르는 버튼(onSelect)을 넘기지 않는다. 실제 흐름에서 다른 후보를 고르는 곳은
// 결과 화면의 「다른 후보」 하위 화면(SubScreens의 CandidateCompare → CandidatesScreen)이고,
// 고르면 ApiFlow가 SELECT_OTHER_CANDIDATE command를 보낸다.
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
