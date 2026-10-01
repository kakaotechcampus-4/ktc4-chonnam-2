import { useEffect, useState, type JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { AppHeader } from '../components/AppHeader'
import { FlowScreen } from './FlowScreen'
import { NoResultScreen } from './NoResultScreen'
import { ResultScreen } from './ResultScreen'
import { CandidateCompare, CandidateDetail, DetailsCheck, PlateCheck } from './SubScreens'
import { UploadScreen, type UploadState } from './UploadScreen'

// 시연용 흐름 — Figma 하단 작업 영역의 Main · Details · Failed 열(After 제외).
// ponytail: API(case.get_view)가 아직 없어 화면마다 fixture CaseView 한 건을 붙인다.
// 상태 전환은 Figma Memo의 키 규칙을 그대로 따른다 — 진행 화면에는 버튼이 없다.
//   d 진행 · a 실패 · w 재시도 · s 뒤로(모든 화면)
// API가 생기면 d/a/w 자리를 get_view() 폴링 결과로 바꾼다.

type Screen =
  | { kind: 'upload'; state: UploadState }
  | { kind: 'flow' | 'retryFlow' | 'failFlow' | 'result' | 'notFound' | 'candidates' | 'plate' | 'details' }
  | { kind: 'candidate'; id: string }

function snapshot(scenarioId: string, index: number): CaseView {
  const found = SNAPSHOTS.find((s) => s.scenarioId === scenarioId && s.index === index)
  if (!found) throw new Error(`fixture 없음: ${scenarioId} #${index}`)
  return found.view
}

// 화면 ↔ fixture. 결과 이후 화면은 모두 같은 결과 CaseView를 본다.
const VIEWS = {
  flow: snapshot('scenario_happy_001', 1),
  retryFlow: snapshot('scenario_infra_failure_001', 1),
  failFlow: snapshot('scenario_infra_failure_001', 2),
  result: snapshot('scenario_happy_001', 2),
  notFound: snapshot('scenario_empty_001', 1),
}

// Memo의 키 규칙. 적혀 있지 않은 조합은 아무 일도 하지 않는다.
function nextScreen(screen: Screen, key: string): Screen | null {
  if (screen.kind === 'upload' && screen.state === 'uploading') {
    if (key === 'd') return { kind: 'upload', state: 'done' }
    if (key === 'a') return { kind: 'upload', state: 'fail' }
  }
  if (screen.kind === 'flow') {
    if (key === 'd') return { kind: 'result' }
    if (key === 'a') return { kind: 'failFlow' }
    if (key === 'w') return { kind: 'retryFlow' }
  }
  if (screen.kind === 'result' && key === 'a') return { kind: 'notFound' }
  return null
}

export function DemoFlow(): JSX.Element {
  const [history, setHistory] = useState<Screen[]>([{ kind: 'upload', state: 'idle' }])
  const [file, setFile] = useState<File | null>(null)
  const [situation, setSituation] = useState('')
  const screen = history[history.length - 1]

  const go = (next: Screen) => setHistory((h) => [...h, next])
  const back = () => setHistory((h) => (h.length > 1 ? h.slice(0, -1) : h))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // 입력칸에 글을 쓰는 중에는 키를 가로채지 않는다.
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === 's') return back()
      const next = nextScreen(screen, e.key)
      if (next) go(next)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [screen])

  const fileName = file?.name ?? ''

  return (
    <>
      <AppHeader />
      <main className="web-main">
        {screen.kind === 'upload' && (
          <UploadScreen
            state={screen.state}
            file={file}
            situation={situation}
            onFile={(f) => {
              setFile(f)
              go({ kind: 'upload', state: 'uploading' })
            }}
            onSituation={setSituation}
            onSearch={() => go({ kind: 'flow' })}
          />
        )}
        {(screen.kind === 'flow' || screen.kind === 'retryFlow' || screen.kind === 'failFlow') && (
          <FlowScreen view={VIEWS[screen.kind]} fileName={fileName} situation={situation} />
        )}
        {screen.kind === 'result' && (
          <ResultScreen
            view={VIEWS.result}
            onCandidates={() => go({ kind: 'candidates' })}
            onPlate={() => go({ kind: 'plate' })}
            onDetails={() => go({ kind: 'details' })}
          />
        )}
        {screen.kind === 'notFound' && <NoResultScreen view={VIEWS.notFound} />}
        {screen.kind === 'candidates' && (
          <CandidateCompare view={VIEWS.result} onBack={back} onDetail={(id) => go({ kind: 'candidate', id })} />
        )}
        {screen.kind === 'candidate' && <CandidateDetail view={VIEWS.result} candidateId={screen.id} onBack={back} />}
        {screen.kind === 'plate' && <PlateCheck view={VIEWS.result} onBack={back} />}
        {screen.kind === 'details' && <DetailsCheck view={VIEWS.result} onBack={back} />}
      </main>
      <div className="demo-keys mono" aria-hidden>
        d 진행 · a 실패 · w 재시도 · s 뒤로
      </div>
    </>
  )
}
