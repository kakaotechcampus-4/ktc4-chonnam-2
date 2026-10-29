import { useState, type JSX, type ReactNode } from 'react'

// FrameRef를 이미지로 그린다. ref가 없거나(null) 받지 못하면(404 · 503) 자리 표시를 그대로 둔다.
export function FrameSlot(props: { src: string | null; alt: string; className: string; children: ReactNode }): JSX.Element {
  const { src } = props
  const [failed, setFailed] = useState<string | null>(null)
  return (
    <div className={props.className}>
      {src !== null && failed !== src ? <img src={src} alt={props.alt} onError={() => setFailed(src)} /> : props.children}
    </div>
  )
}
