import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type JSX } from 'react'
import { ChevronDown, CircleAlert, FileVideo, Upload } from 'lucide-react'

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

// 업로드 영역 높이가 내용(안내 문구 ↔ 파일 목록)에 따라 바뀔 때 갑자기 튀지 않도록,
// 바깥 높이를 안쪽 높이에 맞춰 주고 CSS transition으로 잇는다. 테두리 두께만큼 더한다.
function useAutoHeight<T extends HTMLElement>(border: number) {
  const inner = useRef<T>(null)
  const [height, setHeight] = useState<number>()
  useLayoutEffect(() => {
    const el = inner.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setHeight(el.offsetHeight + border * 2))
    ro.observe(el)
    return () => ro.disconnect()
  }, [border])
  return { inner, height }
}

// Figma 01_Home_Upload · 01_Uploading · 01_UploadComplete · 01_UploadFail.
// 네 프레임은 같은 틀이고 끌어다 놓는 영역만 상태에 따라 바뀐다.
// 파일 고르기는 영역 안의 버튼 하나로만 키보드가 멈춘다 — 영역 클릭은 고르기 전(idle)과
// 실패 때만 쓰는 마우스용 지름길이고, 파일 입력칸은 숨겨 두어 Tab이 두 번 서지 않는다.
// 버튼은 모든 상태에서 같은 요소로 남는다(문구·모양만 바뀜) — 업로드가 끝나 영역이 바뀌어도
// 키보드 포커스가 사라지지 않는다.
//
// 업로드가 끝나면(done) 큰 영역이 한 줄 요약으로 줄어든다. 높이는 useAutoHeight로 잇는다.
// 파일이 여럿이면 요약 제목을 눌러 목록을 펼친다.
export function UploadScreen(props: {
  state: UploadState
  files: File[]
  /** 열 수 없어 건너뛴 파일. 일부 실패를 전체 실패로 만들지 않는다(core-user-flow §23) */
  skipped: string[]
  situation: string
  onFiles: (files: File[]) => void
  onSituation: (text: string) => void
  onSearch: () => void
}): JSX.Element {
  const [over, setOver] = useState(false)
  const [intro, setIntro] = useState(!introPlayed)
  useEffect(() => {
    introPlayed = true
    const t = setTimeout(() => setIntro(false), INTRO_MS)
    return () => clearTimeout(t)
  }, [])
  const box = useAutoHeight<HTMLDivElement>(1.5)
  const input = useRef<HTMLInputElement>(null)
  const choose = () => input.current?.click()
  const pick = (files: FileList | null) => {
    if (files?.length) props.onFiles([...files])
  }
  const { state } = props
  const okCount = props.files.filter((f) => !props.skipped.includes(f.name)).length
  const title = state === 'done' ? `업로드 완료 · 영상 ${okCount}개` : DROP_TEXT[state]
  const canClickArea = state === 'idle' || state === 'fail'
  const fileList = (
    <ul className="rs-files">
      {props.files.map((f, i) => (
        <li key={`${f.name}-${i}`}>
          <FileVideo size={16} strokeWidth={1.8} aria-hidden />
          <span>{f.name}</span>
        </li>
      ))}
    </ul>
  )

  return (
    <div className={`rs upload is-${state}${intro ? ' rs-intro' : ''}`}>
      <div className="rs-group" style={{ '--i': 0 } as CSSProperties}>
        <h1 className="rs-title">블랙박스 영상을 올려주세요</h1>
        <p className="rs-lede">
          신호위반 · 중앙선 침범 · 진로변경 · 이륜차 안전모 미착용 장면을 찾아 드려요.
          <br />
          찾은 장면은 신고할 가능성이 있는 후보예요. 제출 전에 꼭 직접 확인해 주세요.
        </p>
      </div>

      <div className="rs-group" style={{ '--i': 1 } as CSSProperties}>
        <div
          className={`rs-drop is-${state}${over ? ' over' : ''}`}
          style={{ height: box.height }}
          onClick={canClickArea ? choose : undefined}
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
          <div className="rs-drop-in" ref={box.inner}>
            {state === 'done' ? (
              <div className="rs-drop-body rs-done rs-appear" key="done">
                <span className="rs-drop-icon" aria-hidden>
                  {/* 업로드 성공 — 체크 선이 한 번 그려진다(pathLength=1이라 CSS로 0→1을 그린다) */}
                  <svg
                    className="rs-check"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M5 12.5l4.5 4.5L19 7.5" pathLength={1} />
                  </svg>
                </span>
                <div className="rs-done-text">
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
                    <>
                      <b className="rs-drop-title" aria-live="polite">
                        {title}
                      </b>
                      <span className="rs-done-name">{props.files[0]?.name}</span>
                    </>
                  )}
                </div>
              </div>
            ) : (
              <div className="rs-drop-body" key="big">
                {state === 'uploading' ? (
                  // 나타나기(rs-pop)와 회전(rs-spin)은 둘 다 transform이라 한 요소에 두면 회전이 덮인다 — 나눈다.
                  <span className="rs-spin" aria-hidden>
                    <span className="rs-spin-arc" />
                  </span>
                ) : (
                  <span className="rs-drop-icon" aria-hidden key={`icon-${state}`}>
                    {state === 'fail' ? (
                      <CircleAlert size={24} strokeWidth={1.8} />
                    ) : (
                      <Upload size={24} strokeWidth={1.8} />
                    )}
                  </span>
                )}
                <b className="rs-drop-title" aria-live="polite">
                  {title}
                </b>
                {state === 'idle' && (
                  <span className="rs-drop-note">여러 파일도 한 번에 올릴 수 있어요. 촬영 시각은 자동으로 읽어요.</span>
                )}
                {state === 'fail' && (
                  <span className="rs-drop-note">이 파일은 열 수 없어요. 다른 파일을 골라 주세요.</span>
                )}
                {props.files.length > 0 && <div className="rs-appear">{fileList}</div>}
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
        </div>
        {state === 'done' && props.skipped.length > 0 && (
          <p className="skip-list">
            열 수 없는 파일 {props.skipped.length}개는 건너뛰었어요: {props.skipped.join(', ')} — 지원하지 않는
            형식이거나 손상된 파일이에요. 나머지 영상으로 찾아볼게요.
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
