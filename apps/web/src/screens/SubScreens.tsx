import { useEffect, useRef, useState, type JSX, type ReactNode } from 'react'
import { ChevronLeft, Film } from 'lucide-react'
import type { CaseView } from '../contracts/caseView'
import { sourceLabel } from '../contracts/labels'
import { splitDateTime } from '../state/resultModel'
import { CandidateCard } from '../components/CandidateCard'
import { FrameSlot } from '../components/FrameSlot'
import { StatusBadge } from '../components/StatusBadge'
import { CandidatesScreen } from './CandidatesScreen'
import { EvidenceScreen } from './EvidenceScreen'
import { SituationInput } from './UploadScreen'

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

// 사용자 입력 번호판 형식(#487) — evidence 서버 검증과 맞출 규칙. 범위가 확정되면 여기만 고친다.
const PLATE_FORMAT = /^([가-힣]{2})?\d{2,3}[가-힣]\d{4}$/

// 03_Sub_Plate_Check — 번호판을 읽은 장면과 번호판 확대를 나란히 두고, 여기서 번호를 고친다.
// 장면은 번호판을 읽은 frame(evidence.plate_preview_ref)이다. preview_ref는 사건 대표 썸네일이라 쓰지 않는다(#47 · #446).
// 값이 없으면(null) 자리만 둔다. 번호판 확대는 자를 위치(bbox)가 CaseView에 없어 아직 자리만 둔다.
// 수정은 읽은 값을 채운 채 열어 틀린 글자만 고치게 한다.
//   저장 — 고친 값이 사건의 번호판이 된다(사용자 확인됨). 결과·자세히 보기를 오가도 유지된다.
//   취소·Esc·뒤로 — 고치던 글자만 버리고, 마지막으로 저장한 값(없으면 읽은 값)을 그대로 둔다.
// aiValue는 번호판 판독이 읽은 값이다. 사용자가 고친 값과 다르면 함께 보여 무엇을 바꿨는지 알 수 있게 한다.
// 시연은 화면 안에서만 반영하고, `?api`는 `MANUAL_PLATE_INPUT` command로 보낸다(#449).
// `onEdit`이 없으면 수정 버튼을 두지 않는다.
export function PlateCheck(props: {
  view: CaseView
  aiValue?: string | null
  /** 「번호판 직접 입력」 notice 동작으로 열면 바로 고치는 칸을 연다 */
  startEditing?: boolean
  onBack: () => void
  onEdit?: (plate: string) => void
  /** FrameRef를 이미지 주소로 바꾼다(API 모드). 없으면(시연) 자리 표시만 둔다 */
  frameSrc?: (frameRef: string) => string
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
  const frame = (ref: string | null | undefined) => (ref && props.frameSrc ? props.frameSrc(ref) : null)
  const src = sourceLabel(plate.source_label_key)
  const edited = plate.info_state === 'INFO_USER_CONFIRMED' && props.aiValue !== undefined && props.aiValue !== plate.value
  // 안쪽 공백은 지우고 받는다(`12가 3456` → `12가3456`). 형식이 틀리면 저장을 막고 칸 아래에 알린다.
  const plateInput = (editing ?? '').replace(/\s/g, '')
  const plateOk = PLATE_FORMAT.test(plateInput)
  const plateWrong = plateInput !== '' && !plateOk
  // 도는 job이 없으면 이미지는 더 오지 않는다(번호판을 못 읽으면 plate_preview_ref는 null로 끝난다) — 「준비 중」이라 하지 않는다
  const pending = props.view.running_jobs.length > 0
  return (
    <SubPage title="번호판 확인" onBack={props.onBack} className="plate-page">
      <div className="plate-grid">
        <figure className="plate-fig plate-scene">
          <FrameSlot className="plate-frame" src={frame(evidence.plate_preview_ref)} alt="번호판을 읽은 장면">
            <Film size={26} strokeWidth={1.5} aria-hidden />
            <span>{pending ? '장면 이미지 준비 중' : '장면 이미지가 없어요'}</span>
          </FrameSlot>
          <figcaption>번호판을 읽은 장면</figcaption>
        </figure>
        <div className="plate-side">
          <figure className="plate-fig">
            <div className="plate-frame plate-crop">
              <Film size={24} strokeWidth={1.5} aria-hidden />
              <span>{pending ? '번호판 이미지 준비 중' : '번호판 이미지가 없어요'}</span>
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
                {props.onEdit && (
                  <button
                    type="button"
                    ref={editButton}
                    className="rs-btn sec"
                    onClick={() => setEditing(plate.value ?? '')}
                  >
                    번호 수정
                  </button>
                )}
              </>
            ) : (
              <form
                className="plate-form"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (!plateOk) return
                  props.onEdit?.(plateInput)
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
                  aria-invalid={plateWrong}
                  aria-describedby="plate-format"
                />
                <span className="rs-hint" id="plate-format">
                  {plateWrong ? '번호판 형식을 확인해 주세요 (예: 12가3456)' : '예: 12가3456'}
                </span>
                <div className="plate-form-actions">
                  <button type="submit" className="rs-btn pri" disabled={!plateOk}>
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

// 발생 시각 직접 입력(#449) — 결과 화면 발생 시간의 「시각 입력하기 · 수정하기」나 notice의 `시각 직접 입력`으로 연다.
// 입력칸은 날짜 · 시간만 받고, 계약이 오프셋이 있는 RFC3339를 요구해 한국 시간(+09:00)을 붙여 보낸다.
export function TimeEdit(props: { view: CaseView; onBack: () => void; onSave: (value: string) => void }): JSX.Element {
  const shown = splitDateTime(props.view.evidence?.event_time_display.value ?? null)
  const [date, setDate] = useState(shown.date ?? '')
  const [time, setTime] = useState(shown.time ?? '')
  return (
    <SubPage title="발생 시각" onBack={props.onBack} className="time-page">
      <form
        className="rs-group"
        onSubmit={(e) => {
          e.preventDefault()
          if (date && time) props.onSave(`${date}T${time.length === 5 ? `${time}:00` : time}+09:00`)
        }}
      >
        <label className="rs-field">
          <span className="rs-label">날짜</span>
          <input type="date" className="field" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="rs-field">
          <span className="rs-label">시간</span>
          <input type="time" step={1} className="field" value={time} onChange={(e) => setTime(e.target.value)} />
        </label>
        <span className="rs-hint">한국 시간 기준으로 저장해요.</span>
        <div className="rs-actions">
          <button type="submit" className="rs-btn pri" disabled={!date || !time}>
            저장
          </button>
          <button type="button" className="rs-btn sec" onClick={props.onBack}>
            취소
          </button>
        </div>
      </form>
    </SubPage>
  )
}

// 설명 고쳐 다시 찾기(#410) — notice가 `EDIT_HINT`를 실었을 때 연다. 분석 시작과 같은 원문 입력이고
// 이전 설명(`CaseView.description`)을 미리 채운다. 보내면 case가 단서 정리부터 다시 돈다(`EDIT_HINT` command).
// 「고친 내용으로 찾기」를 앞에 두고 강조, 「처음으로」는 약하게 — 언제나 그리는 고정 출구다(서버 action이 아니다).
export function EditHint(props: {
  view: CaseView
  onBack: () => void
  onSearch: (description: string) => void
  onHome: () => void
}): JSX.Element {
  return (
    <SubPage title="설명 고치기" onBack={props.onBack} className="hint-page">
      <HintForm view={props.view} onSearch={props.onSearch} onHome={props.onHome} />
    </SubPage>
  )
}

// 설명 입력 폼만 — 위반 미관찰에 다른 후보가 없으면 화면 안에 바로 둔다(#431)
export function HintForm(props: { view: CaseView; onSearch: (description: string) => void; onHome: () => void }): JSX.Element {
  const [text, setText] = useState(props.view.description ?? '')
  return (
    <form
      className="rs-group"
      onSubmit={(e) => {
        e.preventDefault()
        if (text.trim()) props.onSearch(text.trim())
      }}
    >
      <label className="rs-field">
        <span className="rs-label">어떤 상황이었나요?</span>
        <SituationInput
          label="어떤 상황이었나요?"
          example="아침 7시쯤이었던 것 같아요. 검은 승용차가 중앙선을 넘어 제 쪽으로 들어왔어요."
          rows={4}
          value={text}
          onChange={setText}
        />
        <span className="rs-hint">시간이나 차 색깔, 어떤 일이 있었는지를 떠오르는 대로 고쳐 주세요.</span>
      </label>
      <div className="rs-actions">
        {/* 비어 있으면 보내지 않는다(#410 web 의견) — 서버는 빈 설명도 받지만 web에서 그 경로는 쓰지 않는다 */}
        <button type="submit" className="rs-btn pri" disabled={!text.trim()}>
          고친 내용으로 찾기
        </button>
        <button type="button" className="rs-btn sec" onClick={props.onHome}>
          처음으로
        </button>
      </div>
    </form>
  )
}
