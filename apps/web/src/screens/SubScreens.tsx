import { useState, type JSX, type ReactNode } from 'react'
import type { CaseView } from '../contracts/caseView'
import { CandidateCard } from '../components/CandidateCard'
import { DisplayRow } from '../components/DisplayRow'
import { EvidenceScreen } from './EvidenceScreen'

// Figma 03_Sub_* 공통 틀: 「<」 뒤로 + 제목 + 본문.
function SubPage(props: { title: string; onBack: () => void; children: ReactNode }): JSX.Element {
  return (
    <div className="stack">
      <h1 className="page-title sub-title">
        <button type="button" className="back" onClick={props.onBack} aria-label="뒤로">
          &lt;
        </button>
        {props.title}
      </h1>
      {props.children}
    </div>
  )
}

// 지금 신고자료 기준 후보는 빼고 다른 후보만 나란히 놓는다. 번호는 candidates[] 안의
// 자리라 시간축 마커 번호와 같다. 고르면 그 후보로 신고자료를 새로 준비한다
// (core-user-flow §8-1) — 실제 전송은 #106 command가 생기면 붙는다.
export function OtherCandidateGrid(props: { view: CaseView; onSelect: (candidateId: string) => void }): JSX.Element {
  const others = props.view.candidates
    .map((c, i) => ({ c, ordinal: i + 1 }))
    .filter(({ c }) => !c.selected)
  return (
    <div className="cand-grid">
      {others.map(({ c, ordinal }) => (
        <div key={c.candidate_id} className="cand-col">
          <CandidateCard candidate={c} ordinal={ordinal} />
          <button type="button" className="btn sm pri" onClick={() => props.onSelect(c.candidate_id)}>
            이 장면으로 다시 준비
          </button>
        </div>
      ))}
    </div>
  )
}

// 03_Sub_Candidate_Video
export function CandidateCompare(props: {
  view: CaseView
  onBack: () => void
  onSelect: (candidateId: string) => void
}): JSX.Element {
  const count = props.view.candidates.filter((c) => !c.selected).length
  return (
    <SubPage title="다른 후보" onBack={props.onBack}>
      <h2 className="panel-t">다른 후보 {count}개</h2>
      <OtherCandidateGrid view={props.view} onSelect={props.onSelect} />
    </SubPage>
  )
}

// 03_Sub_Details_Check
export function DetailsCheck(props: { view: CaseView; onBack: () => void }): JSX.Element {
  return (
    <SubPage title="어떻게 정했는지" onBack={props.onBack}>
      {/* 다른 후보는 결과 화면의 「다른 후보 영상」에서만 연다 */}
      <EvidenceScreen view={props.view} hideOthers />
    </SubPage>
  )
}

// 03_Sub_Plate_Check — 원본 프레임 + 번호판 값 + 직접 입력. 번호판 프레임을
// 가리키는 필드가 CaseView에 아직 없어 자리만 둔다(#47).
// ponytail: 직접 입력을 case로 보내는 경로가 아직 계약에 없다(MANUAL_PLATE_INPUT, #212·#217).
// 시연에서는 화면 안에서만 반영한다 — command가 생기면 onApply 자리에서 보낸다.
export function PlateCheck(props: { view: CaseView; onBack: () => void; onApply: (plate: string) => void }): JSX.Element {
  const [typed, setTyped] = useState('')
  const plate = props.view.evidence?.plate_display
  return (
    <SubPage title="번호판 확인" onBack={props.onBack}>
      <div className="video-main tall">
        <span className="video-cap">번호판 장면 미리보기 준비 중</span>
      </div>
      {plate && (
        <div className="panel panel-p">
          <div className="kv kv-rows">
            <DisplayRow
              label="차량 번호"
              value={plate.value}
              infoState={plate.info_state}
              sourceLabelKey={plate.source_label_key}
            />
          </div>
          <form
            className="plate-form"
            onSubmit={(e) => {
              e.preventDefault()
              if (typed.trim()) props.onApply(typed.trim())
            }}
          >
            <input
              className="field"
              placeholder="내가 아는 번호 입력 (예: 12가3456)"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
            />
            <button type="submit" className="btn pri" disabled={!typed.trim()}>
              이 번호로 바꾸기
            </button>
          </form>
        </div>
      )}
    </SubPage>
  )
}
