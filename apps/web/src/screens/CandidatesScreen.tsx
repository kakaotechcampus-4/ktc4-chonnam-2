import type { JSX } from 'react'
import type { Candidate, CaseView } from '../contracts/caseView'
import { CandidateAxis } from '../components/CandidateAxis'
import { CandidateVideo, type CandidatePlayback } from '../components/CandidateVideo'
import { CandidateCard, ThumbPlaceholder } from '../components/CandidateCard'
import { HintRecall } from '../components/HintRecall'
import { Panel } from '../components/Panel'

// 후보를 세로로 쌓지 않고 나란히 놓는다(core-user-flow.md §8-2). 배열 순서를
// 그대로 그린다 — 정렬·순위 재계산은 case가 소유한 판정이다.
//
// 기억 단서는 후보 위에 한 번 놓는다. 대조는 하지 않는다(HintRecall 주석).
//
// onSelect가 있으면 기준 후보가 아닌 카드 아래에 「이 장면으로 다시 준비」를 단다
// (core-user-flow §8-1). 누르면 실제 흐름(ApiFlow)이 SELECT_OTHER_CANDIDATE를 보낸다. 기준 후보는 버튼 없이 같이 놓아 비교 기준이 된다.
//
// case는 선택 후보의 관찰 job이 도는 동안(재판독 · 다시 시도 포함) 재선택을 `not_allowed`로 거부한다
// (docs/modules/case/decisions/reselect-while-preparing.md §2). 같은 때에 버튼을 막아 눌렀다 거부당하는 일을 없앤다.
// `REPORT_VIDEO_EXPORT`는 case도 막지 않는다. 낡은 화면에서 눌려 오는 거부는 오류 배너가 받는다.
// 한계: case-view에 재선택 가능 신호가 없어 kind로 추정한다. 후보 · 세대는 view에 없어 case보다 넓게 막을 수 있다(docs/modules/case/decisions/reselect-while-preparing.md §4). 재선택 가능 신호가 CaseView에 생기면 이 목록이 필요 없다.
const PREPARING_KINDS = ['FINE_VERIFY', 'INCIDENT_CLIP_BUILD', 'PLATE_READ', 'OVERLAY_TIME_READ']

// 후보 카드에 장면 이미지와 영상 미리보기를 붙인다. 후보 그리드와 「어떻게 정했는지」의 기준 후보 카드가 같이 쓴다.
export function PlayableCandidateCard(props: {
  view: CaseView
  candidate: Candidate
  ordinal: number
  selectedLabel?: string
} & CandidatePlayback): JSX.Element {
  const c = props.candidate
  // 후보 장면은 thumb_ref(상위 후보마다 case가 만든다). 기준 후보는 아직 thumb_ref가 없으면 근거 장면(evidence.preview_ref)을 쓴다
  const ref = c.thumb_ref ?? (c.selected ? props.view.evidence?.preview_ref ?? null : null)
  const src = ref && props.frameSrc ? props.frameSrc(ref) : null
  // 후보 장면과 근거 장면은 사건 클립을 만드는 작업이 함께 발급한다. 그 작업이 돌 때만 「준비 중」이라 한다
  const pending = props.view.running_jobs.some((j) => j.kind === 'INCIDENT_CLIP_BUILD')
  return (
    <CandidateCard
      candidate={c}
      ordinal={props.ordinal}
      selectedLabel={props.selectedLabel}
      src={src}
      pending={pending}
      preview={c.video_preview && (props.videoSrc || props.onPreview) && (
        <CandidateVideo preview={c.video_preview} ordinal={c.rank ?? props.ordinal}
          src={c.video_preview.clip_ref && props.videoSrc ? props.videoSrc(c.video_preview.clip_ref) : undefined}
          poster={src ?? undefined}
          placeholder={<ThumbPlaceholder pending={pending} />}
          onRequest={props.onPreview ? () => props.onPreview?.(c.candidate_id) : undefined}
          busy={props.previewBusy} />
      )}
    />
  )
}

export function CandidatesScreen(props: {
  view: CaseView
  onSelect?: (candidateId: string) => void
  /** 기준 후보 태그 문구 — 신고자료가 없는 화면에서 바꾼다(CandidateCard) */
  selectedLabel?: string
} & CandidatePlayback): JSX.Element {
  const { onSelect } = props
  const preparing = props.view.running_jobs.some((j) => PREPARING_KINDS.includes(j.kind))
  return (
    <Panel title="찾은 장면">
      <HintRecall hints={props.view.hints} description={props.view.description} />
      <CandidateAxis view={props.view} />
      {onSelect && preparing && <p className="kv-src">지금 준비 중이라 끝난 뒤에 고를 수 있어요.</p>}
      {props.view.candidates.length === 0 && <p className="kv-src">찾은 후보가 없어요.</p>}
      <div className="cands" onPlayCapture={(event) => {
        event.currentTarget.querySelectorAll('video').forEach((video) => {
          if (video !== event.target && !video.paused) video.pause()
        })
      }}>
        {props.view.candidates.map((c, i) => {
          const card = <PlayableCandidateCard key={c.candidate_id} {...props} candidate={c} ordinal={i + 1} />
          if (!onSelect) return card
          return (
            <div key={c.candidate_id} className="cand-col">
              {card}
              {!c.selected && (
                <button type="button" className="btn sm pri" disabled={preparing || props.previewBusy} onClick={() => onSelect(c.candidate_id)}>
                  이 장면으로 다시 준비
                </button>
              )}
            </div>
          )
        })}
      </div>
    </Panel>
  )
}
