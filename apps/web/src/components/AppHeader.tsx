import type { JSX } from 'react'

export function AppHeader(): JSX.Element {
  return (
    <header className="app-header">
      <span className="brand">
        <span className="brand-name">대신고</span>
        <span className="brand-sub">신고할 순간을 대신 찾아드립니다</span>
      </span>
    </header>
  )
}
