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

// 결과 없음의 출구(와이어프레임 12 「기억 단서 고치기」). 단서를 다시 글로 받아 새 탐색을
// 시작한다 — 홈과 같은 입력 방식이라 사용자가 새로 배울 것이 없다. 조건별 「넓히기」
// 버튼은 단서를 항목으로 나누는 창구(#210)와 범위 확대 비용 표시(§22)가 생기면 붙인다.
export function RetrySearch(props: {
  situation: string
  onSituation: (text: string) => void
  onRetry: () => void
}): JSX.Element {
  return (
    <Panel title="기억나는 걸 다시 적어 주세요">
      <div className="stack">
        <span className="kv-src">시간·차량·상황을 조금 다르게 적으면 다른 장면을 찾을 수 있어요.</span>
        <textarea
          className="field situation"
          rows={3}
          aria-label="다시 찾을 상황"
          placeholder="예: 7시 전후, 검은 승용차, 중앙선 침범"
          value={props.situation}
          onChange={(e) => props.onSituation(e.target.value)}
        />
        <button type="button" className="btn pri cta" onClick={props.onRetry}>
          다시 찾기
        </button>
      </div>
    </Panel>
  )
}
