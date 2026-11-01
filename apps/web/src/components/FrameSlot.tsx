import { useState, type JSX, type ReactNode } from 'react'

// FrameRef를 이미지로 그린다. ref가 없거나(null) 받지 못하면(404 · 503) 자리 표시(children)를 둔다.
// 자리 표시가 없으면 칸을 그리지 않는다 — 있을 때만 보이는 이미지다.
export function FrameSlot(props: { src: string | null; alt: string; className: string; children?: ReactNode }): JSX.Element | null {
  const { src } = props
  const [failed, setFailed] = useState<string | null>(null)
  const shown = src !== null && failed !== src
  if (!shown && !props.children) return null
  return (
    <div className={props.className}>
      {shown ? <img src={src} alt={props.alt} onError={() => setFailed(src)} /> : props.children}
    </div>
  )
}
