import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, Film } from 'lucide-react'
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
export function DrivingPreview({ active, onBack, sessionKey }: { active: boolean; onBack: () => void; sessionKey?: string }) {
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
      scene.current = createDrivingScene(
        root.current,
        () => { if (!cancelled) setStatus('unavailable') },
        () => { if (!cancelled) setStatus('ready') },
        sessionKey,
      )
      scene.current.setActive(activeRef.current)
    }).catch(() => {
      if (!cancelled) setStatus('unavailable')
    })
    return () => {
      cancelled = true
      scene.current?.dispose()
      scene.current = null
    }
  }, [sessionKey])

  return (
    <div className="driving-preview" ref={root} data-status={status} hidden={!active}>
      <div className="media">
        <button type="button" ref={back} className="flow-preview-switch is-back" title="미리보기로 돌아가기" aria-label="미리보기로 돌아가기" onClick={async () => {
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
        <p className="drive-message" role="status" aria-live="polite" />
      </div>
    </div>
  )
}
