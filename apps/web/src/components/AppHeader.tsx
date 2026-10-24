import type { JSX } from 'react'

export function AppHeader(props: { onNewReport: () => void }): JSX.Element {
  return (
    <header className="app-header rs-header">
      {/* 로고를 누르면 첫 화면(업로드)으로 — 「새 신고」와 같은 동작이다 */}
      <button type="button" className="brand" onClick={props.onNewReport} aria-label="대신고 첫 화면으로">
        <span className="brand-name">대신고</span>
        <span className="brand-sub">신고할 순간을 대신 찾아드립니다</span>
      </button>
      <nav>
        <button type="button" className="nav-link" onClick={props.onNewReport}>
          새 신고
        </button>
      </nav>
    </header>
  )
}
