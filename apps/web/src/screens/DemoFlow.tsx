import { useEffect, useState, type JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { AppHeader } from '../components/AppHeader'
import { FlowScreen } from './FlowScreen'
import { NoResultScreen } from './NoResultScreen'
import { NotObservedScreen } from './NotObservedScreen'
import { ResultScreen } from './ResultScreen'
import { CandidateCompare, CandidateDetail, DetailsCheck, PlateCheck } from './SubScreens'
import { UploadScreen, type UploadState } from './UploadScreen'

// 시연용 흐름 — Figma 하단 작업 영역의 Main · Details · Failed 열(After 제외).
// 화면은 사용자 행동(파일 선택·버튼)과 작업 상태 변화로만 넘어간다.
// ponytail: API(case.get_view)가 아직 없어 업로드는 타이머로, 진행은 fixture
// CaseView를 차례로 재생해 흉내 낸다. API가 생기면 이 두 타이머 자리를
// 업로드 응답과 get_view() 폴링으로 바꾼다.
const UPLOAD_MS = 1500
const STEP_MS = 2500

function snapshot(scenarioId: string, index: number): CaseView {
  const found = SNAPSHOTS.find((s) => s.scenarioId === scenarioId && s.index === index)
  if (!found) throw new Error(`fixture 없음: ${scenarioId} #${index}`)
  return found.view
}

const SEARCHING = snapshot('scenario_happy_001', 1)
const RESULT = snapshot('scenario_happy_001', 2)
const PLATE_RETRY = snapshot('scenario_infra_failure_001', 1)
const PLATE_FAILED = snapshot('scenario_infra_failure_001', 2)
const NOT_FOUND = snapshot('scenario_empty_001', 1)

// ponytail: 음성 결과(#168 [A]) fixture가 아직 없다(case PR #209 이후). 계약이 정한 모양
// — EVIDENCE_REVIEW + evidence=null + evidence.visual_event_not_observed — 을 시연용으로만
// 만든다. 「다른 후보 보기」를 보이려고 두 번째 후보도 붙인다. fixture가 생기면 snapshot()으로 바꾼다.
const NOT_OBSERVED: CaseView = {
  ...SEARCHING,
  stage: 'EVIDENCE_REVIEW',
  progress: SEARCHING.progress.map((p) => ({ ...p, state: 'DONE' as const })),
  running_jobs: [],
  candidates: [
    ...RESULT.candidates,
    {
      ...RESULT.candidates[0],
      candidate_id: 'demo_c2',
      selected: false,
      at: null,
      observed: '흰 SUV가 교차로에서 정지선을 넘어 멈춘 장면',
    },
  ],
  notices: [
    {
      code: 'evidence.visual_event_not_observed',
      severity: 'INFO',
      blocking: false,
      message_key: 'notice.visual_event_not_observed',
      actions: [],
    },
  ],
}

// 실패·재시도·결과 없음은 사용자가 고르는 게 아니라 작업이 정한다. 시연에서
// 어느 경우를 보여 줄지만 미리 고른다.
type End = 'result' | 'notFound' | 'notObserved' | 'stay'
const CASES = {
  main: { label: '정상 — 신고자료 준비', uploadOk: true, frames: [SEARCHING], end: 'result' },
  retry: { label: '번호판 다시 읽은 뒤 신고자료', uploadOk: true, frames: [SEARCHING, PLATE_RETRY], end: 'result' },
  fail: { label: '번호판 판독 실패', uploadOk: true, frames: [SEARCHING, PLATE_RETRY, PLATE_FAILED], end: 'stay' },
  notObserved: { label: '찾은 장면에서 위반 미관찰', uploadOk: true, frames: [SEARCHING], end: 'notObserved' },
  notFound: { label: '결과 없음(장면 0개)', uploadOk: true, frames: [SEARCHING], end: 'notFound' },
  uploadFail: { label: '업로드 실패', uploadOk: false, frames: [], end: 'stay' },
} satisfies Record<string, { label: string; uploadOk: boolean; frames: CaseView[]; end: End }>
type CaseKey = keyof typeof CASES

type Main =
  | { kind: 'upload'; state: UploadState }
  | { kind: 'flow'; frame: number }
  | { kind: 'result' | 'notFound' | 'notObserved' }
type Sub = { kind: 'candidates' | 'plate' | 'details' } | { kind: 'candidate'; id: string }

export function DemoFlow(): JSX.Element {
  const [caseKey, setCaseKey] = useState<CaseKey>('main')
  const [main, setMain] = useState<Main>({ kind: 'upload', state: 'idle' })
  const [subs, setSubs] = useState<Sub[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [situation, setSituation] = useState('')
  const demo = CASES[caseKey]

  // 업로드가 끝나면 완료/실패로 넘어간다.
  useEffect(() => {
    if (main.kind !== 'upload' || main.state !== 'uploading') return
    const t = setTimeout(() => setMain({ kind: 'upload', state: demo.uploadOk ? 'done' : 'fail' }), UPLOAD_MS)
    return () => clearTimeout(t)
  }, [main, demo])

  // 진행 중에는 다음 CaseView가 오면 화면이 바뀌고, 마지막이 오면 결과로 간다.
  useEffect(() => {
    if (main.kind !== 'flow') return
    const last = main.frame >= demo.frames.length - 1
    if (last && demo.end === 'stay') return
    const t = setTimeout(
      () =>
        setMain(last ? { kind: demo.end as 'result' | 'notFound' | 'notObserved' } : { kind: 'flow', frame: main.frame + 1 }),
      STEP_MS,
    )
    return () => clearTimeout(t)
  }, [main, demo])

  const open = (sub: Sub) => setSubs((s) => [...s, sub])
  const back = () => setSubs((s) => s.slice(0, -1))
  const sub = subs[subs.length - 1]
  // 하위 화면은 들어온 결과 화면의 CaseView를 그대로 본다.
  const subView = main.kind === 'notObserved' ? NOT_OBSERVED : RESULT

  return (
    <>
      <AppHeader />
      <main className="web-main">
        {main.kind === 'upload' && (
          <>
            <UploadScreen
              state={main.state}
              file={file}
              situation={situation}
              onFile={(f) => {
                setFile(f)
                setMain({ kind: 'upload', state: 'uploading' })
              }}
              onSituation={setSituation}
              onSearch={() => setMain({ kind: 'flow', frame: 0 })}
            />
            <label className="kv-src demo-pick">
              시연할 경우{' '}
              <select value={caseKey} onChange={(e) => setCaseKey(e.target.value as CaseKey)}>
                {Object.entries(CASES).map(([key, c]) => (
                  <option key={key} value={key}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        {main.kind === 'flow' && (
          <FlowScreen view={demo.frames[main.frame]} fileName={file?.name ?? ''} situation={situation} />
        )}
        {main.kind === 'notFound' && <NoResultScreen view={NOT_FOUND} />}
        {main.kind === 'notObserved' && !sub && (
          <NotObservedScreen view={NOT_OBSERVED} onCandidates={() => open({ kind: 'candidates' })} />
        )}

        {main.kind === 'result' && !sub && (
          <ResultScreen
            view={RESULT}
            onCandidates={() => open({ kind: 'candidates' })}
            onPlate={() => open({ kind: 'plate' })}
            onDetails={() => open({ kind: 'details' })}
          />
        )}
        {sub?.kind === 'candidates' && (
          <CandidateCompare view={subView} onBack={back} onDetail={(id) => open({ kind: 'candidate', id })} />
        )}
        {sub?.kind === 'candidate' && <CandidateDetail view={subView} candidateId={sub.id} onBack={back} />}
        {sub?.kind === 'plate' && <PlateCheck view={RESULT} onBack={back} />}
        {sub?.kind === 'details' && <DetailsCheck view={RESULT} onBack={back} />}
      </main>
    </>
  )
}
