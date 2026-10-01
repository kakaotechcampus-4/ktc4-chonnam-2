import type { JSX, ReactNode } from 'react'
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

// 03_Sub_Candidate_Video — 후보를 나란히 놓는다. 「아니에요」는 고른 후보를
// 보내는 경로가 계약에 없어 비활성이다(#106).
export function CandidateCompare(props: {
  view: CaseView
  onBack: () => void
  onDetail: (candidateId: string) => void
}): JSX.Element {
  const { candidates } = props.view
  return (
    <SubPage title="후보 비교" onBack={props.onBack}>
      <h2 className="panel-t">찾은 장면 {candidates.length}개입니다.</h2>
      <div className="cand-grid">
        {candidates.map((c, i) => (
          <div key={c.candidate_id} className="cand-col">
            <CandidateCard candidate={c} ordinal={i + 1} />
            <div className="btnrow">
              <button type="button" className="btn sm" disabled title="계약 대기(#106)">
                아니에요
              </button>
              <button type="button" className="btn sm" onClick={() => props.onDetail(c.candidate_id)}>
                자세히
              </button>
            </div>
          </div>
        ))}
      </div>
    </SubPage>
  )
}

// 03_Sub_CandidateVideo_Details
export function CandidateDetail(props: { view: CaseView; candidateId: string; onBack: () => void }): JSX.Element {
  const index = props.view.candidates.findIndex((c) => c.candidate_id === props.candidateId)
  return (
    <SubPage title="후보 자세히" onBack={props.onBack}>
      <div className="video-main tall">
        <span className="video-play" aria-hidden>
          ▶
        </span>
      </div>
      {index >= 0 && <CandidateCard candidate={props.view.candidates[index]} ordinal={index + 1} />}
    </SubPage>
  )
}

// 03_Sub_Details_Check
export function DetailsCheck(props: { view: CaseView; onBack: () => void }): JSX.Element {
  return (
    <SubPage title="어떻게 정했는지" onBack={props.onBack}>
      <EvidenceScreen view={props.view} />
    </SubPage>
  )
}

// 03_Sub_Plate_Check — 원본 프레임 + 번호판 값 + 직접 입력. 번호판 프레임을
// 가리키는 필드가 CaseView에 아직 없어 자리만 둔다(#47).
export function PlateCheck(props: { view: CaseView; onBack: () => void }): JSX.Element {
  const plate = props.view.evidence?.plate_display
  return (
    <SubPage title="번호판 확인" onBack={props.onBack}>
      <div className="video-main tall">
        <span className="video-cap">원본 프레임 (계약 대기 #47)</span>
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
          <input className="field" style={{ marginTop: 12 }} placeholder="내가 아는 번호 입력" />
        </div>
      )}
    </SubPage>
  )
}
