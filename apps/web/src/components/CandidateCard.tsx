import type { JSX } from 'react'
import type { Candidate } from '../contracts/caseView'
import { SITUATION_LABELS, atProvenanceLabel, staleLabel } from '../contracts/labels'
import '../styles/candidates.css'

// 시각 출처는 `at_provenance_label_key`로만 고른다(case-view/v1.4 §7, PR #46
// Q-3). raw `at_provenance`는 authoritative지만 web이 해석하지 않으므로 화면에
// 내보내지 않는다. v5 fixture는 아직 키를 안 내려서 지금은 전부 fallback
// 문구가 뜬다 — 키가 들어오면 문구가 자동으로 바뀐다.
//
// `ordinal`은 candidates[] 배열에서의 자리(1부터)다. 화면이 계산한 순위가
// 아니라 case가 준 순서를 그대로 센 것이다(core-user-flow.md §8-2의
// 「시간축 마커와 같은 번호」 자리).
export function CandidateCard(props: { candidate: Candidate; ordinal: number }): JSX.Element {
  const c = props.candidate
  const stale = staleLabel(c.stale_revision_label_key)
  return (
    <div className={`cand${c.selected ? ' sel' : ''}`}>
      <div className="cand-th">
        <span className="cand-th-note">미리보기 준비 중</span>
      </div>
      <div className="cand-b">
        <div className="cand-h">
          <span className="cnum">{props.ordinal}</span>
          <span className="cand-tc">{c.at ?? '시각 미확정'}</span>
          {c.selected && <span className="cand-tag">선택된 장면</span>}
        </div>
        {c.stale_revision && stale && <span className="badge badge-unknown sm">{stale}</span>}
        <p className="cand-obs">{c.observed}</p>
        <dl className="cand-meta">
          <div>
            <dt>상황 확인</dt>
            <dd>{SITUATION_LABELS[c.situation_confirmation]}</dd>
          </div>
          <div>
            <dt>시각 출처</dt>
            <dd>{atProvenanceLabel(c.at_provenance_label_key)}</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
