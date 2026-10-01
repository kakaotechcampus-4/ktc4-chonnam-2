import type { JSX } from 'react'

const STEPS = [
  ['영상 올리기', '블랙박스 영상 파일을 골라요.'],
  ['상황 말하기', '언제·어디서·무슨 일이었는지 편하게 적어요.'],
  ['신고자료 받기', 'AI가 장면을 찾고 신고자료 초안까지 준비해요.'],
] as const

export function HomeScreen(props: { onStart: () => void }): JSX.Element {
  return (
    <div className="stack">
      <section className="hero">
        <h1>블랙박스 영상만 있으면 신고자료까지 대신 정리해드려요.</h1>
        <p>영상을 올리고 무슨 일이 있었는지 적어주시면, AI가 위반 장면을 찾아 신고자료 초안을 만들어요.</p>
        <button type="button" className="btn" onClick={props.onStart}>+ 새 신고 시작하기</button>
      </section>
      <div className="step-cards">
        {STEPS.map(([title, desc], i) => (
          <div className="panel panel-p step-card" key={title}>
            <span className="step-no mono">{i + 1}</span>
            <b>{title}</b>
            <span className="kv-src">{desc}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
