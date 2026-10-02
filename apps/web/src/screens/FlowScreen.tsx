import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type JSX } from 'react'
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
const TITLE_OUT_MS = 260
// 진입 연출이 끝나는 시간 — 그 안에 장면 찾기가 시작되면 빛은 연출이 끝난 뒤에 지나간다.
const ENTER_MS = 450

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
  const rootRef = useRef<HTMLDivElement>(null)
  const mountedAt = useRef(Date.now())
  // 「영상에서 찾아보기」가 사라져 포커스가 갈 곳을 잃으면 진행 화면이 받는다(보이는 요소).
  useEffect(() => {
    if (!document.activeElement || document.activeElement === document.body)
      rootRef.current?.focus({ preventScroll: true })
  }, [])
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

  // 큰 제목 전환 — 새 제목이 나타나는 동안 이전 제목이 같은 자리에서 짧게 사라진다(빈 순간 없음).
  // 이전 제목은 장식이라 읽지 않게 숨기고, 빠르게 바뀌면 가장 최근 것만 남긴다.
  const titleText = current ? stepLabel(current) : overall
  const shownTitle = useRef(titleText)
  const [leaving, setLeaving] = useState<{ text: string; id: number } | null>(null)
  useLayoutEffect(() => {
    if (shownTitle.current === titleText) return
    setLeaving({ text: shownTitle.current, id: Date.now() })
    shownTitle.current = titleText
  }, [titleText])
  useEffect(() => {
    if (!leaving) return
    const t = setTimeout(() => setLeaving(null), TITLE_OUT_MS)
    return () => clearTimeout(t)
  }, [leaving])

  // 장면 찾기 시작 장식 — coarse_search가 실제로 RUNNING이 되는 순간 한 번. 단계가 끝나면 지운다.
  const scanning = props.view.progress.some((p) => p.step === 'coarse_search' && p.state === 'RUNNING')
  const [scan, setScan] = useState<{ id: number; delayMs: number } | null>(null)
  useEffect(() => {
    if (!scanning) return setScan(null)
    const now = Date.now()
    setScan({ id: now, delayMs: Math.max(0, ENTER_MS - (now - mountedAt.current)) })
  }, [scanning])

  // 진행 중 강조 면 — 진행 중인 단계가 정확히 하나일 때만 면 하나가 그 행으로 옮겨 간다.
  // 이웃 행으로 넘어갈 때만 미끄러지고, 건너뛰면 그 자리에 바로 나타난다(지나친 행을 진행
  // 중처럼 보이지 않게). 여럿이 동시에 진행 중이면 각 행이 따로 강조된다(CSS). 하나도 없으면
  // 면을 숨긴다 — 끝난 단계를 진행 중처럼 남기지 않는다.
  const runningIdx = props.view.progress.flatMap((p, i) => (p.state === 'RUNNING' ? [i] : []))
  const single = runningIdx.length === 1 ? runningIdx[0] : -1
  const stepsRef = useRef<HTMLDivElement>(null)
  const [hl, setHl] = useState<{ top: number; height: number; index: number; slide: boolean } | null>(null)
  useLayoutEffect(() => {
    const root = stepsRef.current
    const li = single < 0 ? null : root?.querySelectorAll<HTMLElement>('.timeline > li')[single]
    if (!root || !li) {
      setHl(null)
      return
    }
    const top = li.getBoundingClientRect().top - root.getBoundingClientRect().top
    setHl((prev) => ({
      top,
      height: li.offsetHeight,
      index: single,
      slide: !!prev && Math.abs(prev.index - single) === 1,
    }))
  }, [single, props.view.progress.length])
  return (
    <div className="rs rs-enter flow" ref={rootRef} tabIndex={-1}>
      {/* 위: 현재 작업·상태·안내(두 칸 전체). 아래 행에 대표 영상과 단계 목록이 같은 높이에서 시작한다 */}
      <div className="flow-head" aria-live="polite">
        {current && <p className="flow-overall">{overall}</p>}
        <div className="flow-now-box">
          {leaving && (
            <span className="rs-title flow-now-leaving" key={leaving.id} aria-hidden>
              {leaving.text}
            </span>
          )}
          {/* key가 바뀌면 다시 그려져 새 제목이 부드럽게 나타난다 */}
          <h1 className="rs-title flow-now" key={current ?? 'overall'}>
            {titleText}
          </h1>
        </div>
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
        {/* 안내 한 줄 자리는 늘 비워 둔다 — 안내가 나타나거나 사라져도 아래 영상·단계 목록이
            밀리지 않는다. 문구가 길어 줄이 바뀌면 그만큼만 늘어난다(자르지 않음) */}
        <div className="flow-partial-slot">
          {continuing && (
            <p className="flow-partial">
              <span className="flow-partial-mark" aria-hidden />
              {failed.length === 1 ? stepFailedLabel(failed[0].step) : SOME_STEPS_FAILED} {OTHERS_CONTINUING}
            </p>
          )}
        </div>
      </div>

      <div className="flow-main">
        <VideoThumb file={representative} name={representative?.name ?? props.files[0]?.name ?? ''} scan={scan} />

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

      <div
        className="flow-steps"
        ref={stepsRef}
        data-running={runningIdx.length === 0 ? 'none' : runningIdx.length === 1 ? 'one' : 'many'}
      >
        <span
          className={`flow-step-hl${hl ? ' on' : ''}${hl?.slide ? ' slide' : ''}`}
          style={hl ? ({ transform: `translateY(${hl.top}px)`, height: hl.height } as CSSProperties) : undefined}
          aria-hidden
        />
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
