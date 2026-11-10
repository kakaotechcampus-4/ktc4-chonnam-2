import { useEffect, useRef, useState, type JSX } from 'react'
import { ChevronRight, Film } from 'lucide-react'
import { PREVIEW_UNAVAILABLE, REPRESENTATIVE_VIDEO } from '../contracts/labels.flow'
import { decodeAviFrame } from './aviFrame'
import { DrivingPreview } from './driving/DrivingPreview'

// 대표 영상의 정지 화면 한 장. 브라우저 안에서 원본 File로 임시 주소를 만들어 앞부분 한
// 장면을 그린다 — 서버 업로드·분석과 무관하고, 재생 기능도 없다.
//
// 그리지 못하면(지원하지 않는 형식·손상·시간 초과·원본 없음) 같은 크기의 프레임에 필름
// 아이콘과 「미리보기를 표시할 수 없어요」를 둔다. 파일 이름은 어느 쪽이든 프레임 아래다. 이것은 브라우저가 미리보기를 못 만든 것일 뿐 분석 실패가 아니다 — 진행 상태나
// 분석 대상에는 아무 영향이 없다. 준비되는 동안에도 나머지 화면은 그대로 그려진다.
const SEEK_SEC = 1
const GIVE_UP_MS = 4000
const MAX_WIDTH = 960

function snapshot(image: CanvasImageSource, w: number, h: number): string | null {
  if (!w || !h) return null
  const scale = Math.min(1, MAX_WIDTH / w)
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(w * scale)
  canvas.height = Math.round(h * scale)
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height)
  try {
    return canvas.toDataURL('image/jpeg', 0.82)
  } catch {
    return null
  }
}

export function VideoThumb(props: {
  file: File | null
  name: string
  /** 분석 중 선택해서 여는 주행 게임. 미리보기 성공 여부와 무관하다. */
  canDrive?: boolean
  gameSessionKey?: string
  /**
   * 브라우저에 원본이 없거나(결과 화면에서 다시 준비 · 창을 닫았다 옴) 그리지 못할 때 대신 보일
   * 서버의 장면 이미지(고른 후보의 thumb_ref). 이것도 못 불러오면 원래 안내를 둔다.
   */
  fallbackSrc?: string | null
}): JSX.Element {
  const [shot, setShot] = useState<{ file: File; src: string } | null>(null)
  const [failed, setFailed] = useState<File | null>(null)
  const [fallbackFailed, setFallbackFailed] = useState<string | null>(null)
  const [driving, setDriving] = useState<'unopened' | 'preview' | 'game'>('unopened')
  const entry = useRef<HTMLButtonElement>(null)
  const wasDriving = useRef(false)
  const gameVisible = !!props.canDrive && driving === 'game'

  useEffect(() => {
    if (!props.canDrive) setDriving('unopened')
  }, [props.canDrive])
  useEffect(() => {
    if (wasDriving.current && !gameVisible) entry.current?.focus({ preventScroll: true })
    wasDriving.current = gameVisible
  }, [gameVisible])

  useEffect(() => {
    const file = props.file
    if (!file) return
    // AVI는 <video>가 열지 못하므로 첫 영상 조각을 직접 디코드한다(블랙박스 AVI 대응). 캡처 지점은 첫 키프레임(0초)이다.
    if (/\.avi$/i.test(file.name) || file.type === 'video/avi' || file.type === 'video/x-msvideo') {
      let cancelled = false
      decodeAviFrame(file).then(
        (frame) => {
          const src = frame && !cancelled ? snapshot(frame.image, frame.width, frame.height) : null
          frame?.close()
          if (cancelled) return
          if (src) setShot({ file, src })
          else setFailed(file)
        },
        () => !cancelled && setFailed(file),
      )
      return () => {
        cancelled = true
      }
    }
    // 임시 주소를 못 만드는 환경(테스트용 jsdom 등)에서는 바로 대체 화면이다.
    if (typeof URL.createObjectURL !== 'function') {
      setFailed(file)
      return
    }
    let url: string
    try {
      url = URL.createObjectURL(file)
    } catch {
      setFailed(file)
      return
    }
    const video = document.createElement('video')
    video.muted = true
    video.preload = 'auto'
    video.playsInline = true
    let done = false

    // 파일이 바뀌거나 화면을 벗어나면 임시 주소와 디코더를 놓는다. 성공·실패·정리 어느 쪽에서
    // 불려도 한 번만 놓는다.
    const release = () => {
      if (done) return
      done = true
      clearTimeout(timer)
      video.removeAttribute('src')
      video.load()
      URL.revokeObjectURL(url)
    }
    const fail = () => {
      if (done) return
      release()
      setFailed(file)
    }
    const timer = setTimeout(fail, GIVE_UP_MS)

    video.addEventListener('error', fail)
    video.addEventListener('loadedmetadata', () => {
      if (done) return
      const d = video.duration
      try {
        video.currentTime = Number.isFinite(d) && d > 0 ? Math.min(SEEK_SEC, d / 2) : 0.1
      } catch {
        fail()
      }
    })
    video.addEventListener('seeked', () => {
      if (done) return
      const src = snapshot(video, video.videoWidth, video.videoHeight)
      if (!src) return fail()
      release()
      setShot({ file, src })
    })
    video.src = url
    return release
  }, [props.file])

  const src = shot && shot.file === props.file ? shot.src : null
  // 준비 중에는 필름 아이콘만, 끝내 못 그리면 「미리보기를 표시할 수 없어요」까지 보인다.
  const unavailable = !props.file || failed === props.file
  const fallback = unavailable && props.fallbackSrc && fallbackFailed !== props.fallbackSrc ? props.fallbackSrc : null
  const shown = src ?? fallback
  return (
    <figure className="flow-thumb">
      <div className="flow-thumb-box">
        <div className={`flow-thumb-frame${shown ? ' has-shot' : ''}`}>
          <div className="flow-thumb-content" hidden={gameVisible}>
            {!shown && (
              <span className="flow-thumb-fallback">
                <Film size={24} strokeWidth={1.8} aria-hidden />
                {unavailable && <span>{PREVIEW_UNAVAILABLE}</span>}
              </span>
            )}
            {src && <img src={src} alt="" />}
            {!src && fallback && <img src={fallback} alt="" onError={() => setFallbackFailed(fallback)} />}
            {props.canDrive && (
              <button type="button" ref={entry} className="flow-preview-switch is-game" onClick={() => setDriving('game')}>
                <span className="flow-preview-invite-copy">
                  {driving === 'unopened' ? '기다리는 동안 게임을 해보시겠어요?' : '주행 게임'}
                </span>
                <ChevronRight size={16} aria-hidden />
              </button>
            )}
          </div>
          {props.canDrive && driving !== 'unopened' && (
            <DrivingPreview active={gameVisible} onBack={() => setDriving('preview')} sessionKey={props.gameSessionKey} />
          )}
        </div>
      </div>
      <figcaption>
        <span>{REPRESENTATIVE_VIDEO}</span>
        {props.name && <span className="flow-thumb-name">{props.name}</span>}
      </figcaption>
    </figure>
  )
}
