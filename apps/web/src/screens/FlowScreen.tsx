import { useEffect, useRef, useState, type JSX } from 'react'
import { Clock, FileVideo, MessageSquareText } from 'lucide-react'
import type { CaseView } from '../contracts/caseView'
import { PROGRESS_LABELS, stepLabel } from '../contracts/labels'
import { selectScreen } from '../state/selectScreen'
import { ProgressPanel } from '../components/ProgressPanel'

// Figma 02_Main_Flow · 02_Retry_Flow · 02_Fail_Flow. 세 프레임은 같은 틀이고
// 단계 상태(progress)와 알림(notices)만 다르다 — 둘 다 CaseView에서 온다.
// 진행 화면에는 버튼도 알림 문구도 없다. 실패는 그 단계를 빨갛게만 칠하고,
// 무슨 일이 있었는지는 결과 화면에서 알린다.
//
// 가장 크게 보이는 제목은 지금 RUNNING인 단계의 이름이다(progress에서 그대로 읽는다).
// 단계 사이처럼 RUNNING이 잠깐 없을 때는 마지막으로 진행하던 단계를 그대로 두어 제목이
// 흔들리지 않게 한다. 아직 한 단계도 시작하지 않았을 때만 전체 흐름 문구를 제목으로 쓴다.
export function FlowScreen(props: {
  view: CaseView
  files: string[]
  situation: string
  startedAt: number
  title?: string
}): JSX.Element {
  const screen = selectScreen(props.view)
  // 장면 찾기가 끝나기 전에는 「찾는 중」, 끝나면 「준비 중」(core-user-flow §7·§19).
  const found = props.view.progress.some((p) => p.step === 'coarse_search' && p.state === 'DONE')
  const overall = props.title ?? (found ? '신고자료를 준비하고 있어요' : '사건을 찾고 있어요')
  const running = props.view.progress.find((p) => p.state === 'RUNNING')?.step
  const last = useRef<string | undefined>(undefined)
  if (running) last.current = running
  const current = running ?? last.current
  // 제목 아래 상태 줄 — 제목으로 둔 단계의 실제 상태(진행 중·완료·실패)를 함께 보여
  // 끝난 단계가 계속 진행 중으로 보이지 않게 한다. 줄 자리는 늘 비워 두어 높이가 같다.
  const currentState = props.view.progress.find((p) => p.step === current)?.state
  // 경과 시간만 보여준다. 남은 시간·퍼센트는 내지 않는다(§7).
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const sec = Math.max(0, Math.floor((now - props.startedAt) / 1000))
  const elapsed = `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`
  return (
    <div className="rs rs-screen flow">
      <div className="flow-head" aria-live="polite">
        {current && <p className="flow-overall">{overall}</p>}
        {/* key가 바뀌면 다시 그려져 제목이 부드럽게 바뀐다 */}
        <h1 className="rs-title flow-now" key={current ?? 'overall'}>
          {current ? stepLabel(current) : overall}
        </h1>
        <p className={`flow-status${currentState ? ` is-${currentState.toLowerCase()}` : ''}`}>
          {currentState && (
            <>
              <span className="flow-status-mark" aria-hidden />
              {PROGRESS_LABELS[currentState]}
            </>
          )}
        </p>
      </div>

      <ul className="flow-meta">
        <li>
          <FileVideo size={16} strokeWidth={1.8} aria-hidden />
          <span className="flow-files">
            {props.files.map((name, i) => (
              <span key={`${name}-${i}`}>{name}</span>
            ))}
          </span>
        </li>
        {props.situation && (
          <li>
            <MessageSquareText size={16} strokeWidth={1.8} aria-hidden />
            <span>“{props.situation}”</span>
          </li>
        )}
        <li>
          <Clock size={16} strokeWidth={1.8} aria-hidden />
          <span>
            경과 시간 <span className="flow-elapsed">{elapsed}</span>
          </span>
        </li>
      </ul>

      <ProgressPanel view={props.view} jobs={screen.jobs} />
    </div>
  )
}
