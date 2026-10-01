import type { JSX } from 'react'
import type { CaseView, InfoState } from '../contracts/caseView'
import { INFO_STATE_LABELS, reportFieldLabel } from '../contracts/labels'
import { StatusBadge } from '../components/StatusBadge'

// Figma 03_Main_Result 틀: 요약 → 신고용 영상(+다른 후보) → 번호판·위치 → 신고서 초안 → 동작.
// 값과 상태는 package.report_field_states를 그대로 쓴다(value-state-display.md §5-1).
// ponytail: 위치(지도·검색어 복사)는 아직 구현하지 못해 이 화면에서 뺀다. 구현되면 HIDDEN을 비운다.
const HIDDEN = new Set(['location'])
export function ResultScreen(props: {
  view: CaseView
  onCandidates: () => void
  onPlate: () => void
  onDetails: () => void
}): JSX.Element {
  const { view } = props
  const pkg = view.package
  const evidence = view.evidence
  if (!pkg || !evidence) return <div className="panel panel-p">아직 신고자료가 없습니다.</div>

  // 요약 칩은 상태별 개수를 셀 뿐 판정하지 않는다.
  const counts = new Map<InfoState, number>()
  const fields = Object.entries(pkg.report_fields).filter(([key]) => !HIDDEN.has(key))
  const unconfirmed = pkg.unconfirmed_fields.filter((key) => !HIDDEN.has(key))
  for (const [key, s] of Object.entries(pkg.report_field_states)) if (!HIDDEN.has(key)) counts.set(s.info_state, (counts.get(s.info_state) ?? 0) + 1)
  const others = view.candidates.filter((c) => !c.selected).length

  return (
    <div className="stack">
      <h1 className="page-title">신고자료</h1>

      <section className="panel panel-p">
        <h2 className="panel-t">신고자료가 준비됐어요.</h2>
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
          <button type="button" className="video-side" onClick={props.onCandidates}>
            다른 후보 영상{others > 0 ? ` ${others}` : ''} →
          </button>
        </div>
        <div className="thumb-row">
          <button type="button" className="thumb" onClick={props.onPlate}>
            <span className="thumb-img plate">{evidence.plate_display.value ?? '번호판'}</span>
            <span className="thumb-cap">
              번호판 <StatusBadge state={evidence.plate_display.info_state} />
            </span>
          </button>
          <button type="button" className="thumb" onClick={props.onDetails}>
            <span className="thumb-img how">어떻게 정했는지</span>
            <span className="thumb-cap">값마다 출처와 근거 보기 →</span>
          </button>
        </div>
      </section>

      <section className="panel panel-p">
        <div className="sec-label">안전신문고 신고서 초안</div>
        <div className="kv kv-rows">
          {fields.map(([key, value]) => (
            <div className="kv-row" key={key}>
              <span className="kv-k">{reportFieldLabel(key)}</span>
              <span className="kv-v">
                <span className="kv-val">{value ?? '알 수 없음'}</span>
              </span>
              {pkg.capabilities.includes('COPY_FIELDS') && (
                <button type="button" className="btn sm" onClick={() => value && navigator.clipboard?.writeText(value)}>
                  복사
                </button>
              )}
            </div>
          ))}
        </div>
        {unconfirmed.length > 0 && (
          <div className="unconfirmed">
            <b>아직 확인하지 않은 항목 {unconfirmed.length}개</b>
            <div className="chips">
              {unconfirmed.map((f) => (
                <span key={f} className="chip warn">
                  {reportFieldLabel(f)} 수정
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      <div className="btnrow center">
        {pkg.capabilities.includes('COPY_FIELDS') && (
          <button type="button" className="btn">
            전체 복사
          </button>
        )}
        {pkg.capabilities.includes('OPEN_DESTINATION') && (
          <button type="button" className="btn btn-blue">
            안전신문고로 이동
          </button>
        )}
      </div>

      <p className="disclaimer">
        대신고는 신고를 <b>대신 접수하지 않습니다.</b> 자료를 받아 안전신문고에서 내용을 다시 확인하고 직접
        제출하셔야 합니다.
      </p>
    </div>
  )
}
