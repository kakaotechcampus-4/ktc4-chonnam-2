import type { JSX } from 'react'
import { Film } from 'lucide-react'
import type { Candidate } from '../contracts/caseView'
import { FrameSlot } from './FrameSlot'
import { SITUATION_LABELS, atProvenanceLabel, formatValue, staleLabel } from '../contracts/labels'
import '../styles/candidates.css'

// 시각 출처는 `at_provenance_label_key`로만 고른다(case-view/v1.4 §7, PR #46
// Q-3). raw `at_provenance`는 authoritative지만 web이 해석하지 않으므로 화면에
// 내보내지 않는다. v5 fixture는 아직 키를 안 내려서 지금은 전부 fallback
// 문구가 뜬다 — 키가 들어오면 문구가 자동으로 바뀐다.
//
// 번호는 case가 준 `rank`다(#122). web이 순위를 계산하지 않는다. mock fixture처럼
// `rank`가 없으면 case가 준 배열 순서(`ordinal`, 1부터)를 그대로 쓴다.
//
// `selected`는 사용자가 고른 후보가 아니라 case가 자동 선택한 현재 초안의
// 기준 후보다(§8-1, #122). 태그 문구도 그 뜻으로 적는다. 신고자료가 없는 화면(위반 미관찰)은
// selectedLabel로 그 뜻에 맞는 문구를 넘긴다.
//
// 미리보기는 case가 내린 장면 ref(#523)를 이미지 주소로 바꾼 `src`로 그린다. 없거나 못 받으면 빈 자리를 두고,
// 도는 작업이 없으면(`pending` 아님) 더 오지 않으므로 「준비 중」이라 하지 않는다(#506과 같은 원칙).
export function CandidateCard(props: {
  candidate: Candidate
  ordinal: number
  selectedLabel?: string
  src?: string | null
  pending?: boolean
}): JSX.Element {
  const c = props.candidate
  const stale = staleLabel(c.stale_revision_label_key)
  return (
    <div className={`cand${c.selected ? ' sel' : ''}`}>
      <FrameSlot className="cand-th" src={props.src ?? null} alt={`${c.rank ?? props.ordinal}번 후보 장면`}>
        <Film className="cand-th-ico" size={24} strokeWidth={1.5} aria-hidden />
        <span className="cand-th-note">{props.pending ? '미리보기 준비 중' : '미리보기가 없어요'}</span>
      </FrameSlot>
      <div className="cand-b">
        <div className="cand-h">
          <span className="cnum">{c.rank ?? props.ordinal}</span>
          <span className="cand-tc">{c.at === null ? '시각 미확정' : formatValue(c.at)}</span>
          {c.selected && <span className="cand-tag">{props.selectedLabel ?? '지금 신고자료 기준'}</span>}
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
