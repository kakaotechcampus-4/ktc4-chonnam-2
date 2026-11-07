import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, ChevronLeft, CornerUpLeft, CornerUpRight, Film, Maximize, Minimize, Pause, Play } from 'lucide-react'
import { PREVIEW_UNAVAILABLE } from '../../contracts/labels.flow'
import type { DrivingScene } from './createDrivingScene.js'
import './driving.css'

/**
 * True when WebGL is drawn by the CPU (SwiftShader, llvmpipe: remote desktops, VMs). There the game
 * starves the page and `/view` polling slows to ~10s, so the entry is hidden. Browsers that hide the
 * renderer name count as hardware.
 */
export function softwareRendering(): boolean {
  if (typeof WebGLRenderingContext === 'undefined') return false
  try {
    const gl = document.createElement('canvas').getContext('webgl')
    if (!gl) return false
    const info = gl.getExtension('WEBGL_debug_renderer_info')
    const name = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : ''
    gl.getExtension('WEBGL_lose_context')?.loseContext()
    return /swiftshader|llvmpipe|softpipe|software|basic render/i.test(name)
  } catch {
    return false
  }
}

/** A browser-local waiting activity. It never reads or changes analysis state. */
export function DrivingPreview({ active, onBack }: { active: boolean; onBack: () => void }) {
  const root = useRef<HTMLDivElement>(null)
  const back = useRef<HTMLButtonElement>(null)
  const scene = useRef<DrivingScene | null>(null)
  const activeRef = useRef(active)
  const [status, setStatus] = useState<'loading' | 'ready' | 'unavailable'>('loading')

  useEffect(() => {
    activeRef.current = active
    scene.current?.setActive(active)
    if (active) back.current?.focus({ preventScroll: true })
  }, [active])

  useEffect(() => {
    let cancelled = false
    // Mounted only after the user chooses the game; returning to preview keeps its state.
    import('./createDrivingScene.js').then(({ createDrivingScene }) => {
      if (cancelled || !root.current) return
      scene.current = createDrivingScene(root.current, () => setStatus('unavailable'))
      scene.current.setActive(activeRef.current)
      setStatus('ready')
    }).catch(() => {
      if (!cancelled) setStatus('unavailable')
    })
    return () => {
      cancelled = true
      scene.current?.dispose()
      scene.current = null
    }
  }, [])

  return (
    <div className="driving-preview" ref={root} data-status={status} hidden={!active}>
      <div className="media">
        <canvas role="img" aria-label="분석을 기다리는 동안 조작하는 주행 화면. 핸들 화살표는 차선 변경과 교차로 회전, P는 갓길 정차, D는 주행입니다." />
        <button type="button" ref={back} className="flow-preview-switch is-back" aria-label="미리보기로 돌아가기" onClick={async () => {
          if (document.fullscreenElement && root.current?.contains(document.fullscreenElement)) {
            try { await document.exitFullscreen() } catch {
              const message = root.current?.querySelector('.drive-message')
              if (message) message.textContent = '크게 보기를 종료한 뒤 돌아갈 수 있어요.'
              return
            }
          }
          onBack()
        }}>
          <ChevronLeft size={18} aria-hidden /><span className="flow-preview-back-label">돌아가기</span>
        </button>
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
