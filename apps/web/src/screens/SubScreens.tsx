import { useEffect, useRef, useState, type JSX, type ReactNode } from 'react'
import { ChevronLeft, Film } from 'lucide-react'
import type { CaseView } from '../contracts/caseView'
import { sourceLabel } from '../contracts/labels'
import { CandidateCard } from '../components/CandidateCard'
import { StatusBadge } from '../components/StatusBadge'
import { CandidatesScreen } from './CandidatesScreen'
import { EvidenceScreen } from './EvidenceScreen'

// Figma 03_Sub_* 공통 틀: 「<」 뒤로 + 제목 + 본문.
// 열리면 제목이 키보드 포커스를 받아 화면이 바뀐 것을 알린다. 뒤로는 결과 화면으로 돌아간다.
function SubPage(props: { title: string; onBack: () => void; children: ReactNode; className?: string }): JSX.Element {
  const head = useRef<HTMLHeadingElement>(null)
  const root = useRef<HTMLDivElement>(null)
  // 안의 입력칸이 이미 포커스를 받았으면(번호판 직접 입력으로 연 경우) 빼앗지 않는다.
  useEffect(() => {
    if (!root.current?.contains(document.activeElement)) head.current?.focus({ preventScroll: true })
  }, [])
  return (
    <div ref={root} className={`rs rs-screen sub${props.className ? ` ${props.className}` : ''}`}>
      <div className="sub-head">
        <button type="button" className="sub-back" onClick={props.onBack} aria-label="뒤로">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden />
        </button>
        <h1 className="sub-title" ref={head} tabIndex={-1}>
          {props.title}
        </h1>
      </div>
      {props.children}
    </div>
  )
}

// 03_Sub_Candidate_Video — 기준 후보와 다른 후보를 나란히 두고, 고르면 그 후보로
// 신고자료를 새로 준비한다(core-user-flow §8-1). 그리드·기억 단서는 CandidatesScreen 것을 쓴다.
export function CandidateCompare(props: {
  view: CaseView
  onBack: () => void
  onSelect: (candidateId: string) => void
}): JSX.Element {
  return (
    <SubPage title="다른 후보" onBack={props.onBack} className="cands-page">
      <CandidatesScreen view={props.view} onSelect={props.onSelect} />
    </SubPage>
  )
}

// 03_Sub_Details_Check — 왼쪽에 지금 신고자료의 기준 장면(후보 카드: AI가 본 내용·시각 출처),
// 오른쪽에 그 장면에서 정한 값과 출처·상태를 나란히 둔다. 어느 장면에서 무엇을 정했는지 한 화면에서 본다.
export function DetailsCheck(props: { view: CaseView; onBack: () => void }): JSX.Element {
  const i = props.view.candidates.findIndex((c) => c.selected)
  const basis = i >= 0 ? props.view.candidates[i] : null
  return (
    <SubPage title="어떻게 정했는지" onBack={props.onBack} className="details-page">
      <div className={basis ? 'details-grid' : undefined}>
        {basis && (
          <aside className="details-scene">
            <CandidateCard candidate={basis} ordinal={i + 1} />
          </aside>
        )}
        {/* 다른 후보는 결과 화면의 「다른 후보 영상」에서만 연다 */}
        <EvidenceScreen view={props.view} hideOthers />
      </div>
    </SubPage>
  )
}

// 03_Sub_Plate_Check — 번호판을 읽은 장면과 번호판 확대를 나란히 두고, 여기서 번호를 고친다.
// 두 이미지는 계약상 FrameRef(evidence.preview_ref · plate_preview_ref)로만 와서 아직 그릴 수 없다 —
// ref로 이미지를 가져오는 경로가 생기면(#47) 자리에 넣는다.
// 수정은 읽은 값을 채운 채 열어 틀린 글자만 고치게 한다.
//   저장 — 고친 값이 사건의 번호판이 된다(사용자 확인됨). 결과·자세히 보기를 오가도 유지된다.
//   취소·Esc·뒤로 — 고치던 글자만 버리고, 마지막으로 저장한 값(없으면 읽은 값)을 그대로 둔다.
// aiValue는 번호판 판독이 읽은 값이다. 사용자가 고친 값과 다르면 함께 보여 무엇을 바꿨는지 알 수 있게 한다.
// ponytail: 시연은 화면 안에서만 반영한다 — 번호판 직접 입력 command(MANUAL_PLATE_INPUT)는 다음 판본이다.
export function PlateCheck(props: {
  view: CaseView
  aiValue: string | null
  /** 「번호판 직접 입력」 notice 동작으로 열면 바로 고치는 칸을 연다 */
  startEditing?: boolean
  onBack: () => void
  onEdit: (plate: string) => void
}): JSX.Element {
  const [editing, setEditing] = useState<string | null>(() =>
    props.startEditing ? (props.view.evidence?.plate_display.value ?? '') : null,
  )
  const editButton = useRef<HTMLButtonElement>(null)
  const refocus = useRef(false)
  useEffect(() => {
    if (editing === null && refocus.current) {
      refocus.current = false
      editButton.current?.focus()
    }
  }, [editing])
  const close = () => {
    refocus.current = true
    setEditing(null)
  }
  const evidence = props.view.evidence
  if (!evidence)
    return (
      <SubPage title="번호판 확인" onBack={props.onBack}>
        <p className="state-body">번호판 정보가 없어요.</p>
      </SubPage>
    )
  const plate = evidence.plate_display
  const src = sourceLabel(plate.source_label_key)
  const edited = plate.info_state === 'INFO_USER_CONFIRMED' && props.aiValue !== plate.value
  return (
    <SubPage title="번호판 확인" onBack={props.onBack} className="plate-page">
      <div className="plate-grid">
        <figure className="plate-fig plate-scene">
          <div className="plate-frame">
            <Film size={26} strokeWidth={1.5} aria-hidden />
            <span>장면 이미지 준비 중</span>
          </div>
          <figcaption>번호판을 읽은 장면</figcaption>
        </figure>
        <div className="plate-side">
          <figure className="plate-fig">
            <div className="plate-frame plate-crop">
              <Film size={24} strokeWidth={1.5} aria-hidden />
              <span>번호판 이미지 준비 중</span>
            </div>
            <figcaption>번호판 확대</figcaption>
          </figure>
          <section className="plate-value" aria-labelledby="plate-k">
            <h2 className="res-k" id="plate-k">
              차량 번호
            </h2>
            {editing === null ? (
              <>
                <p className={`res-plate-v${plate.value === null ? ' is-none' : ''}`}>{plate.value ?? '알 수 없음'}</p>
                <div className="res-plate-meta">
                  <StatusBadge state={plate.info_state} />
                  {src && <span className="res-src">{src}</span>}
                </div>
                {edited && (
                  <>
                    <p className="plate-ai">
                      AI가 읽은 값 <b>{props.aiValue ?? '알 수 없음'}</b>
                    </p>
                    <p className="plate-local">이 화면에서만 바꿨어요. 서버에는 아직 저장되지 않아요.</p>
                  </>
                )}
                <button
                  type="button"
                  ref={editButton}
                  className="rs-btn sec"
                  onClick={() => setEditing(plate.value ?? '')}
                >
                  번호 수정
                </button>
              </>
            ) : (
              <form
                className="plate-form"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (editing.trim()) props.onEdit(editing.trim())
                  close()
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') close()
                }}
              >
                <input
                  className="plate-input"
                  aria-label="차량 번호"
                  autoFocus
                  value={editing}
                  onChange={(e) => setEditing(e.target.value)}
                />
                <div className="plate-form-actions">
                  <button type="submit" className="rs-btn pri" disabled={!editing.trim()}>
                    저장
                  </button>
                  <button type="button" className="rs-btn sec" onClick={close}>
                    취소
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      </div>
    </SubPage>
  )
}
