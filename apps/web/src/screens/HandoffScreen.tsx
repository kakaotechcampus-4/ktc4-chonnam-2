import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { DisplayRow } from '../components/DisplayRow'
import { Panel } from '../components/Panel'
import { reportFieldLabel } from '../contracts/labels'

// 신고자료 화면 — report_field_states를 직접 읽는다(value-state-display.md §5-1).
// unconfirmed_fields는 요약(「확인 필요 N건」)에만 쓰고 필드별 배지·출처는
// report_field_states에서 가져온다. 두 값이 어긋나면 report_field_states가 authoritative.
export function HandoffScreen(props: { view: CaseView }): JSX.Element {
  const pkg = props.view.package
  if (!pkg) return <Panel title="신고자료">아직 만들어지지 않았습니다.</Panel>

  const gates = [
    ['신고요건', props.view.requirements_evidence?.readiness ?? '확인 전'],
    ['자료 완성', props.view.requirements_package?.readiness ?? '확인 전'],
    ['사용자 확인', props.view.user_reviewed ? '완료' : '미완료'],
  ] as const

  return (
    <div className="stack">
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
        {/* §3-7 WARN이라고 경로를 막지 않는다 — 버튼은 capabilities가 켠다 */}
        <div className="btnrow" style={{ marginTop: 12 }}>
          {pkg.capabilities.includes('DOWNLOAD_ASSETS') && (
            <button type="button" className="btn">
              자료 내려받기
            </button>
          )}
          {pkg.capabilities.includes('COPY_FIELDS') && (
            <button type="button" className="btn">
              항목 복사
            </button>
          )}
          {pkg.capabilities.includes('OPEN_DESTINATION') && (
            <button type="button" className="btn btn-primary">
              안전신문고 열기
            </button>
          )}
        </div>
        {pkg.warnings.length > 0 && (
          <div className="kv-src" style={{ marginTop: 10 }}>
            {pkg.warnings.join(' · ')}
          </div>
        )}
      </Panel>
    </div>
  )
}
