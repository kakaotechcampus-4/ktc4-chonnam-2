import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { DisplayRow } from '../components/DisplayRow'
import { OtherCandidates } from '../components/OtherCandidates'
import { Panel } from '../components/Panel'
import { readinessLabel, reportFieldLabel } from '../contracts/labels'

// 신고자료 화면 — report_field_states를 직접 읽는다(value-state-display.md §5-1).
// unconfirmed_fields는 요약(「확인 필요 N건」)에만 쓰고 필드별 배지·출처는
// report_field_states에서 가져온다. 두 값이 어긋나면 report_field_states가 authoritative.
export function HandoffScreen(props: { view: CaseView }): JSX.Element {
  const pkg = props.view.package
  if (!pkg) return <Panel title="신고자료">아직 만들어지지 않았습니다.</Panel>

  // §3-5 세 gate는 각각 구분해 표시한다. 등재값을 그대로 내보내지 않고 문구로 바꾼다 —
  // 「PASS」와 「완료」가 한 패널에 나란히 뜨면 같은 축의 값처럼 읽힌다.
  const gates = [
    ['신고요건', readinessLabel(props.view.requirements_evidence?.readiness)],
    ['자료 완성', readinessLabel(props.view.requirements_package?.readiness)],
    ['사용자 확인', props.view.user_reviewed ? '완료' : '미완료'],
  ] as const

  const caps = pkg.capabilities
  // 와이어프레임 13(신고자료) 틀: 머리 → handoff 3단계 → 2단 본문(옮길 값 | 제출 전 확인).
  // 버튼은 capabilities가 켠다(§3-7 WARN이라고 경로를 막지 않는다).
  const handoff = [
    ['영상 내려받기', '신고에 첨부할 영상을 내려받아요.', caps.includes('DOWNLOAD_ASSETS') && '자료 내려받기'],
    ['안전신문고 열기', '새 창에서 열고, 이 화면을 옆에 두고 보세요.', caps.includes('OPEN_DESTINATION') && '안전신문고 열기'],
    ['아래 내용 옮겨 담기', '복사해서 붙여넣거나 안전신문고에서 직접 고르세요.', caps.includes('COPY_FIELDS') && '항목 복사'],
  ] as const

  return (
    <div className="stack">
      <div className="result-head">
        <span className="result-check" aria-hidden>✓</span>
        <div>
          <h1 className="page-title">신고자료가 준비됐어요</h1>
          <p className="kv-src">영상을 내려받고 안전신문고를 연 뒤, 아래 내용을 옮겨 담으시면 됩니다.</p>
        </div>
      </div>

      <div className="step-cards">
        {handoff.map(([title, desc, action], i) => (
          <div className="panel panel-p step-card" key={title}>
            <span className="step-no mono">{i + 1}</span>
            <b>{title}</b>
            <span className="kv-src">{desc}</span>
            {action && (
              <button type="button" className="btn sm">
                {action}
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="result-cols">
        <Panel title="신고자료">
          <div className="kv kv-rows">
            {Object.entries(pkg.report_fields).map(([key, value]) => {
              const state = pkg.report_field_states[key]
              return (
                <DisplayRow
                  key={key}
                  label={reportFieldLabel(key)}
                  value={value}
                  infoState={state ? state.info_state : 'INFO_UNKNOWN'}
                  sourceLabelKey={state ? state.source_label_key : null}
                />
              )
            })}
          </div>
          {pkg.unconfirmed_fields.length > 0 && (
            <div className="kv-src" style={{ marginTop: 10 }}>
              확인 필요 {pkg.unconfirmed_fields.length}건
            </div>
          )}
        </Panel>

        <Panel title="제출 전 확인">
          {/* §3-5 세 gate를 하나의 readiness로 합치지 않는다 */}
          <div className="kv kv-rows">
            {gates.map(([label, value]) => (
              <div className="kv-row" key={label}>
                <span className="kv-k">{label}</span>
                <span className="kv-v">
                  <span className="kv-val">{value}</span>
                </span>
              </div>
            ))}
          </div>
          {pkg.warnings.length > 0 && (
            <div className="kv-src" style={{ marginTop: 10 }}>
              {pkg.warnings.join(' · ')}
            </div>
          )}
        </Panel>
      </div>

      {/* READY에서도 다른 후보를 고를 수 있다(core-user-flow.md §8-1, #173 E-4) */}
      <OtherCandidates view={props.view} />
    </div>
  )
}
