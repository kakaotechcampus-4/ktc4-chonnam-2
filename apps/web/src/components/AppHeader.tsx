import type { JSX } from 'react'

// 결과 중심 흐름(core-user-flow.md, #145)의 세 묶음. 사용자가 멈추는 곳은
// 입력과 결과 두 곳뿐이고, 가운데는 AI 작업이다.
const STEPS = ['영상·상황 입력', '신고자료 준비', '결과 확인'] as const

export function AppHeader(props: { step: number | null; onHome: () => void }): JSX.Element {
  const step = props.step
  return (
    <header className="app-header">
      <button type="button" className="brand" onClick={props.onHome}>
        <span className="brand-name">대신고</span>
        <span className="brand-sub">신고할 순간을 대신 찾아드립니다</span>
      </button>
      {step !== null && (
        <ol className="flow-steps">
          {STEPS.map((label, i) => (
            <li key={label} className={i === step ? 'on' : i < step ? 'done' : ''}>
              <span className="mono">{i + 1}</span> {label}
            </li>
          ))}
        </ol>
      )}
    </header>
  )
}
