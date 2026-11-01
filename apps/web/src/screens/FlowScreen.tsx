import { useEffect, useLayoutEffect, useRef, useState, type JSX } from 'react'
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
import { SearchFx } from '../components/SearchFx'
import carTop from '../assets/car/car-top.webp'

// Figma 02_Main_Flow · 02_Retry_Flow · 02_Fail_Flow. 세 프레임은 같은 틀이고
// 단계 상태(progress)와 알림(notices)만 다르다 — 둘 다 CaseView에서 온다.
// 진행 화면에는 버튼이 없다. 실패한 단계는 목록에서 빨갛게 칠하고, 다른 단계가 실제로
// RUNNING일 때만 「나머지 작업은 계속하고 있어요」를 한 줄 붙인다. 전체 작업이 멈췄는지는
// 화면이 RUNNING 유무로 단정하지 않는다 — 단계 사이에도 RUNNING이 잠깐 없을 수 있다.
// 멈춤은 blocking notice(계약 B절 notices[].blocking)로만 알 수 있고, 그때는 이 안내를
// 내지 않는다. 무슨 일이 있었는지는 실패·결과 화면에서 알린다. 버튼은 [분석 중단] 하나뿐이고,
// 중단할 수 있을 때만 부모가 `onStop`을 준다(STOP_ANALYSIS, #342).
//
// 가장 크게 보이는 제목은 지금 RUNNING인 단계의 이름이다(progress에서 그대로 읽는다).
// 단계 사이처럼 RUNNING이 잠깐 없을 때는 마지막으로 진행하던 단계를 그대로 두어 제목이
// 흔들리지 않게 한다. 아직 한 단계도 시작하지 않았을 때만 전체 흐름 문구를 제목으로 쓴다.
const TITLE_OUT_MS = 260
// 위에서 본 자동차(car-top.webp, 앞이 아래) 표시 크기 — 이미지 여백을 빼면 보이는 차는 약 23×49
const CAR_H = 53

export function FlowScreen(props: {
  view: CaseView
  /** 올린 영상들. 브라우저에 원본(File)이 있으면 대표 영상 정지 화면을 그린다 */
  files: { name: string }[]
  /** 업로드가 열 수 없어 건너뛴 파일 이름 — 대표 영상에서 뺀다 */
  skipped?: string[]
  situation: string
  startedAt: number
  title?: string
  /** 업로드 화면에서 자동차가 출발하며 넘어올 때 — 오른쪽에서 밀려 들어온다(처음 그릴 때만 본다) */
  pushIn?: boolean
  onStop?: () => void
}): JSX.Element {
  const screen = selectScreen(props.view)
  const [enter] = useState(() => (props.pushIn ? 'rs-push-in' : 'rs-enter'))
  const rootRef = useRef<HTMLDivElement>(null)
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

  // 세로 경로 위 자동차 — 위치는 실제 단계 상태로만 정한다. 진행 중 단계 중 가장 앞(위) 단계 옆에
  // 서고, 진행 중이 잠깐 없으면 마지막 위치에서 기다린다(재시도로 앞 단계가 다시 진행되면 돌아간다).
  // 처음 열 때 진행 중이 없으면 이미 지난 마지막 단계 옆에서 시작한다 — 첫 단계부터 가짜로 달리지 않는다.
  // 시간이 흐른다고 움직이지 않으며, 진행률·남은 시간·도착을 뜻하지 않는다.
  const progress = props.view.progress
  const firstRunning = progress.findIndex((p) => p.state === 'RUNNING')
  const carAt = useRef<number | null>(null)
  if (firstRunning >= 0) carAt.current = firstRunning
  else if (carAt.current === null) {
    let reached = -1
    progress.forEach((p, i) => {
      if (p.state !== 'PENDING') reached = i
    })
    carAt.current = Math.max(0, reached)
  }
  const carIndex = progress.length > 0 ? Math.min(carAt.current, progress.length - 1) : null
  const stepsRef = useRef<HTMLDivElement>(null)
  const [stops, setStops] = useState<number[]>([])
  useLayoutEffect(() => {
    const root = stepsRef.current
    if (!root) return
    const measure = () => {
      const top = root.getBoundingClientRect().top
      setStops([...root.querySelectorAll<HTMLElement>('.timeline > li')].map((li) => {
        const marker = li.querySelector<HTMLElement>('.scene-search-mark')
        const r = (marker ?? li).getBoundingClientRect()
        return r.top - top + r.height / 2
      }))
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(root)
    return () => observer.disconnect()
  }, [progress.length])
  const carY = carIndex !== null && stops[carIndex] !== undefined ? stops[carIndex] - CAR_H / 2 : null

  return (
    <div className={`rs ${enter} flow`} ref={rootRef} tabIndex={-1}>
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
        <VideoThumb
          file={representative instanceof File ? representative : null}
          name={representative?.name ?? props.files[0]?.name ?? ''}
          overlay={running === 'coarse_search' && <SearchFx />}
        />

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

        {props.onStop && (
          <div className="flow-stop-row">
            <button type="button" className="rs-btn sec" onClick={props.onStop}>
              분석 중단
            </button>
          </div>
        )}
      </div>

      <div className="flow-steps" ref={stepsRef}>
        {stops.length > 0 && (
          <div className="flow-lane" aria-hidden>
            <span className="flow-lane-line" style={{ top: stops[0], height: stops[stops.length - 1] - stops[0] }} />
            {stops.map((y, i) => (
              <span key={i} className="flow-stop" style={{ top: y }} />
            ))}
            {carY !== null && (
              <span className="flow-car" data-step={carIndex ?? undefined} style={{ transform: `translateY(${carY}px)` }}>
                <img src={carTop} alt="" />
              </span>
            )}
          </div>
        )}
        <ProgressPanel
          view={props.view}
          sceneNow={now}
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
