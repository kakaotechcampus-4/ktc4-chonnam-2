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

// 03_Sub_Plate_Check — 번호판을 읽은 장면과 번호판 확대를 나란히 두고, 여기서 번호를 고친다.
// 두 이미지는 계약상 FrameRef(evidence.preview_ref · plate_preview_ref)로만 와서 아직 그릴 수 없다 —
// ref로 이미지를 가져오는 경로가 생기면(#47) 자리에 넣는다.
// 수정은 읽은 값을 채운 채 열어 틀린 글자만 고치게 한다.
export function PlateCheck(props: { view: CaseView; onBack: () => void; onEdit: (plate: string) => void }): JSX.Element {
  const [editing, setEditing] = useState<string | null>(null)
  const evidence = props.view.evidence
  if (!evidence) return <SubPage title="번호판 확인" onBack={props.onBack}>번호판 정보가 없어요.</SubPage>
  const plate = evidence.plate_display
  return (
    <SubPage title="번호판 확인" onBack={props.onBack}>
      <div className="plate-frames">
        <figure>
          <div className="video-main">
            <span className="video-cap">장면 이미지 준비 중</span>
          </div>
          <figcaption className="kv-src">번호판을 읽은 장면</figcaption>
        </figure>
        <figure>
          <div className="video-main plate-crop">
            <span className="video-cap">번호판 이미지 준비 중</span>
          </div>
          <figcaption className="kv-src">번호판 확대</figcaption>
        </figure>
      </div>
      <div className="panel panel-p">
        {editing === null ? (
          <div className="plate-value-row">
            <div className="kv kv-rows">
              <DisplayRow
                label="차량 번호"
                value={plate.value}
                infoState={plate.info_state}
                sourceLabelKey={plate.source_label_key}
              />
            </div>
            <button type="button" className="btn sm" onClick={() => setEditing(plate.value ?? '')}>
              번호 수정
            </button>
          </div>
        ) : (
          <form
            className="plate-form"
            onSubmit={(e) => {
              e.preventDefault()
              if (editing.trim()) props.onEdit(editing.trim())
              setEditing(null)
            }}
          >
            <input
              className="field plate-input"
              aria-label="차량 번호"
              autoFocus
              value={editing}
              onChange={(e) => setEditing(e.target.value)}
            />
            <button type="submit" className="btn pri" disabled={!editing.trim()}>
              저장
            </button>
            <button type="button" className="btn" onClick={() => setEditing(null)}>
              취소
            </button>
          </form>
        )}
      </div>
    </SubPage>
  )
}
