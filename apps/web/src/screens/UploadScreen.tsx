import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type JSX } from 'react'
import { ChevronDown, CircleAlert } from 'lucide-react'
import carSide from '../assets/car/car-side.webp'
import carDoorOpen from '../assets/car/car-door-open.webp'
import frontBack from '../assets/car/wheel-front-back.webp'
import frontSpin from '../assets/car/wheel-front-spin.webp'
import frontBlur from '../assets/car/wheel-front-blur.webp'
import rearBack from '../assets/car/wheel-rear-back.webp'
import rearSpin from '../assets/car/wheel-rear-spin.webp'
import rearBlur from '../assets/car/wheel-rear-blur.webp'
import { Puffs, SpeedLines, burst, seeded, type Puff, type Speed } from '../components/CarFx'

const EXAMPLE = '6시 반쯤 미금역 근처에서 흰색 SUV가 실선을 넘어 제 앞으로 끼어들었어요.'

export type UploadState = 'idle' | 'uploading' | 'done' | 'fail'

const DROP_TEXT: Record<Exclude<UploadState, 'done'>, string> = {
  idle: '여기에 영상 파일을 끌어다 놓으세요',
  uploading: '업로드 중',
  fail: '업로드 실패',
}

// 첫 진입 효과는 페이지를 처음 열 때 한 번만 — 「새 신고」로 돌아올 때는 다시 하지 않는다.
let introPlayed = false
const INTRO_MS = 700

// ── 자동차 장면 ────────────────────────────────────────────────
// 원본 car-side.webp(1774×887, 앞이 왼쪽) 한 장의 위치·배율만 바꿔 문과 앞바퀴를 보인다 —
// 정지 이미지의 이동·확대이지 3D 카메라 이동이 아니다. 문 열림은 열림 사진(car-door-open)을
// 원본의 문 위치(원본 사진 1448px 기준 배율 .388·원점 466,274)에 겹친 임시 표현이고 실제 회전이
// 아니다.
//
// 휠은 같은 원본에서 나눈 두 층을 원본 위 같은 자리에 겹친다 — 고정 층(디스크·캘리퍼·타이어 옆면)과
// 도는 층(휠살·림·허브·너트). 도는 층은 휠살이 5번 반복되는 성질로 5곳을 겹쳐 캘리퍼를 뺀 것이라
// 사진 전체를 돌리지 않는다. 차체·캘리퍼·바닥 그림자는 그대로다. 빠르게 돌 때(출발)는 같은 층을 한 바퀴
// 평균한 흐린 층으로 넘어간다. 업로드 중 회전 속도는 일정하며 진행률·남은 시간을 뜻하지 않는다.
const SCENE_H = 320
const VIEW = {
  door: { x: 735, y: 440, span: 440 },
  hover: { x: 735, y: 440, span: 415 },
  wheel: { x: 340, y: 600, span: 400 },
  /** 출발 장면 — 자동차 전체 */
  whole: { x: 887, y: 470, span: 820 },
}
type View = keyof typeof VIEW
const OPEN_FIT = { x: 466, y: 274, s: (0.388 * 1448) / 900 }
// 업로드 연출: 카드 탑승 → 문 닫힘 → 닫힌 상태 → 바퀴로 이동(이동 자체는 CSS 0.35초).
// 실제 업로드는 접수 즉시 시작하고, 완료·실패가 먼저 오면 그 자리에서 최신 상태로 바뀐다.
const BOARD_MS = 300
const CLOSE_MS = 150
const HOLD_MS = 50
type Phase = 'boarding' | 'closing' | 'wheel' | null
// 원본 기준 휠 층 위치(243px 정사각, 가운데가 휠 중심)와 타이어 반지름
const WHEELS = {
  front: { x: 200.5, y: 509.5, back: frontBack, spin: frontSpin, blur: frontBlur },
  rear: { x: 1265, y: 509.5, back: rearBack, spin: rearSpin, blur: rearBlur },
}
const TIRE_R = 123
// 출발 — 차가 장면 안에서 앞(왼쪽)으로 달려 나가는 거리. 휠은 같은 시간·같은 가속으로 이 거리만큼
// 구른다(미끄러지지 않는 회전각 = 거리 ÷ 화면 속 타이어 반지름).
const DEPART_PX = 1000
// 출발 전 제자리에서 헛도는 만큼(휠스핀) 더 돈다
const BURNOUT_DEG = -900
const DEPART_ROLL_DEG = (-DEPART_PX / (TIRE_R * (SCENE_H / VIEW.whole.span)) / Math.PI) * 180 + BURNOUT_DEG
const GHOSTS = [1, 2, 3]

// 출발 연기·속도선 — 원본 좌표(ox, oy)를 출발 장면(칸 너비 width, 높이 320) 좌표로 옮겨 놓는다.
// 시간(ms)은 refresh.css의 출발 타임라인과 맞춘다: 시동 진동 100~450 · 배기 120~ · 휠스핀 연기 300~ · 출발 450~970
function departFx(width: number): { puffs: Puff[]; lines: Speed[] } {
  const s = SCENE_H / VIEW.whole.span
  const at = (ox: number, oy: number) => ({ x: width / 2 + (ox - VIEW.whole.x) * s, y: SCENE_H / 2 + (oy - VIEW.whole.y) * s })
  const puffs = [
    // 배기 — 뒤범퍼 아래에서 작게 뭉게뭉게
    ...burst(6, at(1700, 690), { from: 120, gap: 70, size: [16, 24], dx: [24, 60], dy: [-26, -10], t: 760, g: 2.4, seed: 7 }),
    // 휠스핀 — 뒷바퀴 바닥에서 크게 터진다
    ...burst(16, at(1386, 745), { from: 300, gap: 26, size: [36, 64], dx: [50, 150], dy: [-64, -18], t: 900, g: 3.2, seed: 11 }),
    // 앞바퀴도 조금
    ...burst(5, at(322, 745), { from: 360, gap: 40, size: [24, 36], dx: [30, 80], dy: [-36, -12], t: 700, g: 2.6, seed: 13 }),
  ]
  const r = seeded(17)
  const lines = Array.from({ length: 9 }, (_, i) => ({
    x: at(300 + r() * 1300, 0).x,
    y: at(0, 260 + r() * 420).y,
    w: 60 + r() * 110,
    d: 520 + i * 45,
  }))
  return { puffs, lines }
}

function Wheel(props: { at: keyof typeof WHEELS }): JSX.Element {
  const w = WHEELS[props.at]
  return (
    <span className="rs-wheel" style={{ left: w.x, top: w.y }}>
      <img className="rs-wheel-back" src={w.back} alt="" />
      <img className="rs-wheel-spin" src={w.spin} alt="" />
      <img className="rs-wheel-blur" src={w.blur} alt="" />
    </span>
  )
}

function sceneTransform(view: View, width: number): string {
  const f = VIEW[view]
  const s = SCENE_H / f.span
  return `translate(${width / 2 - f.x * s}px, ${SCENE_H / 2 - f.y * s}px) scale(${s})`
}

// Figma 01_Home_Upload · 01_Uploading · 01_UploadComplete · 01_UploadFail.
// 업로드 칸 = 자동차 앞문. 커서나 파일이 칸에 들어오면 문이 열리고(접수 전만), 파일을 놓거나
// 고르면 한 번 접수한다. 파일 고르기는 칸 안의 버튼 하나로만 키보드가 멈춘다 — 칸 클릭은 고르기
// 전(idle)과 실패 때만 쓰는 마우스용 지름길이다. 버튼은 모든 상태에서 같은 요소로 남아(문구·모양만
// 바뀜) 업로드가 끝나 칸이 바뀌어도 키보드 포커스가 사라지지 않는다.
//
// 업로드가 끝나면(done) 그림이 접히고 한 줄 요약이 남는다. 「영상에서 찾아보기」를 누르면
// (departing — DemoFlow의 겉모습 복사본에서만) 이전 업로드 칸 자리에 같은 자동차 전체가 나타나
// 휠이 구르며 앞(왼쪽)으로 출발한다. 칸이 다시 펼쳐지지 않으므로 입력칸을 밀지 않는다.
export function UploadScreen(props: {
  state: UploadState
  /** 이름만 쓴다 — 시연은 고른 `File`을, `?api`는 업로드 결과 목록을 그대로 넘긴다 */
  files: { name: string }[]
  /** 열 수 없어 건너뛴 파일. 일부 실패를 전체 실패로 만들지 않는다(core-user-flow §23) */
  skipped: string[]
  situation: string
  onFiles: (files: File[]) => void
  onSituation: (text: string) => void
  onSearch: () => void
  /** 분석 시작 직후 화면이 빠지는 동안 — 자동차가 출발한다(누를 수 없는 복사본에서만 쓴다) */
  departing?: boolean
}): JSX.Element {
  const [over, setOver] = useState(false)
  const [pointerIn, setPointerIn] = useState(false)
  const [intro, setIntro] = useState(!introPlayed)
  useEffect(() => {
    introPlayed = true
    const t = setTimeout(() => setIntro(false), INTRO_MS)
    return () => clearTimeout(t)
  }, [])
  const input = useRef<HTMLInputElement>(null)
  const choose = () => input.current?.click()
  const pick = (files: FileList | null) => {
    if (files?.length) props.onFiles([...files])
  }
  const { state } = props

  // 연출 단계 — 실제 업로드 상태(state)와 따로 둔다. 업로드가 새로 시작될 때마다(파일 교체 포함)
  // 처음부터 다시 하고, 업로드 중이 아니면 바로 지운다.
  const [phase, setPhase] = useState<Phase>(null)
  useEffect(() => {
    if (state !== 'uploading') return setPhase(null)
    setPhase('boarding')
    const a = setTimeout(() => setPhase('closing'), BOARD_MS)
    const b = setTimeout(() => setPhase('wheel'), BOARD_MS + CLOSE_MS + HOLD_MS)
    return () => {
      clearTimeout(a)
      clearTimeout(b)
    }
  }, [state, props.files])

  // 장면의 폭(칸 너비)만 따라간다 — 높이는 설계값이라 칸이 접혀도 배율이 흔들리지 않는다.
  const scene = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(720)
  useLayoutEffect(() => {
    const el = scene.current
    if (el?.clientWidth) setWidth(el.clientWidth) // 첫 그림부터 맞는 자리(출발 장면이 튀지 않게)
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth || 720))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const open = phase === 'boarding' || (state === 'idle' && (over || pointerIn))
  const view: View = phase === 'wheel' ? 'wheel' : state === 'idle' && open ? 'hover' : 'door'
  // 실패는 이동을 멈춘 그 자리에서 — 직전 값을 그대로 둔다.
  const transform = sceneTransform(view, width)
  const shown = useRef(transform)
  if (state !== 'fail') shown.current = transform
  // 이동 중에 실패하면 그 자리에서 멈춘다 — 지금 그려진 위치를 읽어 전환 없이 고정한다.
  const carImg = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const el = carImg.current
    if (state !== 'fail' || !el) return
    const now = getComputedStyle(el).transform
    el.style.transition = 'none'
    if (now && now !== 'none') el.style.transform = now
    return () => {
      el.style.transition = ''
    }
  }, [state])
  // 바퀴로 이동하는 순간부터 완료·실패까지 배경 차를 숨긴다(두 대처럼 보이지 않게).
  const bgOff = phase === 'wheel' || state === 'done' || state === 'fail'
  // 휠은 바퀴 화면에 도착한 뒤 업로드가 끝날 때까지만 돈다. 끝나거나 실패하면 그 각도에서 멈춘다.
  const spinning = phase === 'wheel'
  const fx = props.departing ? departFx(width) : null

  const okCount = props.files.filter((f) => !props.skipped.includes(f.name)).length
  const title = state === 'done' ? `업로드 완료 · 영상 ${okCount}개` : DROP_TEXT[state]
  const canClickArea = state === 'idle' || state === 'fail'
  const names = props.files.map((f) => f.name).join(', ')
  const fileList = (
    <ul className="rs-files">
      {props.files.map((f, i) => (
        <li key={`${f.name}-${i}`}>
          <span>{f.name}</span>
        </li>
      ))}
    </ul>
  )

  return (
    <div
      className={`rs upload is-${state}${intro ? ' rs-intro' : ''}${props.departing ? ' is-departing' : ''}${bgOff ? ' bg-off' : ''}`}
    >
      <div className="rs-group" style={{ '--i': 0 } as CSSProperties}>
        <h1 className="rs-title">블랙박스 영상을 올려주세요</h1>
        <p className="rs-lede">
          신호위반 · 중앙선 침범 · 진로변경 · 이륜차 안전모 미착용 장면을 찾아 드려요.
          <br />
          찾은 장면은 신고할 가능성이 있는 후보예요. 제출 전에 꼭 직접 확인해 주세요.
        </p>
      </div>

      <div className="rs-group g-drop" style={{ '--i': 1 } as CSSProperties}>
        {/* 같은 원본을 은은하게 깐 자동차 전체 — 업로드 칸 가운데, 칸 높이 안에서 */}
        <img className="rs-bgcar" src={carSide} alt="" aria-hidden />
        <div
          className={`rs-drop is-${state}${over ? ' over' : ''}${open ? ' is-open' : ''}${spinning ? ' is-spinning' : ''}`}
          onClick={canClickArea ? choose : undefined}
          onPointerEnter={() => setPointerIn(true)}
          onPointerLeave={() => setPointerIn(false)}
          onDragOver={(e) => {
            e.preventDefault()
            setOver(true)
          }}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false)
          }}
          onDrop={(e) => {
            e.preventDefault()
            setOver(false)
            pick(e.dataTransfer.files)
          }}
        >
          <div className="rs-scene" ref={scene} aria-hidden>
            {/* 원본 좌표 그대로의 판 — 차·앞휠·문 열림이 함께 옮겨진다 */}
            <div ref={carImg} className="rs-rig" style={{ transform: shown.current }}>
              <img className="rs-scene-car" src={carSide} alt="" />
              <Wheel at="front" />
              <img
                className="rs-scene-open"
                src={carDoorOpen}
                alt=""
                style={{ transform: `translate(${OPEN_FIT.x}px, ${OPEN_FIT.y}px) scale(${OPEN_FIT.s})` }}
              />
            </div>
            {phase === 'boarding' && (
              // 영상 카드 — 열린 입구(실내) 쪽으로 작아지며 들어간다. 최대 3장, 개수는 문구로 정확히.
              <div className="rs-cards" key={names}>
                {props.files.slice(0, 3).map((f, i) => (
                  <span
                    key={`${f.name}-${i}`}
                    className="rs-vcard"
                    style={{ '--d': `${i * 30}ms`, '--x': `${i * 20}px` } as CSSProperties}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="rs-cap">
            {state === 'done' && <span className="rs-mini-car" aria-hidden />}
            {state === 'done' ? (
              <div className="rs-done-text">
                <span className="rs-done-badge" aria-hidden>
                  {/* 업로드 성공 — 체크 선이 한 번 그려진다(pathLength=1이라 CSS로 0→1을 그린다) */}
                  <svg
                    className="rs-check"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.4}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M5 12.5l4.5 4.5L19 7.5" pathLength={1} />
                  </svg>
                </span>
                {props.files.length > 1 ? (
                  <details className="rs-done-files">
                    <summary>
                      <b className="rs-drop-title" aria-live="polite">
                        {title}
                      </b>
                      <ChevronDown size={16} strokeWidth={1.8} aria-hidden />
                    </summary>
                    {fileList}
                  </details>
                ) : (
                  <span className="rs-done-one">
                    <b className="rs-drop-title" aria-live="polite">
                      {title}
                    </b>
                    <span className="rs-done-name">{props.files[0]?.name}</span>
                  </span>
                )}
              </div>
            ) : (
              <div className="rs-cap-text">
                <b className="rs-drop-title" aria-live="polite">
                  {state === 'uploading' && <span className="rs-spin-sm" aria-hidden />}
                  {state === 'fail' && <CircleAlert size={18} strokeWidth={1.8} aria-hidden />}
                  {title}
                </b>
                {state === 'idle' && (
                  <span className="rs-drop-note">여러 파일도 한 번에 올릴 수 있어요. 촬영 시각 정보도 확인해요.</span>
                )}
                {state === 'uploading' && (
                  // 칸 높이를 지키려고 업로드 중 파일 이름은 한 줄. 전체 이름은 완료 요약에 남는다.
                  <span className="rs-drop-note one" title={names}>
                    {names}
                  </span>
                )}
                {/* 원인(형식·손상·네트워크)을 단정하지 않는다 — 화면은 알 수 없다(#224 recording 리뷰) */}
                {state === 'fail' && <span className="rs-drop-note">파일을 올리지 못했어요. 다시 골라 주세요.</span>}
              </div>
            )}
            <button
              type="button"
              // 고르기 전·실패 때는 주 동작, 고른 뒤에는 「영상에서 찾아보기」가 주 동작이라 보조로 낮춘다.
              className={`rs-btn ${canClickArea ? 'pri' : 'sec'}`}
              onClick={(e) => {
                e.stopPropagation()
                choose()
              }}
            >
              {state === 'idle' ? '파일 선택' : '다시 선택'}
            </button>
          </div>
          <input
            ref={input}
            type="file"
            accept="video/*"
            multiple
            hidden
            onChange={(e) => {
              pick(e.target.files)
              // 같은 파일을 다시 골라도 change가 나도록 비운다.
              e.target.value = ''
            }}
          />
        </div>
        {props.departing && (
          // 출발 장면 — 이전 업로드 칸 자리에 겹쳐 그린다(아래 요소를 밀지 않음).
          <div className="rs-depart" aria-hidden>
            {/* 잔상 — 같은 차가 조금씩 늦게 따라가며 흐려진다 */}
            {GHOSTS.map((g) => (
              <div key={g} className="rs-depart-car is-ghost" style={{ '--go': `${-DEPART_PX}px`, '--gd': `${g * 45}ms` } as CSSProperties}>
                <div className="rs-rig" style={{ transform: sceneTransform('whole', width) }}>
                  <img className="rs-scene-car" src={carSide} alt="" />
                </div>
              </div>
            ))}
            <div className="rs-depart-car" style={{ '--roll': `${DEPART_ROLL_DEG}deg`, '--go': `${-DEPART_PX}px` } as CSSProperties}>
              <div className="rs-depart-body">
                <div className="rs-rig" style={{ transform: sceneTransform('whole', width) }}>
                  <img className="rs-scene-car" src={carSide} alt="" />
                  <Wheel at="front" />
                  <Wheel at="rear" />
                </div>
              </div>
            </div>
            {fx && <Puffs items={fx.puffs} />}
            {fx && <SpeedLines items={fx.lines} />}
          </div>
        )}
        {state === 'done' && props.skipped.length > 0 && (
          <p className="skip-list">
            올리지 못했거나 열 수 없는 파일 {props.skipped.length}개는 건너뛰었어요: {props.skipped.join(', ')}. 나머지
            영상으로 찾아볼게요.
          </p>
        )}
      </div>

      <div className="rs-group" style={{ '--i': 2 } as CSSProperties}>
        <label className="rs-field">
          <span className="rs-label">어떤 상황이었나요?</span>
          <SituationInput
            label="어떤 상황이었나요?"
            example={EXAMPLE}
            rows={4}
            value={props.situation}
            onChange={props.onSituation}
          />
          <span className="rs-hint">Tab 키를 누르면 예시 문장이 들어가요. 비워 두셔도 영상에서 찾아볼게요.</span>
        </label>

        <div className="rs-actions">
          <button type="button" className="rs-btn pri lg" disabled={state !== 'done'} onClick={props.onSearch}>
            영상에서 찾아보기
          </button>
        </div>
      </div>
    </div>
  )
}

// 상황 설명 입력칸. 비어 있을 때만 Tab이 예시를 채운다 — 글이 있으면 원래 Tab(다음 칸으로 이동)이다.
export function SituationInput(props: {
  label: string
  example: string
  rows: number
  value: string
  onChange: (text: string) => void
}): JSX.Element {
  return (
    <textarea
      className="field situation"
      rows={props.rows}
      aria-label={props.label}
      placeholder={`예: ${props.example}`}
      value={props.value}
      onChange={(e) => props.onChange(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Tab' && !e.shiftKey && !props.value) {
          e.preventDefault()
          props.onChange(props.example)
        }
      }}
    />
  )
}
