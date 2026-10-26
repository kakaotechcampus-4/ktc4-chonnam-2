import { useEffect, useRef, useState, type JSX, type ReactNode } from 'react'
import { ChevronRight, CircleAlert, Download, ExternalLink, Film, Info } from 'lucide-react'
import {
  isAction,
  type Action,
  type CaseView,
  type InfoState,
  type Notice,
} from '../contracts/caseView'
import { ACTION_LABELS, INFO_STATE_LABELS, formatValue, jobLabel, noticeMessage, sourceLabel } from '../contracts/labels'
import { PREVIEW_UNAVAILABLE } from '../contracts/labels.flow'
import { PENDING_TEXT } from '../components/DisplayRow'
import { StatusBadge } from '../components/StatusBadge'
import { ArrivingCar } from '../components/ArrivingCar'
import { reportVideoState, splitDateTime } from '../state/resultModel'

// 03_Main_Result — 위에 전체 준비 상태, 아래는 안전신문고 신고 양식 순서
// (유형 → 동영상 → 위치 선택 → 제목 → 신고 내용 → 차량 번호 → 발생 일자 → 발생 시간), 마지막에 복사와 이동.
// 값과 상태는 계약 대응표 그대로다(case-view §report_fields ↔ evidence.*_display) — package가 있으면
// report_fields·report_field_states를, 없으면(판독 실패 등) 같은 출처인 evidence.*_display를 읽는다.
// 복사·이동은 package가 있을 때만 연다(COPY_FIELDS·OPEN_DESTINATION).
// 제출 단계로의 연결은 READY(= PACKAGE_READY)이고 blocking notice가 없을 때만 연다(#171 C, #172).
// 안전신문고는 새 창으로 연다 — 이 화면을 옆에 두고 보며 직접 제출한다(§21). 자료를 보내거나 자동으로
// 채우지 않는다. 대신고에는 접수 버튼이 없다.
const SAFETY_REPORT_URL = 'https://www.safetyreport.go.kr/'
const COPIED = '복사했습니다'
const COPY_FAILED = '복사하지 못했어요. 값을 직접 선택해 복사해 주세요.'
const TOAST_MS = 3000
// 아래 문구는 검토 대기 중인 새 문구다(보고서 「검토할 문구」).
// 붙여넣지 않고 안전신문고에서 사용자가 고르는 칸(유형·위치·발생 일시) 표시
const PICK_MARK = '직접 선택'
const NO_TITLE = '대신고가 아직 제목을 만들어 주지 않아요. 안전신문고에서 직접 적어 주세요.'
const ACTION_UNAVAILABLE = '아직 이 화면에서 할 수 없어요'
const VIDEO_STATUS: Record<ReturnType<typeof reportVideoState>, string> = {
  none: '신고용 영상이 아직 없어요',
  preparing: jobLabel('job.report_video_export'),
  failed: '신고용 영상을 만들지 못했어요',
  unlinked: '영상 파일을 내려받는 연결이 아직 준비되지 않았어요',
}
const VIDEO_CAPTION = '신고용 영상 · 원본에서 사건 구간만 잘라 만든 영상이에요'
const COPY_ALL_NOTE = '칸 이름과 함께 제목·차량 번호·신고 내용을 복사해요. 영상 첨부와 위치 선택은 안전신문고에서 직접 해 주세요.'
// 번호판 확인 화면에서 번호를 고칠 수 있다는 것을 결과 화면에서 미리 알린다(10/23 승인 문구)
const PLATE_EDIT_LINK = '확인·수정하기'
const PLATE_EDIT_WHY = '번호가 틀렸다면 여기서 고칠 수 있어요'
const LOCAL_EDIT_NOTE = '이 화면에서만 바꿨어요. 서버에는 아직 저장되지 않아요.'
const KEYWORD_MISSING = 'evidence.location_search_keyword_missing'

const COUNT_ORDER: InfoState[] = [
  'INFO_NEEDS_REVIEW',
  'INFO_UNKNOWN',
  'INFO_AI_ESTIMATED',
  'INFO_SOURCE_VERIFIED',
  'INFO_USER_CONFIRMED',
]

// 빨강은 실패(ERROR)에만, 주황은 확인이 필요한 경고(WARN)에만 쓴다. 안내(INFO)는 기본 색이다.
function tone(n: Notice): 'fail' | 'review' | 'info' {
  return n.severity === 'ERROR' ? 'fail' : n.severity === 'WARN' ? 'review' : 'info'
}

interface Field {
  value: string | null
  state: InfoState
  source: string | null
}

export function ResultScreen(props: {
  view: CaseView
  onCandidates: () => void
  onPlate: () => void
  onDetails: () => void
  onAction: (noticeCode: string, action: Action) => void
  /** 지금 연결된 notice 동작인가 — 아니면 버튼을 사용 불가로 두고 이유를 적는다 */
  canRun: (action: Action) => boolean
  /** 번호판을 이 화면에서만 고쳤는가(서버 저장 아님) */
  plateEditedLocally?: boolean
  /** 진행에서 막 넘어왔는가 — 첫 화면의 배경 자동차가 오른쪽에서 들어와 멈춘다. 하위 화면에서 돌아올 때는 제자리 */
  arriving?: boolean
  /** 신고 상황 응답. RECORD_SITUATION_RESPONSE가 받는 두 값만 둔다 — 「다른 상황」은 입력형이라 command가 아직 없다 */
  onRespond?: (value: 'CONFIRMED' | 'USER_UNSURE') => void
}): JSX.Element {
  const { view } = props
  const pkg = view.package
  const ev = view.evidence
  // 신고 상황은 결과 화면에서 묻는다(core-user-flow §20, #171 B-2). 응답 전에는 묶음이 없다.
  const selected = view.candidates.find((c) => c.selected)
  const awaiting =
    selected?.situation_confirmation === 'NOT_ASKED' &&
    view.notices.some((n) => n.code === 'case.situation_response_pending')
  // 응답 전 부분 투영(v1.8, evidence.record_id null) — 상황 따라 정해지는 값은 응답 뒤에 정해진다
  const partial = !pkg && ev?.record_id === null

  // 계약 대응표: report_fields 키 ↔ evidence.*_display. package가 없으면 evidence 쪽을 읽는다.
  const field = (key: string, fromEvidence: () => Field | null): Field | null => {
    if (pkg) {
      const st = pkg.report_field_states[key]
      return {
        value: pkg.report_fields[key] ?? null,
        state: st?.info_state ?? 'INFO_UNKNOWN',
        source: sourceLabel(st?.source_label_key ?? null),
      }
    }
    return fromEvidence()
  }
  const reportType = field('safety_report_type', () =>
    ev ? { value: ev.report_type_display.label, state: ev.report_type_display.info_state, source: sourceLabel(ev.report_type_display.source_label_key) } : null,
  )
  const location = field('location', () =>
    ev ? { value: ev.location_display.value, state: ev.location_display.info_state, source: sourceLabel(ev.location_display.source_label_key) } : null,
  )
  const content = field('violation_expression', () =>
    ev ? { value: ev.violation_display.label, state: ev.violation_display.info_state, source: sourceLabel(ev.violation_display.source_label_key) } : null,
  )
  const plate = field('vehicle_number', () =>
    ev ? { value: ev.plate_display.value, state: ev.plate_display.info_state, source: sourceLabel(ev.plate_display.source_label_key) } : null,
  )
  const occurred = field('occurred_at', () =>
    ev ? { value: ev.event_time_display.value, state: ev.event_time_display.info_state, source: sourceLabel(ev.event_time_display.source_label_key) } : null,
  )
  const when = splitDateTime(occurred?.value ?? null)
  // 제목·신고 내용은 case가 만든 신고문(package.report, v1.7)을 그대로 보여 주고 복사만 한다.
  // 계약상 package가 있으면 report도 항상 있다. 옛 판본 응답이 와도 깨지지 않게 없으면 예전처럼 둔다.
  const report = pkg?.report ?? null
  const keyword = ev?.location_display.search_keyword ?? null
  const hasForm = Boolean(pkg || ev)
  // 검색어를 못 만들었다는 안내는 위치 칸에 붙는 말이라 위 목록이 아니라 검색어 자리에 둔다
  // (버튼 없는 INFO라 옮겨도 잃는 것이 없다). 위치 칸이 없으면 위 목록에 남긴다.
  const keywordMissing = hasForm ? view.notices.find((n) => n.code === KEYWORD_MISSING) : undefined
  const headNotices = keywordMissing ? view.notices.filter((n) => n !== keywordMissing) : view.notices

  const counts = new Map<InfoState, number>()
  for (const s of Object.values(pkg?.report_field_states ?? {})) counts.set(s.info_state, (counts.get(s.info_state) ?? 0) + 1)
  const others = view.candidates.filter((c) => !c.selected).length
  const ready = view.stage === 'READY' && !!pkg && !view.notices.some((n) => n.blocking)
  const canCopy = !!pkg?.capabilities.includes('COPY_FIELDS')
  const video = reportVideoState(view)
  // 붙여넣을 것(§21: 제목·차량번호·신고 내용) 중 지금 값이 있는 것만, 칸 이름을 붙여 복사한다.
  const pasteText = [
    ['제목', report?.title],
    ['차량 번호', plate?.value],
    ['신고 내용', report?.description ?? content?.value],
  ]
    .filter(([, v]) => v)
    .map(([k, v]) => `${k}: ${formatValue(v!)}`)
    .join('\n')

  const [toast, setToast] = useState<{ text: string; id: number } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])
  const copy = (text: string) => {
    const done = (ok: boolean) => {
      setToast({ text: ok ? COPIED : COPY_FAILED, id: Date.now() })
      clearTimeout(timer.current)
      timer.current = setTimeout(() => setToast(null), TOAST_MS)
    }
    if (!navigator.clipboard) return done(false)
    navigator.clipboard.writeText(text).then(
      () => done(true),
      () => done(false),
    )
  }
  const copyButton = (label: string, value: string | null | undefined) =>
    canCopy && (
      <button
        type="button"
        className="rs-btn sec sm"
        disabled={!value}
        aria-label={`${label} 복사`}
        onClick={() => value && copy(formatValue(value))}
      >
        복사
      </button>
    )

  return (
    <div className="rs rs-screen result">
      <header className="res-head">
        <ArrivingCar arriving={props.arriving} />
        <p className="state-context">신고자료</p>
        <h1 className="res-title">{ready ? '신고자료가 준비됐어요.' : awaiting ? '신고 상황을 확인해 주세요.' : '신고자료를 완성하지 못했어요.'}</h1>
        {counts.size > 0 && (
          <ul className="res-counts">
            {COUNT_ORDER.filter((s) => counts.has(s)).map((s) => (
              <li key={s} className={`res-count is-${s.toLowerCase()}`}>
                <span className="res-dot" aria-hidden />
                {INFO_STATE_LABELS[s]} <b>{counts.get(s)}</b>
              </li>
            ))}
          </ul>
        )}
        {headNotices.length > 0 && (
          <ul className="res-notices">
            {headNotices.map((n) => {
              const t = tone(n)
              const Icon = t === 'info' ? Info : CircleAlert
              return (
                <li key={n.code} className={`res-notice is-${t}`}>
                  <Icon size={18} strokeWidth={1.8} aria-hidden />
                  <span className="res-notice-text">{noticeMessage(n.message_key)}</span>
                  {/* notice가 실은 actions[]만 버튼으로 연다 — 계약 밖 버튼은 만들지 않는다.
                      연결되지 않은 동작은 눌러도 아무 일이 없게 두지 않고, 사용 불가와 이유를 보인다 */}
                  {n.actions.filter(isAction).map((a) =>
                    props.canRun(a) ? (
                      <button key={a} type="button" className="rs-btn pri sm" onClick={() => props.onAction(n.code, a)}>
                        {ACTION_LABELS[a]}
                      </button>
                    ) : (
                      <span key={a} className="res-action-off">
                        <button type="button" className="rs-btn sec sm" disabled aria-describedby={`off-${n.code}-${a}`}>
                          {ACTION_LABELS[a]}
                        </button>
                        <span id={`off-${n.code}-${a}`} className="res-off-why">
                          {ACTION_UNAVAILABLE}
                        </span>
                      </span>
                    ),
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </header>

      {awaiting && selected && props.onRespond && (
        <section className="res-situation" aria-labelledby="res-situation-h">
          <div className="res-sec-head">
            <h2 id="res-situation-h">신고 상황</h2>
          </div>
          <p className="res-situation-text">
            이 사건을 이렇게 정리했어요. <b>“{selected.observed}”</b>
          </p>
          {/* 근거 장면은 FrameRef로만 와서 아직 그릴 수 없다(#47) — 자리만 둔다 */}
          <div className="res-frame">
            <Film size={26} strokeWidth={1.5} aria-hidden />
            <span>근거 장면 준비 중</span>
          </div>
          {/* 상황에 따라 정해지는 값 셋(#171)만 응답 뒤로 미룬다. 나머지(번호판·시각·위치)는 그대로 둔다 */}
          <ul className="res-pending">
            {['사건 유형', '신고 유형', '위반 내용'].map((label) => (
              <li key={label}>
                <span className="res-pending-k">{label}</span>
                <span className="res-val is-none">{PENDING_TEXT}</span>
              </li>
            ))}
          </ul>
          {/* 「잘 모르겠어요」도 진행을 막지 않는다. 값은 AI 추정으로 남는다(core-user-flow 「신고 상황」) */}
          <div className="res-actions">
            <button type="button" className="rs-btn pri" onClick={() => props.onRespond!('CONFIRMED')}>
              맞아요
            </button>
            <button type="button" className="rs-btn sec" onClick={() => props.onRespond!('USER_UNSURE')}>
              잘 모르겠어요
            </button>
          </div>
          {/* 응답 전에는 영상 칸이 없으니 다른 후보 입구를 여기에 둔다(§20 묶음 전) */}
          {others > 0 && (
            <button type="button" className="res-link" onClick={props.onCandidates}>
              다른 장면이었나요? 다른 후보 {others}
              <ChevronRight size={16} strokeWidth={2} aria-hidden />
            </button>
          )}
        </section>
      )}

      {hasForm && (
        <section className="res-form" aria-labelledby="res-form-h">
          <div className="res-sec-head">
            <h2 id="res-form-h">안전신문고 신고서 초안</h2>
            {ev && (
              <button type="button" className="res-link" onClick={props.onDetails}>
                어떻게 정했는지
                <ChevronRight size={16} strokeWidth={2} aria-hidden />
              </button>
            )}
          </div>

          <Item label="유형" review={reportType?.state} pick>
            <Value f={reportType} pending={partial} />
          </Item>

          {/* 신고용 영상은 응답 뒤 조립에서 만들어진다. 응답 전(v1.8 부분 투영 포함)에는 영상 칸을 그리지 않는다.
              다른 후보 입구는 위 「신고 상황」에 이미 있다 */}
          {!awaiting && (
            <Item label="동영상">
              <div className="res-video">
                {/* 미리보기와 다운로드는 따로 판단한다 — 둘 다 아직 파일로 받을 경로가 없다 */}
                <div className="res-frame">
                  <Film size={26} strokeWidth={1.5} aria-hidden />
                  <span>{video === 'unlinked' ? PREVIEW_UNAVAILABLE : VIDEO_STATUS[video]}</span>
                </div>
                <div className="res-video-side">
                  {video === 'unlinked' && <p className="res-video-cap">{VIDEO_CAPTION}</p>}
                  <button type="button" className="rs-btn sec sm" disabled aria-describedby="res-video-why">
                    <Download size={16} strokeWidth={2} aria-hidden />
                    신고용 영상 다운로드
                  </button>
                  <p id="res-video-why" className={`res-hint${video === 'failed' ? ' is-fail' : ''}`}>
                    {VIDEO_STATUS[video]}
                  </p>
                  {others > 0 && (
                    <button type="button" className="res-link" onClick={props.onCandidates}>
                      다른 후보 영상 {others}
                      <ChevronRight size={16} strokeWidth={2} aria-hidden />
                    </button>
                  )}
                </div>
              </div>
            </Item>
          )}

          <Item label="위치 선택" review={location?.state} pick>
            <Value f={location} />
            {keyword && (
              <p className="res-keyword">
                <span className="res-keyword-k">검색어</span>
                <span className="res-keyword-v">{keyword}</span>
                {canCopy && (
                  <button type="button" className="rs-btn sec sm" aria-label="검색어 복사" onClick={() => copy(keyword)}>
                    복사
                  </button>
                )}
              </p>
            )}
            {!keyword && keywordMissing && (
              <p className="res-keyword-missing">
                <Info size={15} strokeWidth={1.8} aria-hidden />
                <span>{noticeMessage(keywordMissing.message_key)}</span>
              </p>
            )}
          </Item>

          <Item label="제목">
            {report ? (
              <span className="res-val-line">
                <span className="res-val">{report.title}</span>
                {copyButton('제목', report.title)}
              </span>
            ) : (
              <p className="res-missing">{NO_TITLE}</p>
            )}
          </Item>

          {report ? (
            <Item label="신고 내용">
              <span className="res-report">
                <span className="res-val res-report-text">{report.description}</span>
                {copyButton('신고 내용', report.description)}
              </span>
            </Item>
          ) : (
            <Item label="신고 내용" review={content?.state}>
              <Value f={content} pending={partial} after={copyButton('신고 내용', content?.value)} />
            </Item>
          )}

          <Item label="차량 번호" review={plate?.state}>
            <div className="res-plate">
              <p className={`res-plate-v${plate?.value ? '' : ' is-none'}`}>{plate?.value ?? '알 수 없음'}</p>
              <div className="res-plate-meta">
                {plate && <StatusBadge state={plate.state} />}
                {plate?.source && <span className="res-src">{plate.source}</span>}
                {copyButton('차량 번호', plate?.value)}
              </div>
              {props.plateEditedLocally && <p className="res-hint">{LOCAL_EDIT_NOTE}</p>}
              {ev && (
                <p className="res-plate-edit">
                  <button type="button" className="res-link" onClick={props.onPlate} aria-describedby="res-plate-edit-why">
                    {PLATE_EDIT_LINK}
                    <ChevronRight size={16} strokeWidth={2} aria-hidden />
                  </button>
                  <span id="res-plate-edit-why" className="res-src">
                    {PLATE_EDIT_WHY}
                  </span>
                </p>
              )}
            </div>
          </Item>

          <Item label="발생 일자" review={occurred?.state} pick>
            <Value f={occurred && { ...occurred, value: when.date }} />
          </Item>

          <Item label="발생 시간" review={occurred?.state} pick>
            <Value f={occurred && { ...occurred, value: when.time }} />
          </Item>
        </section>
      )}

      <section className="res-handoff">
        <p className="res-disclaimer">
          대신고는 신고를 <b>대신 접수하지 않습니다.</b> 자료를 받아 안전신문고에서 내용을 다시 확인하고 직접
          제출하셔야 합니다.
        </p>
        {pkg && (
          <div className="res-actions">
            {canCopy && (
              <button
                type="button"
                className="rs-btn sec"
                disabled={!ready || !pasteText}
                aria-describedby="res-copy-all-note"
                onClick={() => copy(pasteText)}
              >
                붙여넣을 내용 전체 복사
              </button>
            )}
            {pkg.capabilities.includes('OPEN_DESTINATION') && (
              <button
                type="button"
                className="rs-btn pri"
                disabled={!ready}
                onClick={() => window.open(SAFETY_REPORT_URL, '_blank', 'noopener')}
              >
                안전신문고로 이동
                <ExternalLink size={16} strokeWidth={2} aria-hidden />
                <span className="sr-only">(새 창)</span>
              </button>
            )}
          </div>
        )}
        {pkg && canCopy && (
          <p id="res-copy-all-note" className="res-block-note">
            {COPY_ALL_NOTE}
          </p>
        )}
        {pkg && !ready && <p className="res-block-note">위 문제가 해결돼야 안전신문고로 넘어갈 수 있어요.</p>}
        <p className="res-toast" role="status" aria-live="polite">
          {toast && <span key={toast.id}>{toast.text}</span>}
        </p>
      </section>
    </div>
  )
}

// 양식 한 칸 — 왼쪽 칸 이름, 오른쪽 값. 확인이 필요한 칸만 주황 바탕이다.
// pick: 안전신문고에서 사용자가 직접 고르는 칸(붙여넣지 않음) — 칸 이름 아래에 작게 적는다.
function Item(props: { label: string; review?: InfoState; pick?: boolean; children: ReactNode }): JSX.Element {
  return (
    <div className={`res-item${props.review === 'INFO_NEEDS_REVIEW' ? ' is-review' : ''}`}>
      <div className="res-item-kbox">
        <h3 className="res-item-k">{props.label}</h3>
        {props.pick && <p className="res-item-pick">{PICK_MARK}</p>}
      </div>
      <div className="res-item-v">{props.children}</div>
    </div>
  )
}

// 값 — 바로 옆에 상태 배지(와 복사 버튼), 아래에 출처. 값이 없으면 「알 수 없음」이다(§3-3).
// pending: 응답 전 부분 투영에서 상황 따라 정해지는 값 — 「알 수 없음」이 아니라 응답 뒤에 정해진다.
function Value(props: { f: Field | null; pending?: boolean; after?: ReactNode }): JSX.Element {
  const f = props.f
  if (props.pending)
    return (
      <span className="res-val-line">
        <span className="res-val is-none">{PENDING_TEXT}</span>
      </span>
    )
  return (
    <>
      <span className="res-val-line">
        <span className={`res-val${f?.value ? '' : ' is-none'}`}>{f?.value ? formatValue(f.value) : '알 수 없음'}</span>
        <StatusBadge state={f?.state ?? 'INFO_UNKNOWN'} />
        {props.after}
      </span>
      {f?.source && <span className="res-src">{f.source}</span>}
    </>
  )
}
