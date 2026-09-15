import type { JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { Panel } from '../components/Panel'

// 후보 0건은 실패가 아니다. candidates=[]·evidence=null·package=null을
// 실패 화면으로 그리지 않는다(체크리스트 Failure/Partial · scenario_empty_001).
export function NoResultScreen(props: { view: CaseView }): JSX.Element {
  const { hints, manifest_summary } = props.view
  return (
    <Panel title="조건에 맞는 장면을 찾지 못했습니다">
      <div className="kv-src">영상은 정상적으로 등록됐습니다. 설명을 바꿔 다시 찾을 수 있습니다.</div>
      <div className="kv kv-rows">
        <div className="kv-row">
          <span className="kv-k">등록된 영상</span>
          <span className="kv-v">
            <span className="kv-val mono">
              {manifest_summary.ok_file_count} / {manifest_summary.file_count}
            </span>
          </span>
        </div>
        {hints.situation && (
          <div className="kv-row">
            <span className="kv-k">말한 상황</span>
            <span className="kv-v">
              <span className="kv-val">{hints.situation}</span>
            </span>
          </div>
        )}
        {hints.time && (
          <div className="kv-row">
            <span className="kv-k">말한 시각</span>
            <span className="kv-v">
              <span className="kv-val">{hints.time}</span>
            </span>
          </div>
        )}
      </div>
    </Panel>
  )
}
