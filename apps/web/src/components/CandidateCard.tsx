import type { JSX } from 'react'
import type { Candidate } from '../contracts/caseView'
import { SITUATION_LABELS, atProvenanceLabel, staleLabel } from '../contracts/labels'

// 시각 출처는 `at_provenance_label_key`로만 고른다(case-view/v1.4 §7, PR #46
// Q-3). raw `at_provenance`는 authoritative지만 web이 해석하지 않으므로 화면에
// 내보내지 않는다. v5 fixture는 아직 키를 안 내려서 지금은 전부 fallback
// 문구가 뜬다 — 키가 들어오면 문구가 자동으로 바뀐다.
export function CandidateCard(props: { candidate: Candidate }): JSX.Element {
  const c = props.candidate
  const stale = staleLabel(c.stale_revision_label_key)
  return (
    <div className={`panel panel-p tight${c.selected ? ' candidate-selected' : ''}`}>
      <div className="sec-label">
        {c.selected ? '선택된 장면' : '후보 장면'}
        {c.stale_revision && stale && <span className="badge badge-unknown sm">{stale}</span>}
      </div>
      <div className="kv-val mono">{c.at ?? '시각 미확정'}</div>
      <div className="kv-src">{c.observed}</div>
      <div className="kv kv-rows">
        <div className="kv-row">
          <span className="kv-k">상황 확인</span>
          <span className="kv-v">
            <span className="kv-val">{SITUATION_LABELS[c.situation_confirmation]}</span>
          </span>
        </div>
        <div className="kv-row">
          <span className="kv-k">시각 출처</span>
          <span className="kv-v">
            <span className="kv-val">{atProvenanceLabel(c.at_provenance_label_key)}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
