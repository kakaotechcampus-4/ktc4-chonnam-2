import { useEffect, useState, type JSX } from 'react'
import { SCENARIO_IDS, SNAPSHOTS } from '../contracts/fixtures'
import { selectScreen } from '../state/selectScreen'
import { CaseScreen } from './CaseScreen'

// 시연용 흐름 — 홈 입력 → 진행 → 결과(core-user-flow.md 결과 중심 흐름).
// ponytail: API(case.get_view)가 아직 없어 고른 시나리오의 CaseView 스냅샷을
// 순서대로 재생한다. 영상·상황 입력은 화면에만 머물고 어디에도 보내지 않는다.
// API가 생기면 재생 타이머 자리를 get_view() 폴링으로 바꾼다.
const STEP_MS = 2500
const DEFAULT_SCENARIO = SCENARIO_IDS.includes('scenario_happy_001') ? 'scenario_happy_001' : SCENARIO_IDS[0]

export function DemoFlow(): JSX.Element {
  const [video, setVideo] = useState<string | null>(null)
  const [situation, setSituation] = useState('')
  const [scenario, setScenario] = useState(DEFAULT_SCENARIO)
  const [step, setStep] = useState<number | null>(null)

  const frames = SNAPSHOTS.filter((s) => s.scenarioId === scenario)
  // 진행 화면인 동안만 다음 스냅샷으로 넘어간다. 결과가 뜨면 거기서 멈춘다 —
  // 그 뒤 스냅샷은 사용자 행동 이후 상태라 자동 재생하면 안 된다.
  const running = step !== null && step < frames.length - 1 && selectScreen(frames[step].view).kind === 'PROGRESS'

  useEffect(() => {
    if (!running) return
    const t = setTimeout(() => setStep((s) => (s ?? 0) + 1), STEP_MS)
    return () => clearTimeout(t)
  }, [step, running])

  useEffect(() => () => { if (video) URL.revokeObjectURL(video) }, [video])

  if (step !== null) {
    return (
      <main className="web-main">
        <div className="web-meta">
          <button type="button" className="btn sm" onClick={() => setStep(null)}>처음으로</button>
          {running && <span className="kv-src">신고자료를 준비하고 있어요…</span>}
        </div>
        <CaseScreen view={frames[step].view} />
      </main>
    )
  }

  return (
    <main className="web-main">
      <h1 className="panel-t">블랙박스 영상으로 신고자료 준비하기</h1>
      <div className="panel panel-p stack">
        <label className="stack">
          <span className="sec-label">1. 블랙박스 영상</span>
          <input
            type="file"
            accept="video/*"
            onChange={(e) => {
              const file = e.target.files?.[0]
              setVideo(file ? URL.createObjectURL(file) : null)
            }}
          />
        </label>
        {video && <video src={video} controls style={{ width: '100%', borderRadius: 'var(--R)' }} />}
        <label className="stack">
          <span className="sec-label">2. 어떤 상황이었나요?</span>
          <textarea
            className="field"
            style={{ height: 'auto', padding: 12 }}
            rows={3}
            placeholder="예: 교차로에서 흰색 차가 신호를 무시하고 지나갔어요"
            value={situation}
            onChange={(e) => setSituation(e.target.value)}
          />
        </label>
        <button type="button" className="btn pri" disabled={!video || !situation.trim()} onClick={() => setStep(0)}>
          분석 시작
        </button>
      </div>
      <label className="kv-src">
        시연 시나리오{' '}
        <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
          {SCENARIO_IDS.map((id) => <option key={id}>{id}</option>)}
        </select>
      </label>
    </main>
  )
}
