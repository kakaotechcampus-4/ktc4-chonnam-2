import type { JSX } from 'react'
import { isAction, type Action, type CaseView, type InfoState } from '../contracts/caseView'
import { ACTION_LABELS, INFO_STATE_LABELS, noticeMessage, reportFieldLabel } from '../contracts/labels'
import { StatusBadge } from '../components/StatusBadge'

// Figma 03_Main_Result 틀: 요약 → 신고용 영상(+다른 후보) → 번호판 → 신고서 초안(+어떻게 정했는지) → 동작.
// 값과 상태는 package.report_field_states를 그대로 쓴다(value-state-display.md §5-1).
// 무엇이 잘 됐든 안 됐든 결과는 여기서 알린다 — 진행 화면은 멈추지 않는다.
// blocking notice가 있으면(예: 번호판 판독 실행 실패, #172) 제출 단계로 넘기지 않는다.
// ponytail: 위치(지도·검색어 복사)는 아직 구현하지 못해 이 화면에서 뺀다. 구현되면 HIDDEN을 비운다.
const HIDDEN = new Set(['location'])
export function ResultScreen(props: {
  view: CaseView
  onCandidates: () => void
  onPlate: () => void
  onDetails: () => void
  onAction: (action: Action) => void
}): JSX.Element {
  const { view } = props
  const pkg = view.package
  const evidence = view.evidence
  if (!pkg || !evidence) return <div className="panel panel-p">아직 신고자료가 없습니다.</div>

  // 요약 칩은 상태별 개수를 셀 뿐 판정하지 않는다.
  const counts = new Map<InfoState, number>()
  const fields = Object.entries(pkg.report_fields).filter(([key]) => !HIDDEN.has(key))
  for (const [key, s] of Object.entries(pkg.report_field_states)) {
    if (!HIDDEN.has(key)) counts.set(s.info_state, (counts.get(s.info_state) ?? 0) + 1)
  }
  const others = view.candidates.filter((c) => !c.selected).length
  const blocking = view.notices.filter((n) => n.blocking)

  return (
    <div className="stack">
      <h1 className="page-title">신고자료</h1>

      <section className="panel panel-p">
        <h2 className="panel-t">{blocking.length > 0 ? '신고자료를 완성하지 못했어요.' : '신고자료가 준비됐어요.'}</h2>
        {view.notices.map((n) => (
          <div key={n.code} className={`flow-notice${n.blocking ? ' blocking' : ''}`} style={{ marginTop: 10 }}>
            {noticeMessage(n.message_key)}
            {/* notice가 실은 actions[]만 버튼으로 연다(예: RETRY_PLATE_READ) — 계약 밖 버튼은 만들지 않는다 */}
            {n.actions.filter(isAction).map((a) => (
              <button key={a} type="button" className="btn sm notice-action" onClick={() => props.onAction(a)}>
                {ACTION_LABELS[a]}
              </button>
            ))}
          </div>
        ))}
        <div className="chips">
          {[...counts].map(([state, n]) => (
            <span key={state} className="chip">
              {INFO_STATE_LABELS[state]} {n}
            </span>
          ))}
        </div>
      </section>

      <section className="panel panel-p stack">
        <div className="video-box">
          <div className="video-main">
            <span className="video-play" aria-hidden>
              ▶
            </span>
            <span className="video-cap mono">신고용 영상</span>
          </div>
          {others > 0 && (
            <button type="button" className="video-side" onClick={props.onCandidates}>
              다른 후보 영상 {others} →
            </button>
          )}
        </div>
        <div className="plate-row">
          <span className="plate-img">{evidence.plate_display.value ?? '번호판 없음'}</span>
          <span className="plate-meta">
            <b>번호판</b>
            <StatusBadge state={evidence.plate_display.info_state} />
          </span>
          <button type="button" className="btn sm" onClick={props.onPlate}>
            자세히 보기
          </button>
        </div>
      </section>

      <section className="panel panel-p">
        <div className="sec-label">
          안전신문고 신고서 초안
          <button type="button" className="link-btn" onClick={props.onDetails}>
            어떻게 정했는지 →
          </button>
        </div>
        <div className="kv kv-rows">
          {fields.map(([key, value]) => (
            <div className="kv-row" key={key}>
              <span className="kv-k">{reportFieldLabel(key)}</span>
              <span className="kv-v">
                <span className="kv-val">{value ?? '알 수 없음'}</span>
              </span>
              {pkg.report_field_states[key] && <StatusBadge state={pkg.report_field_states[key].info_state} />}
              {pkg.capabilities.includes('COPY_FIELDS') && (
                <button type="button" className="btn sm" onClick={() => value && navigator.clipboard?.writeText(value)}>
                  복사
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      <div className="btnrow center">
        {pkg.capabilities.includes('COPY_FIELDS') && (
          <button type="button" className="btn" disabled={blocking.length > 0}>
            전체 복사
          </button>
        )}
        {pkg.capabilities.includes('OPEN_DESTINATION') && (
          <button type="button" className="btn btn-blue" disabled={blocking.length > 0}>
            안전신문고로 이동
          </button>
        )}
      </div>
      {blocking.length > 0 && <p className="kv-src center-text">위 문제가 해결돼야 안전신문고로 넘어갈 수 있어요.</p>}

      <p className="disclaimer">
        대신고는 신고를 <b>대신 접수하지 않습니다.</b> 자료를 받아 안전신문고에서 내용을 다시 확인하고 직접
        제출하셔야 합니다.
      </p>
    </div>
  )
}
