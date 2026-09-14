import type { JSX, ReactNode } from 'react'

/**
 * 한 화면 = 한 단계가 제품 흐름(`core-user-flow.md` §4-1)이다. 증빙을 위해
 * 다른 단계의 패널을 같이 띄워야 할 때만 이걸로 접어 둔다 — 펼치면 증빙이
 * 그대로 남고, 접혀 있으면 화면이 제품 흐름과 같은 모양이 된다.
 * 제품 빌드에서는 이 컴포넌트째로 빠진다.
 */
export function DevExtra(props: { label: string; children: ReactNode }): JSX.Element {
  return (
    <details className="dev-extra">
      <summary>{props.label}</summary>
      <div className="dev-extra-body">{props.children}</div>
    </details>
  )
}
