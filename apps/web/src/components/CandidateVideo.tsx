import { useState, type JSX } from 'react'
import { Play } from 'lucide-react'
import type { CandidateVideoPreview } from '../contracts/caseView'
import { FrameSlot } from './FrameSlot'
import '../styles/candidates.css'

export interface CandidatePlayback {
  videoSrc?: (clipRef: string) => string
  frameSrc?: (frameRef: string) => string
  onPreview?: (candidateId: string) => void
  previewBusy?: boolean
}

export function CandidateVideo(props: {
  preview: CandidateVideoPreview
  ordinal: number
  src?: string
  poster?: string
  onRequest?: () => void
  busy?: boolean
}): JSX.Element {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const status = props.preview.status
  if (status === 'READY' && props.src && failedSrc !== props.src) {
    return <video className="candidate-video-player" src={props.src} poster={props.poster} controls playsInline
      preload="metadata" aria-label={`${props.ordinal}번 후보 영상`} onError={() => setFailedSrc(props.src ?? null)} />
  }
  const browserFailed = status === 'READY' && !!props.src && failedSrc === props.src
  const preparing = status === 'PREPARING'
  const message = preparing ? '영상 준비 중' : browserFailed ? '영상을 재생할 수 없어요.'
    : status === 'FAILED' ? '영상을 준비하지 못했어요.'
      : status === 'UNAVAILABLE' || !props.onRequest ? '이 후보의 미리보기를 볼 수 없어요.' : null
  return (
    <div className="candidate-video">
      <FrameSlot className="candidate-video-poster" src={props.poster ?? null} alt={`${props.ordinal}번 후보 장면`} />
      <div className="candidate-video-actions">
        {message && <span role={preparing ? 'status' : undefined}>{message}</span>}
        {browserFailed ? (
          <button type="button" className="btn sm" onClick={() => setFailedSrc(null)}>다시 불러오기</button>
        ) : !preparing && status !== 'UNAVAILABLE' && props.onRequest && (
          <button type="button" className="btn sm" onClick={props.onRequest} disabled={props.busy}
            aria-label={`${props.ordinal}번 후보 ${status === 'FAILED' ? '영상 다시 준비' : '영상 보기'}`}>
            <Play size={18} aria-hidden />{status === 'FAILED' ? '다시 준비' : '영상 보기'}
          </button>
        )}
      </div>
    </div>
  )
}
