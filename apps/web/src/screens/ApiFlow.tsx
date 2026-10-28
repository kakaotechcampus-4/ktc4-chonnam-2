import { useEffect, useRef, useState, type JSX } from 'react'
import { createApi, type Api, type Command } from '../api/client'
import { AppHeader } from '../components/AppHeader'
import { isAction, type Action, type CaseView } from '../contracts/caseView'
import { CircleAlert } from 'lucide-react'
import { ACTION_LABELS, errorMessage, noticeMessage } from '../contracts/labels'
import { selectScreen } from '../state/selectScreen'
import { useCaseFlow } from '../state/useCaseFlow'
import { FailedScreen } from './FailedScreen'
import { FlowScreen } from './FlowScreen'
import { NoResultScreen } from './NoResultScreen'
import { NotObservedScreen } from './NotObservedScreen'
import { ResultScreen } from './ResultScreen'
import { StoppedScreen } from './StoppedScreen'
import { CandidateCompare, DetailsCheck, EditHint, PlateCheck } from './SubScreens'
import { DEPART_EXIT_MS, UploadScreen, type UploadState } from './UploadScreen'

// 실제 HTTP API(`?api`)로 도는 흐름 — 시연(DemoFlow)과 같은 화면을 쓰고, 어느 화면인가는 CaseView가 정한다.
// 로컬에 둔 것은 사용자가 고른 파일 · 입력한 설명 · 열어 둔 하위 화면뿐이다(web-stack.md 확정 4).
// 화면 → command 연결은 `contract-case-command.md`를, 요청 · 재시도 규칙은 `contract-http-api.md` §6을 따른다.

type Sub = 'candidates' | 'plate' | 'details' | 'hint'
const noop = () => {}
// 결과 화면 갈래 — 진행에서 여기로 넘어오는 순간 자동차가 도착한다(시연과 같다)
const RESULT_KINDS: ReadonlySet<string> = new Set(['AWAIT_RESPONSE', 'EVIDENCE', 'HANDOFF'])
type NoticeAction = Extract<Command, { kind: 'RUN_NOTICE_ACTION' }>['payload']['action']

// notice 버튼 중 command가 있는 것만 보낸다. 나머지(직접 입력류)는 입력형 command가 아직 없다(#212 · #217).
// `EDIT_HINT`는 바로 보내지 않고 설명 입력 화면을 연다 — 거기서 `EDIT_HINT` command로 보낸다(#410).
const SENDABLE: ReadonlySet<string> = new Set<NoticeAction>([
  'GENERATE_REPORT_VIDEO',
  'RETRY_PLATE_READ',
  'RETRY_SEARCH',
  'GENERATE_PLATE_IMAGE',
])

export function ApiFlow(props: { api?: Api; caseId?: string | null }): JSX.Element {
  const [api] = useState(() => props.api ?? createApi())
  const { state, addFiles, send, resume } = useCaseFlow(api)
  const { view } = state
  const [situation, setSituation] = useState('')
  const [subs, setSubs] = useState<Sub[]>([])
  const [startedAt, setStartedAt] = useState(() => Date.now())
  const [unsupported, setUnsupported] = useState(false)

  // 주소의 case id로 이어간다. 새로 만든 case는 주소에 남겨 새로고침해도 이어진다.
  // ponytail: 경과 시간은 이어받은 시점부터 다시 센다 — CaseView에 시작 시각이 없다.
  const { caseId } = props
  useEffect(() => {
    if (caseId) void resume(caseId)
  }, [caseId, resume])
  useEffect(() => {
    if (!state.caseId) return
    const url = new URL(location.href)
    url.searchParams.set('case', state.caseId)
    history.replaceState(null, '', url)
  }, [state.caseId])

  // 자동차 출발 — [영상에서 찾아보기]를 누른 뒤 진행 화면이 실제로 열리는 순간부터 업로드 화면 겉모습
  // 복사본에서 차가 출발한다(시연과 같은 연출). 시작 요청이 실패해 진행 화면이 열리지 않으면 접는다.
  const [leaving, setLeaving] = useState<{ files: { name: string }[]; skipped: string[] } | null>(null)
  const analysing = !!view && view.stage !== 'INTAKE'
  useEffect(() => {
    if (!leaving || !analysing) return
    const t = setTimeout(() => setLeaving(null), DEPART_EXIT_MS)
    return () => clearTimeout(t)
  }, [leaving, analysing])
  useEffect(() => {
    if (state.error) setLeaving(null)
  }, [state.error])
  // 자동차 도착 — 진행 화면에서 결과 화면으로 바뀐 그 순간에만. 이어받아 바로 결과를 열거나 하위 화면에서
  // 돌아올 때는 제자리다
  const kind = analysing ? selectScreen(view).kind : 'UPLOAD'
  const lastKind = useRef(kind)
  const [arriving, setArriving] = useState(false)
  useEffect(() => {
    if (lastKind.current === 'PROGRESS' && RESULT_KINDS.has(kind)) setArriving(true)
    else if (!RESULT_KINDS.has(kind)) setArriving(false)
    lastKind.current = kind
  }, [kind])

  const run = (command: Command) => {
    setUnsupported(false)
    void send(command)
  }
  const onAction = (noticeCode: string, action: Action) => {
    if (action === 'EDIT_HINT') return open('hint')
    if (!SENDABLE.has(action)) return setUnsupported(true)
    run({ kind: 'RUN_NOTICE_ACTION', payload: { notice_code: noticeCode, action: action as NoticeAction } })
  }
  // 보낼 command가 없는 동작은 화면이 사용 불가와 이유를 보인다
  const canRun = (action: Action) => action === 'EDIT_HINT' || SENDABLE.has(action)
  const reselect = (candidateId: string) => {
    setSubs([])
    run({ kind: 'SELECT_OTHER_CANDIDATE', payload: { candidate_id: candidateId } })
  }
  const editHint = (description: string) => {
    setSubs([])
    setSituation(description) // 진행 화면이 새 설명을 보인다
    setStartedAt(Date.now())
    run({ kind: 'EDIT_HINT', payload: { description } })
  }
  const respond = (value: 'CONFIRMED' | 'USER_UNSURE') => run({ kind: 'RECORD_SITUATION_RESPONSE', payload: { value } })
  const open = (sub: Sub) => {
    setSubs((s) => [...s, sub])
    setArriving(false)
  }
  const back = () => setSubs((s) => s.slice(0, -1))
  const sub = subs[subs.length - 1]

  const newReport = () => location.assign(`${location.pathname}?api`)
  const banner = state.error ? errorMessage(state.error.code) : unsupported ? '이 동작은 아직 연결되지 않았어요.' : null

  return (
    <>
      <AppHeader onNewReport={newReport} />
      <main className="web-main rs-page">
        {banner && (
          // 요청 실패 알림 — 결과 화면 실패 안내(.res-notice.is-fail)와 같은 모양
          <div className="rs rs-banner" role="alert">
            <CircleAlert size={18} strokeWidth={1.8} aria-hidden />
            <span>{banner}</span>
          </div>
        )}
        {analysing && leaving && (
          // 겉모습만 남긴 업로드 화면 — 누를 수도, 읽히지도 않는다. 진행 화면은 이미 아래에 열려 있다
          <div className="rs-upload-exit" aria-hidden inert>
            <UploadScreen
              state="done"
              files={leaving.files}
              skipped={leaving.skipped}
              situation={situation}
              onFiles={noop}
              onSituation={noop}
              onSearch={noop}
              departing
            />
          </div>
        )}
        {!view || view.stage === 'INTAKE' ? upload() : analysis(view)}
      </main>
    </>
  )

  // 아래 둘은 컴포넌트가 아니라 함수로 부른다 — 컴포넌트로 두면 렌더마다 새로 만들어져 입력칸 · 타이머가 초기화된다.
  // 올리기 — 영상은 고르는 순간 올라가고(case는 첫 영상에서 만든다), 분석은 [영상에서 찾아보기]에서 시작한다.
  function upload(): JSX.Element {
    const uploads = state.uploads
    // 이어받은 case에는 이번 화면에서 올린 기록이 없다 — 서버에 이미 있는 영상은 개수로 보인다(이름은 오지 않는다).
    // `ok_file_count`만 본다. `failed_file_count`는 화면 판단에 쓰지 않는다(http-api §5.2).
    const already = uploads.length === 0 ? (view?.manifest_summary.ok_file_count ?? 0) : 0
    const uploading = uploads.some((u) => u.status === 'WAITING' || u.status === 'UPLOADING')
    const anyDone = already > 0 || uploads.some((u) => u.status === 'DONE')
    const uploadState: UploadState = uploading ? 'uploading' : anyDone ? 'done' : uploads.length > 0 ? 'fail' : 'idle'
    const files = already > 0 ? [{ name: `이미 올린 영상 ${already}개` }] : uploads
    const skipped = uploads.filter((u) => u.status === 'FAILED').map((u) => u.name)
    return (
      <UploadScreen
        state={uploadState}
        files={files}
        skipped={skipped}
        situation={situation}
        onFiles={(picked) => void addFiles(picked)} // 올리는 중에 고른 파일은 store가 받지 않는다
        onSituation={setSituation}
        onSearch={() => {
          setStartedAt(Date.now())
          setLeaving({ files, skipped })
          run({ kind: 'START_ANALYSIS', payload: { description: situation } })
        }}
      />
    )
  }

  function analysis(view: CaseView): JSX.Element {
    // 설명 고치기는 결과 없음 · 중단 · 결과 화면 어디서나 열린다 — 화면 갈래보다 먼저 본다
    if (sub === 'hint') return <EditHint view={view} onBack={back} onSearch={editHint} onHome={newReport} />
    const screen = selectScreen(view)
    switch (screen.kind) {
      case 'PROGRESS':
        return (
          <FlowScreen
            view={view}
            files={
              state.uploads.length
                ? state.uploads.filter((u) => u.status === 'DONE')
                : [{ name: `영상 ${view.manifest_summary.ok_file_count}개` }]
            }
            situation={situation || view.description || ''}
            startedAt={startedAt}
            pushIn={!!leaving}
            onStop={view.stage === 'SEARCHING' ? () => run({ kind: 'STOP_ANALYSIS', payload: {} }) : undefined}
          />
        )
      case 'STOPPED':
        return <StoppedScreen view={view} onAction={onAction} />
      case 'SEARCH_FAILED':
        return <FailedScreen view={view} onAction={onAction} canRun={canRun} />
      case 'NO_RESULT':
        // 시연과 같은 틀. case가 실은 동작(설명 고치기 · 같은 조건으로 다시 찾기)을 버튼으로 두고, 첫 버튼만 강조한다.
        // 「처음으로」는 서버 action과 따로 언제나 둔다(#410)
        return (
          <div className="rs rs-screen state-page noresult">
            <p className="state-context">신고자료</p>
            <NoResultScreen view={view} />
            {/* 설명을 잘 이해하지 못해 넓게 찾았는데도 0건 — 「결과 없음」과 뜻이 달라 함께 보인다(#266) */}
            {view.notices
              .filter((n) => n.code === 'search.hint_unclear')
              .map((n) => (
                <p key={n.code} className="state-body">
                  {noticeMessage(n.message_key)}
                </p>
              ))}
            <div className="state-actions">
              {view.notices
                .flatMap((n) => n.actions.filter(isAction).filter(canRun).map((a) => ({ code: n.code, a })))
                // 설명을 잘 이해하지 못함(hint_unclear)도 함께 붙으면 같은 동작이 겹친다 — 한 번만 둔다
                .filter((x, i, all) => all.findIndex((y) => y.a === x.a) === i)
                .map(({ code, a }, i) => (
                <button key={`${code}-${a}`} type="button" className={`rs-btn ${i === 0 ? 'pri' : 'sec'}`} onClick={() => onAction(code, a)}>
                  {ACTION_LABELS[a]}
                </button>
              ))}
              <button type="button" className="rs-btn sec" onClick={newReport}>
                처음으로
              </button>
            </div>
          </div>
        )
      case 'NOT_OBSERVED':
        return (
          <NotObservedScreen view={view} onSelect={reselect} restyled onNewReport={newReport} onAction={onAction} canRun={canRun} />
        )
      default:
        if (sub === 'candidates') return <CandidateCompare view={view} onBack={back} onSelect={reselect} />
        if (sub === 'plate') return <PlateCheck view={view} onBack={back} />
        if (sub === 'details') return <DetailsCheck view={view} onBack={back} />
        return (
          <ResultScreen
            view={view}
            onCandidates={() => open('candidates')}
            onPlate={() => open('plate')}
            onDetails={() => open('details')}
            onRespond={respond}
            onAction={onAction}
            canRun={canRun}
            arriving={arriving}
          />
        )
    }
  }
}
