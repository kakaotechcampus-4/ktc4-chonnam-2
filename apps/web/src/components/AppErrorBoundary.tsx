import { Component, type ReactNode } from 'react'

// 렌더 중 오류가 나면 React는 앱 전체를 내려 빈 화면이 된다(예: 주행 게임 중 결과 화면으로 넘어갈 때). 그 자리에 다시 불러오기 안내를 둔다.
// 버그를 고치지는 않는다 — 오류는 React가 콘솔에 그대로 남긴다. 안내는 다른 컴포넌트·상태 없이 그린다.
export class AppErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="rs upload" role="alert">
        <h1 className="rs-title">화면을 표시하지 못했어요</h1>
        <p className="rs-lede">새로고침하면 다시 불러와요.</p>
        <div>
          <button type="button" className="rs-btn pri" onClick={() => location.reload()}>
            새로고침
          </button>
        </div>
      </div>
    )
  }
}
