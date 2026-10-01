import { useEffect, useState, type JSX } from 'react'
import { SCENARIO_IDS, SNAPSHOTS } from '../contracts/fixtures'
import { selectScreen } from '../state/selectScreen'
import { AppHeader } from '../components/AppHeader'
import { CaseScreen } from './CaseScreen'
import { HomeScreen } from './HomeScreen'
import { UploadScreen } from './UploadScreen'

// 시연용 흐름 — 홈 → 영상·상황 입력 → 준비 중 → 결과(core-user-flow.md 결과 중심 흐름).
// ponytail: API(case.get_view)가 아직 없어 고른 시나리오의 CaseView 스냅샷을
// 순서대로 재생한다. 영상·상황 입력은 화면에만 머물고 어디에도 보내지 않는다.
// API가 생기면 재생 타이머 자리를 get_view() 폴링으로 바꾼다.
const STEP_MS = 2500
const DEFAULT_SCENARIO = SCENARIO_IDS.includes('scenario_happy_001') ? 'scenario_happy_001' : SCENARIO_IDS[0]

type Phase = 'home' | 'upload' | 'run'

export function DemoFlow(): JSX.Element {
  const [phase, setPhase] = useState<Phase>('home')
  const [file, setFile] = useState<File | null>(null)
  const [situation, setSituation] = useState('')
  const [scenario, setScenario] = useState(DEFAULT_SCENARIO)
  const [step, setStep] = useState(0)

  const frames = SNAPSHOTS.filter((s) => s.scenarioId === scenario)
  const view = frames[step].view
  // 진행 화면인 동안만 다음 스냅샷으로 넘어간다. 결과가 뜨면 거기서 멈춘다 —
  // 그 뒤 스냅샷은 사용자 행동 이후 상태라 자동 재생하면 안 된다.
  const preparing = selectScreen(view).kind === 'PROGRESS'
  const running = phase === 'run' && preparing && step < frames.length - 1

  useEffect(() => {
    if (!running) return
    const t = setTimeout(() => setStep((s) => s + 1), STEP_MS)
    return () => clearTimeout(t)
  }, [step, running])

  const home = () => {
    setPhase('home')
    setStep(0)
  }
  const headerStep = phase === 'home' ? null : phase === 'upload' ? 0 : preparing ? 1 : 2

  return (
    <>
      <AppHeader step={headerStep} onHome={home} />
      <main className="web-main">
        {phase === 'home' && <HomeScreen onStart={() => setPhase('upload')} />}

        {phase === 'upload' && (
          <>
            <UploadScreen
              file={file}
              situation={situation}
              onFile={setFile}
              onSituation={setSituation}
              onSubmit={() => {
                setStep(0)
                setPhase('run')
              }}
            />
            <label className="kv-src demo-pick">
              시연 시나리오{' '}
              <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
                {SCENARIO_IDS.map((id) => (
                  <option key={id}>{id}</option>
                ))}
              </select>
            </label>
          </>
        )}

        {phase === 'run' && (
          <>
            <div className="panel panel-p tight run-summary">
              <b>{file?.name}</b>
              <span className="kv-src">“{situation}”</span>
            </div>
            {preparing && <h1 className="page-title">신고자료를 준비하고 있어요</h1>}
            <CaseScreen view={view} />
            {!preparing && (
              <footer className="result-foot">
                <span className="kv-src">
                  <b>대신고는 정부·공공기관 서비스가 아닙니다.</b> 신고 접수는 안전신문고에서 직접 하셔야 하며, 위반
                  여부는 관계기관이 판단합니다.
                </span>
                <button type="button" className="btn sm" onClick={home}>
                  다른 사건 찾기
                </button>
              </footer>
            )}
          </>
        )}
      </main>
    </>
  )
}
