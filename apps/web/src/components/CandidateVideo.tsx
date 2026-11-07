import { useEffect, useId, useRef, useState, type JSX, type ReactNode } from 'react'
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
  /** 포스터 이미지가 없을 때 그 자리에 둔다(없으면 포스터 칸을 비운다) */
  placeholder?: ReactNode
  onRequest?: () => void
  busy?: boolean
}): JSX.Element {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const status = props.preview.status
  const playable = status === 'READY' && !!props.src && failedSrc !== props.src
  const preparing = status === 'PREPARING'
  const browserFailed = status === 'READY' && !!props.src && failedSrc === props.src
  const message = preparing ? '영상 준비 중' : browserFailed ? '영상을 재생할 수 없어요.'
    : status === 'FAILED' ? '영상을 준비하지 못했어요.'
      : status === 'UNAVAILABLE' || !props.onRequest ? '이 후보의 미리보기를 볼 수 없어요.' : null
  // 버튼 · 문구가 사라지거나 플레이어로 바뀌면 초점이 body로 빠진다(#554 리뷰). 상태가 바뀔 때 초점이 빠져 있으면
  // 준비 중엔 문구로, 그 밖엔 영상 → 버튼 → 문구 순으로 옮긴다. 다른 곳을 보던 사용자는 끌어오지 않는다.
  const phase = playable ? 'PLAYING' : browserFailed ? 'BROWSER_FAILED' : status
  const msgRef = useRef<HTMLSpanElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const prev = useRef(phase)
  const [changed, setChanged] = useState(false)
  useEffect(() => {
    if (prev.current === phase) return
    prev.current = phase
    setChanged(true)
    const active = document.activeElement
    if (active && active !== document.body) return
    const target = preparing ? msgRef.current : videoRef.current ?? buttonRef.current ?? msgRef.current
    target?.focus({ preventScroll: true })
  }, [phase, preparing])
  const msgId = useId()
  // 알림 칸은 늘 같은 자리(첫 자식)에 둔다 — 자리가 바뀌면 새 요소가 되어 스크린 리더가 읽지 않는다.
  // 플레이어로 바뀌면 문구가 사라지므로 「준비됐어요」만 여기서 읽는다. 그 밖의 문구는 초점이 옮겨 간 문구 · 버튼(설명)이 읽는다.
  return <>
    <span className="candidate-video-live" role="status">{changed && playable ? '영상이 준비됐어요' : ''}</span>
    {playable ? (
      <video ref={videoRef} tabIndex={-1} className="candidate-video-player" src={props.src} poster={props.poster} controls playsInline
        preload="metadata" aria-label={`${props.ordinal}번 후보 영상`} onError={() => setFailedSrc(props.src ?? null)} />
    ) : (
      <div className="candidate-video">
        <FrameSlot className="candidate-video-poster" src={props.poster ?? null} alt={`${props.ordinal}번 후보 장면`}>
          {props.placeholder}
        </FrameSlot>
        <div className="candidate-video-actions">
          {/* 상태마다 새 요소로 그린다 — 초점이 있는 문구의 글자만 바뀌면 스크린 리더가 바뀐 조각만 읽다 끊긴다 */}
          {message && <span key={phase} ref={msgRef} id={msgId} tabIndex={-1}>{message}</span>}
          {browserFailed ? (
            <button ref={buttonRef} type="button" className="btn sm" aria-describedby={msgId} onClick={() => setFailedSrc(null)}>다시 불러오기</button>
          ) : !preparing && status !== 'UNAVAILABLE' && props.onRequest && (
            <button ref={buttonRef} type="button" className="btn sm" onClick={props.onRequest} disabled={props.busy} aria-describedby={message ? msgId : undefined}
              aria-label={`${props.ordinal}번 후보 ${status === 'FAILED' ? '영상 다시 준비' : '영상 보기'}`}>
              <Play size={18} aria-hidden />{status === 'FAILED' ? '다시 준비' : '영상 보기'}
            </button>
          )}
        </div>
      </div>
    )}
  </>
}
