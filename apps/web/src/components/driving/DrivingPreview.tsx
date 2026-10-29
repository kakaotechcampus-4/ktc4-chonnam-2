import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, CornerUpLeft, CornerUpRight, Film, Maximize, Minimize, Pause, Play } from 'lucide-react'
import { PREVIEW_UNAVAILABLE } from '../../contracts/labels.flow'
import './driving.css'

/** A browser-local waiting activity. It never reads or changes analysis state. */
export function DrivingPreview() {
  const root = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'unavailable'>('loading')

  useEffect(() => {
    let cancelled = false
    let dispose: (() => void) | undefined
    // Neither Three.js nor its scene is loaded for a successful video thumbnail.
    import('./createDrivingScene.js').then(({ createDrivingScene }) => {
      if (cancelled || !root.current) return
      dispose = createDrivingScene(root.current, () => setStatus('unavailable'))
      setStatus('ready')
    }).catch(() => {
      if (!cancelled) setStatus('unavailable')
    })
    return () => {
      cancelled = true
      dispose?.()
    }
  }, [])

  return (
    <div className="driving-preview" ref={root} data-status={status}>
      <div className="media">
        <canvas role="img" aria-label="분석을 기다리는 동안 조작하는 주행 화면. 핸들 화살표는 차선 변경과 교차로 회전, P는 갓길 정차, D는 주행입니다." />
        {status !== 'ready' && (
          <div className="drive-unavailable" role="status">
            <Film size={24} aria-hidden />
            <span>{status === 'loading' ? '주행 화면을 준비하고 있어요' : PREVIEW_UNAVAILABLE}</span>
          </div>
        )}
        <div className="drive-controls" hidden={status !== 'ready'}>
          <div className="view-tools">
            <button type="button" className="motion" aria-label="주행 화면 일시정지" aria-pressed="false">
              <Pause className="pause-icon" size={17} aria-hidden /><Play className="play-icon" size={17} aria-hidden />
            </button>
            <button type="button" className="fullscreen" aria-label="주행 화면 크게 보기" aria-pressed="false">
              <Maximize className="expand-icon" size={17} aria-hidden /><Minimize className="collapse-icon" size={17} aria-hidden />
            </button>
          </div>
          <button type="button" className="wheel-arrow" data-steer="-1" data-mode="lane" aria-label="왼쪽 차선으로 이동" aria-pressed="false">
            <ArrowLeft className="lane-symbol" aria-hidden /><CornerUpLeft className="turn-symbol" aria-hidden />
          </button>
          <button type="button" className="wheel-arrow" data-steer="1" data-mode="lane" aria-label="오른쪽 차선으로 이동" aria-pressed="false">
            <ArrowRight className="lane-symbol" aria-hidden /><CornerUpRight className="turn-symbol" aria-hidden />
          </button>
          <div className="gear" role="group" aria-label="주행 화면 기어">
            <button type="button" data-gear="P" aria-label="P 갓길에 정차" aria-pressed="false">P</button>
            <button type="button" data-gear="D" aria-label="D 주행" aria-pressed="true">D</button>
          </div>
        </div>
        <p className="drive-message" role="status" aria-live="polite" />
      </div>
    </div>
  )
}
