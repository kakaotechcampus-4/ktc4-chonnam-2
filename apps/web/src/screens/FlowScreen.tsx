import { useEffect, useRef, useState, type JSX } from 'react'
import { ChevronDown } from 'lucide-react'
import type { CaseView } from '../contracts/caseView'
import { stepLabel } from '../contracts/labels'
import {
  CURRENT_STEP_STATE,
  OTHERS_CONTINUING,
  SITUATION_HEADING,
  SOME_STEPS_FAILED,
  STEPS_HEADING,
  stepCount,
  stepFailedLabel,
  videoCount,
} from '../contracts/labels.flow'
import { selectScreen } from '../state/selectScreen'
import { ProgressPanel } from '../components/ProgressPanel'
import { VideoThumb } from '../components/VideoThumb'

// Figma 02_Main_Flow · 02_Retry_Flow · 02_Fail_Flow. 세 프레임은 같은 틀이고
// 단계 상태(progress)와 알림(notices)만 다르다 — 둘 다 CaseView에서 온다.
// 진행 화면에는 버튼이 없다. 실패한 단계는 목록에서 빨갛게 칠하고, 다른 단계가 실제로
// RUNNING일 때만 「나머지 작업은 계속하고 있어요」를 한 줄 붙인다. 전체 작업이 멈췄는지는
// 화면이 RUNNING 유무로 단정하지 않는다 — 단계 사이에도 RUNNING이 잠깐 없을 수 있다.
// 멈춤은 blocking notice(계약 B절 notices[].blocking)로만 알 수 있고, 그때는 이 안내를
// 내지 않는다. 무슨 일이 있었는지는 실패·결과 화면에서 알린다.
//
// 가장 크게 보이는 제목은 지금 RUNNING인 단계의 이름이다(progress에서 그대로 읽는다).
// 단계 사이처럼 RUNNING이 잠깐 없을 때는 마지막으로 진행하던 단계를 그대로 두어 제목이
// 흔들리지 않게 한다. 아직 한 단계도 시작하지 않았을 때만 전체 흐름 문구를 제목으로 쓴다.
export function FlowScreen(props: {
  view: CaseView
  files: File[]
  /** 업로드가 열 수 없어 건너뛴 파일 이름 — 대표 영상에서 뺀다 */
  skipped?: string[]
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
  const failed = props.view.progress.filter((p) => p.state === 'FAILED')
  const continuing = failed.length > 0 && running !== undefined && screen.blocking.length === 0
  // 대표 영상 = 업로드가 정상으로 받아들인 첫 파일. 지금 분석 중인 파일이라는 뜻이 아니다
  // (CaseView에는 파일별 진행이 없다).
  const representative = props.files.find((f) => !props.skipped?.includes(f.name)) ?? null
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
      <div className="flow-main">
        <div className="flow-head" aria-live="polite">
          {current && <p className="flow-overall">{overall}</p>}
          {/* key가 바뀌면 다시 그려져 제목이 부드럽게 바뀐다 */}
          <h1 className="rs-title flow-now" key={current ?? 'overall'}>
            {current ? stepLabel(current) : overall}
          </h1>
          <div className="flow-status-row">
            <p className={`flow-status${currentState ? ` is-${currentState.toLowerCase()}` : ''}`}>
              {currentState && (
                <>
                  <span className="flow-status-mark" aria-hidden />
                  {CURRENT_STEP_STATE[currentState]}
                </>
              )}
            </p>
            <p className="flow-elapsed">
              경과 시간 <span>{elapsed}</span>
            </p>
          </div>
          {continuing && (
            <p className="flow-partial">
              <span className="flow-partial-mark" aria-hidden />
              {failed.length === 1 ? stepFailedLabel(failed[0].step) : SOME_STEPS_FAILED} {OTHERS_CONTINUING}
            </p>
          )}
        </div>

        <VideoThumb file={representative} name={representative?.name ?? props.files[0]?.name ?? ''} />

        {props.files.length > 1 && (
          // 여러 파일은 접어 둔다. open은 브라우저가 들고 있어 단계가 바뀌어 다시 그려져도 유지된다.
          <details className="flow-files">
            <summary>
              {videoCount(props.files.length)}
              <ChevronDown size={16} strokeWidth={1.8} aria-hidden />
            </summary>
            <ul>
              {props.files.map((f, i) => (
                <li key={`${f.name}-${i}`}>{f.name}</li>
              ))}
            </ul>
          </details>
        )}

        {props.situation && (
          <section className="flow-situation">
            <h2>{SITUATION_HEADING}</h2>
            <p>“{props.situation}”</p>
          </section>
        )}
      </div>

      <div className="flow-steps">
        <ProgressPanel
          view={props.view}
          jobs={screen.jobs}
          heading={
            <>
              <span>{STEPS_HEADING}</span>
              <span className="flow-steps-count">{stepCount(props.view.progress.length)}</span>
            </>
          }
        />
      </div>
    </div>
  )
}
