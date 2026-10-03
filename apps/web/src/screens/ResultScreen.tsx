import { useEffect, useRef, useState, type JSX } from 'react'
import { ChevronRight, CircleAlert, ExternalLink, Film, Info } from 'lucide-react'
import { isAction, type Action, type CaseView, type InfoState, type Notice } from '../contracts/caseView'
import {
  ACTION_LABELS,
  INFO_STATE_LABELS,
  formatValue,
  noticeMessage,
  reportFieldLabel,
  sourceLabel,
} from '../contracts/labels'
import { PREVIEW_UNAVAILABLE } from '../contracts/labels.flow'
import { StatusBadge } from '../components/StatusBadge'

// Figma 03_Main_Result 틀: 요약 → 신고용 영상(+다른 후보) → 번호판 → 신고서 초안(+어떻게 정했는지) → 동작.
// 값과 상태는 package.report_field_states를 그대로 쓴다(value-state-display.md §5-1).
// 무엇이 잘 됐든 안 됐든 결과는 여기서 알린다 — 진행 화면은 멈추지 않는다.
// 제출 단계로의 연결은 READY(= PACKAGE_READY)이고 blocking notice가 없을 때만 연다(#171 C, #172).
// 실패해도 package·evidence가 없을 수 있다(판독 실패·상황 응답 대기). 그래도 notice와
// 다시 시도는 보여야 하므로, 요약은 항상 그리고 나머지는 있는 것만 그린다.
// ponytail: 위치는 지도·검색어 복사 없이 초안 행만 둔다. 붙여넣을 칸이 아니라 직접 고른다.
// 안전신문고 칸 중 붙여넣을 수 있는 것만 복사 버튼을 둔다. 나머지는 거기서 직접 고른다(core-user-flow §21).
// 「제목」 칸은 report_fields에 아직 없다.
const PASTE = new Set(['vehicle_number', 'violation_expression'])
// 안전신문고는 새 창으로 연다 — 이 화면을 옆에 두고 보며 직접 제출한다(§21, PROTOTYPE-SPEC §6).
// 제출은 사용자가 거기서 한다. 대신고에는 접수 버튼이 없다.
const SAFETY_REPORT_URL = 'https://www.safetyreport.go.kr/'
const COPIED = '복사했습니다'
const COPY_FAILED = '복사하지 못했어요. 값을 직접 선택해 복사해 주세요.'
const TOAST_MS = 2000

// 요약 개수는 확인이 필요한 것부터 — 사용자가 손볼 것이 먼저 보이게. 판정은 하지 않고 셀 뿐이다.
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

export function ResultScreen(props: {
  view: CaseView
  onCandidates: () => void
  onPlate: () => void
  onDetails: () => void
  onAction: (noticeCode: string, action: Action) => void
}): JSX.Element {
  const { view } = props
  const pkg = view.package
  const evidence = view.evidence

  const counts = new Map<InfoState, number>()
  const fields = pkg ? Object.entries(pkg.report_fields) : []
  for (const s of Object.values(pkg?.report_field_states ?? {})) {
    counts.set(s.info_state, (counts.get(s.info_state) ?? 0) + 1)
  }
  const others = view.candidates.filter((c) => !c.selected).length
  const ready = view.stage === 'READY' && !view.notices.some((n) => n.blocking)
  const noVideo = view.notices.some((n) => n.code === 'case.report_video_not_generated')
  const pasteText = fields
    .filter(([key, value]) => PASTE.has(key) && value)
    .map(([key, value]) => `${reportFieldLabel(key)}: ${formatValue(value!)}`)
    .join('\n')

  // 복사 결과는 한 줄 상태로 알린다(화면 읽기 프로그램도 읽음). 버튼 이름은 바꾸지 않는다.
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

  return (
    <div className="rs rs-screen result">
      <header className="res-head">
        <p className="state-context">신고자료</p>
        <h1 className="res-title">{ready ? '신고자료가 준비됐어요.' : '신고자료를 완성하지 못했어요.'}</h1>
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
        {view.notices.length > 0 && (
          <ul className="res-notices">
            {view.notices.map((n) => {
              const t = tone(n)
              const Icon = t === 'info' ? Info : CircleAlert
              return (
                <li key={n.code} className={`res-notice is-${t}`}>
                  <Icon size={18} strokeWidth={1.8} aria-hidden />
                  <span className="res-notice-text">{noticeMessage(n.message_key)}</span>
                  {/* notice가 실은 actions[]만 버튼으로 연다 — 계약 밖 버튼은 만들지 않는다 */}
                  {n.actions.filter(isAction).map((a) => (
                    <button key={a} type="button" className="rs-btn pri sm" onClick={() => props.onAction(n.code, a)}>
                      {ACTION_LABELS[a]}
                    </button>
                  ))}
                </li>
              )
            })}
          </ul>
        )}
      </header>

      {evidence && (
        <div className="res-top">
          <section className="res-video" aria-label="신고용 영상">
            {/* 신고용 영상은 계약상 참조(artifact_ref)로만 와서 아직 재생할 수 없다 — 재생 표시를 두지 않는다 */}
            <div className="res-frame">
              <Film size={28} strokeWidth={1.5} aria-hidden />
              <span>{noVideo ? '신고용 영상이 아직 없어요' : PREVIEW_UNAVAILABLE}</span>
            </div>
            <div className="res-frame-cap">
              <span>{noVideo ? '신고용 영상' : '신고용 영상 · 원본에서 사건 구간만 잘라 만든 영상이에요'}</span>
              {others > 0 && (
                <button type="button" className="rs-btn sec sm" onClick={props.onCandidates}>
                  다른 후보 영상 {others}
                  <ChevronRight size={16} strokeWidth={2} aria-hidden />
                </button>
              )}
            </div>
          </section>

          <section className="res-plate" aria-labelledby="res-plate-k">
            <h2 className="res-k" id="res-plate-k">
              번호판
            </h2>
            <p className={`res-plate-v${evidence.plate_display.value === null ? ' is-none' : ''}`}>
              {evidence.plate_display.value ?? '번호판 없음'}
            </p>
            <div className="res-plate-meta">
              <StatusBadge state={evidence.plate_display.info_state} />
              {sourceLabel(evidence.plate_display.source_label_key) && (
                <span className="res-src">{sourceLabel(evidence.plate_display.source_label_key)}</span>
              )}
            </div>
            <button type="button" className="rs-btn sec" onClick={props.onPlate}>
              자세히 보기
            </button>
          </section>
        </div>
      )}

      {pkg && (
        <section className="res-draft" aria-labelledby="res-draft-h">
          <div className="res-sec-head">
            <h2 id="res-draft-h">안전신문고 신고서 초안</h2>
            <button type="button" className="res-link" onClick={props.onDetails}>
              어떻게 정했는지
              <ChevronRight size={16} strokeWidth={2} aria-hidden />
            </button>
          </div>
          <div className="res-rows">
            {fields.map(([key, value]) => {
              const st = pkg.report_field_states[key]
              const src = st ? sourceLabel(st.source_label_key) : null
              return (
                <div className={`res-row${st?.info_state === 'INFO_NEEDS_REVIEW' ? ' is-review' : ''}`} key={key}>
                  <span className="res-row-k">{reportFieldLabel(key)}</span>
                  <span className="res-row-v">
                    <span className="res-val-line">
                      <span className={`res-val${value === null ? ' is-none' : ''}`}>
                        {value === null ? '알 수 없음' : formatValue(value)}
                      </span>
                      {st && <StatusBadge state={st.info_state} />}
                    </span>
                    {src && <span className="res-src">{src}</span>}
                  </span>
                  <span className="res-row-act">
                    {PASTE.has(key) ? (
                      <button
                        type="button"
                        className="rs-btn sec sm"
                        disabled={value === null}
                        aria-label={`${reportFieldLabel(key)} 복사`}
                        onClick={() => value && copy(formatValue(value))}
                      >
                        복사
                      </button>
                    ) : (
                      <span className="res-pick">안전신문고에서 직접 골라요</span>
                    )}
                  </span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      <section className="res-handoff">
        <p className="res-disclaimer">
          대신고는 신고를 <b>대신 접수하지 않습니다.</b> 자료를 받아 안전신문고에서 내용을 다시 확인하고 직접
          제출하셔야 합니다.
        </p>
        {pkg && (
          <div className="res-actions">
            {pkg.capabilities.includes('COPY_FIELDS') && (
              // 전체 복사는 붙여넣을 칸만, 칸 이름을 붙여 복사한다(§21)
              <button type="button" className="rs-btn sec" disabled={!ready || !pasteText} onClick={() => copy(pasteText)}>
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
        {pkg && !ready && <p className="res-block-note">위 문제가 해결돼야 안전신문고로 넘어갈 수 있어요.</p>}
        <p className="res-toast" role="status" aria-live="polite">
          {toast && <span key={toast.id}>{toast.text}</span>}
        </p>
      </section>
    </div>
  )
}
