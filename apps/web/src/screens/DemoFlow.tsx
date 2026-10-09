import { useEffect, useRef, useState, type JSX } from 'react'
import type { Action, Candidate, CaseView, Notice } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { AppHeader } from '../components/AppHeader'
import { FailedScreen } from './FailedScreen'
import { FlowScreen } from './FlowScreen'
import { NoResultScreen, RetrySearch } from './NoResultScreen'
import { NotObservedScreen } from './NotObservedScreen'
import { ResultScreen } from './ResultScreen'
import { CandidateCompare, DetailsCheck, PlateCheck } from './SubScreens'
import { acceptView } from '../state/resultModel'
import { UploadScreen, type UploadState } from './UploadScreen'

// 시연용 흐름 — Figma 하단 작업 영역의 Main · Details · Failed 열(After 제외).
// 화면은 사용자 행동(파일 선택·버튼)과 작업 상태 변화로만 넘어간다.
// 진행 화면은 무엇이 실패하든 끝까지 흐르고, 결과는 마지막 화면에서 알린다.
// ponytail: API(case.get_view)가 아직 없어 업로드는 타이머로, 진행은 단계를
// 하나씩 넘기는 CaseView를 만들어 재생해 흉내 낸다. API가 생기면 이 두 타이머
// 자리를 업로드 응답과 get_view() 폴링으로 바꾼다.
const UPLOAD_MS = 1500
const STEP_MS = 1200
// 「영상에서 찾아보기」 뒤 자동차가 출발하고 업로드 화면이 밀려 나가는 시간(전환 0.54초 + 여유).
// 실제 상태는 누르는 즉시 진행으로 넘어가고, 이 시간 동안 겉모습 복사본만 위에 겹쳐 둔다.
const UPLOAD_EXIT_MS = 580
const noop = () => {}

// 스냅샷은 순번이 아니라 모양으로 고른다 — fixture에 스냅샷이 끼어들면 순번이 밀린다
// (응답 전 스냅샷 추가, #177).
function snapshot(scenarioId: string, pick: (view: CaseView) => boolean): CaseView {
  const found = SNAPSHOTS.find((s) => s.scenarioId === scenarioId && pick(s.view))
  if (!found) throw new Error(`fixture 없음: ${scenarioId}`)
  return found.view
}
function fixtureNotice(code: string): Notice {
  const found = SNAPSHOTS.flatMap((s) => s.view.notices).find((n) => n.code === code)
  if (!found) throw new Error(`fixture notice 없음: ${code}`)
  return found
}

const SEARCHING = snapshot('scenario_happy_001', (v) => v.stage === 'SEARCHING')
const HAPPY = snapshot('scenario_happy_001', (v) => v.stage === 'READY' && v.package !== null)
const NOT_FOUND = snapshot('scenario_empty_001', () => true)

// 단계 순서는 fixture(progress)를 따른다. i번째 단계가 진행 중이면 앞은 완료, 뒤는 대기다.
// failedAt 단계는 실패한 채로 남고 뒤 단계는 계속 진행한다. stopped면 until 뒤는 시작하지 않는다.
const STEPS = SEARCHING.progress.map((p) => p.step)
const COARSE = STEPS.indexOf('coarse_search')
const PLATE = STEPS.indexOf('plate_read')
const PACKAGE = STEPS.indexOf('package_assembly')
type StepState = CaseView['progress'][number]['state']

function at(running: number, failedAt = -1, stopped = false): CaseView {
  const state = (i: number): StepState =>
    i === failedAt && i <= running
      ? 'FAILED'
      : i < running
        ? 'DONE'
        : i > running || stopped
          ? 'PENDING'
          : 'RUNNING'
  return { ...SEARCHING, running_jobs: [], notices: [], progress: STEPS.map((step, i) => ({ step, state: state(i) })) }
}
// 0..until-1 단계를 차례로 진행하고, 마지막에 until 앞까지 끝난 화면을 하나 더 둔다.
const walk = (until: number, failedAt = -1) => [
  ...STEPS.slice(0, until).map((_, i) => at(i, failedAt)),
  at(until, failedAt, true),
]

// ponytail: 아래 시연용 CaseView들은 fixture에 아직 없는 경우를 계약 모양대로 만든 것이다.
// fixture가 생기면 snapshot()으로 바꾼다.
//
// fixture 후보가 1개뿐이라 「다른 후보」를 보이려고 두 개를 더 붙인다.
const OTHER_CANDIDATES: Candidate[] = [
  { ...HAPPY.candidates[0], candidate_id: 'demo_c2', selected: false, at: null, observed: '흰 SUV가 교차로에서 정지선을 넘어 멈춘 장면' },
  { ...HAPPY.candidates[0], candidate_id: 'demo_c3', selected: false, at: null, observed: '회색 승용차가 실선 구간에서 차로를 바꾸는 장면' },
]
const RESULT: CaseView = { ...HAPPY, candidates: [...HAPPY.candidates, ...OTHER_CANDIDATES] }

function withoutPlate(view: CaseView, notices: Notice[]): CaseView {
  return {
    ...view,
    notices,
    evidence: view.evidence && {
      ...view.evidence,
      plate_display: { value: null, needs_review: true, info_state: 'INFO_UNKNOWN', source_label_key: null },
    },
    package: view.package && {
      ...view.package,
      report_fields: { ...view.package.report_fields, vehicle_number: null },
      report_field_states: {
        ...view.package.report_field_states,
        vehicle_number: { info_state: 'INFO_UNKNOWN', source_label_key: null },
      },
    },
  }
}
// 번호판 판독 실행 실패(#172 D) — blocking notice. 이 상태로는 제출 단계로 넘기지 않는다.
// 실제 CaseView는 evidence만 있고 package가 없다(#224 case 확인).
const PLATE_FAILED_RESULT: CaseView = {
  ...withoutPlate(RESULT, [fixtureNotice('readout.plate_read_failed')]),
  package: null,
}
// 번호판을 읽었지만 확정하지 못함(#172 D-3) — 경고만 달고 제출은 막지 않는다.
// notice는 fixture 그대로(actions: MANUAL_PLATE_INPUT) — 실제 데이터에서 오는 버튼을 시연에서도 보인다.
const PLATE_UNREAD_RESULT = withoutPlate(RESULT, [fixtureNotice('evidence.plate_abstained')])
// 신고용 영상 미생성 — 아직 만들지 않아 GENERATE_REPORT_VIDEO 발주가 필요한 상태다. 묶음이
// 완성되지 않아 READY가 아니다. export 실패(recording.report_video_export_failed)와 다르다 —
// 그 notice는 message_key·actions 모양이 아직 없어 시연하지 않는다(#224 recording 리뷰).
const VIDEO_NOT_GENERATED_RESULT: CaseView = {
  ...RESULT,
  stage: 'EVIDENCE_REVIEW',
  package: RESULT.package && { ...RESULT.package, artifact_ref: null },
  notices: [fixtureNotice('case.report_video_not_generated')],
}
// 발생 시각 확인 필요 — fixture의 시각 notice 그대로(actions: EDIT_EVENT_TIME · REVIEW_TIME).
// 두 동작은 입력 화면과 command가 아직 없어 사용 불가로 보인다. 제출을 막지 않는 경고다.
const TIME_REVIEW_RESULT: CaseView = {
  ...RESULT,
  notices: [fixtureNotice('evidence.time_needs_user_confirmation'), fixtureNotice('evidence.time_conflict_needs_notice')],
}
// 음성 결과(#168 [A]) — EVIDENCE_REVIEW + evidence=null + evidence.visual_event_not_observed.
const NOT_OBSERVED: CaseView = {
  ...RESULT,
  stage: 'EVIDENCE_REVIEW',
  evidence: null,
  package: null,
  notices: [
    { code: 'evidence.visual_event_not_observed', severity: 'INFO', blocking: false, message_key: 'notice.visual_event_not_observed', actions: [] },
  ],
}
// 탐색 실패(#197) — SEARCHING + coarse_search FAILED + search.candidate_search_failed.
const SEARCH_FAILED: CaseView = {
  ...at(COARSE, COARSE, true),
  notices: [
    {
      code: 'search.candidate_search_failed',
      severity: 'ERROR',
      blocking: true,
      message_key: 'notice.candidate_search_failed',
      actions: ['RETRY_SEARCH'],
    },
  ],
}

// 다른 후보를 고른 뒤의 결과. 판독 결과 fixture는 1순위 후보(HAPPY) 것뿐이다.
// 다른 후보는 이전 후보의 번호판·시각·장소·위반 내용·신고자료 묶음·영상을 옮기지 않는다(§8-1 「자동 이월
// 금지」, case-view 계약: 이전 선택 context의 evidence·package는 내리지 않음). 값이 없으니 모두 알 수 없음이고
// 신고자료 묶음(package)도 없다 — 시연용 상태다. 사건 전체 값(기억 단서·파일 요약·후보 목록)은 그대로 둔다.
const FIXTURE_CANDIDATE = HAPPY.candidates[0].candidate_id
function resultFor(candidateId: string): CaseView {
  const candidates = RESULT.candidates.map((c) => ({ ...c, selected: c.candidate_id === candidateId }))
  // 다시 고르면 case_rev가 오른다(SELECT_OTHER_CANDIDATE 성공 시 case_rev +1, contract-case-command §74)
  const base = { ...RESULT, candidates, case_rev: RESULT.case_rev + 1 }
  if (candidateId === FIXTURE_CANDIDATE) return base
  const chosen = candidates.find((c) => c.selected)!
  const unknown = { value: null, needs_review: true, info_state: 'INFO_UNKNOWN' as const, source_label_key: null }
  const unknownCode = { code: null, label: null, needs_review: true, info_state: 'INFO_UNKNOWN' as const, source_label_key: null }
  return {
    ...base,
    stage: 'EVIDENCE_REVIEW',
    notices: [],
    running_jobs: [],
    requirements_evidence: null,
    requirements_package: null,
    package: null,
    evidence: {
      ...RESULT.evidence!,
      record_id: `demo_evidence_${candidateId}`,
      case_type_display: unknownCode,
      report_type_display: unknownCode,
      violation_display: unknownCode,
      plate_display: unknown,
      event_time_display: unknown,
      location_display: { ...unknown, coord: null, search_keyword: null },
      user_edited: false,
      // 계약: evidence.preview_ref는 선택된 후보의 thumb_ref와 같다
      preview_ref: chosen.thumb_ref,
      review_needed: true,
      reason_code: 'evidence.multiple_fields_need_review',
    },
  }
}

// 한 번의 진행: 재생할 CaseView들, 끝나면 보여 줄 마지막 화면, 진행 화면 제목(다시 할 때만).
type End = 'result' | 'notFound' | 'notObserved' | 'failed'
interface Run {
  frames: CaseView[]
  end: End
  view: CaseView
  title?: string
}
const FULL_RUN: Run = { frames: walk(STEPS.length), end: 'result', view: RESULT }
// 이미 끝난 단계는 완료로 두고 from 단계부터 다시 흐른다(core-user-flow §19·§23).
const rerunFrom = (from: number, title: string): Run => ({ ...FULL_RUN, frames: FULL_RUN.frames.slice(from), title })

// 실패·결과 없음은 사용자가 고르는 게 아니라 작업이 정한다. 시연에서 어느 경우를 보여 줄지만 고른다.
interface DemoCase {
  label: string
  upload: 'ok' | 'fail' | 'partial'
  run: Run
}
const CASES: Record<string, DemoCase> = {
  main: { label: '정상 — 신고자료 준비', upload: 'ok', run: FULL_RUN },
  plateUnread: {
    label: '번호판 못 읽음(경고만, 제출 가능)',
    upload: 'ok',
    run: { ...FULL_RUN, view: PLATE_UNREAD_RESULT },
  },
  timeReview: {
    label: '발생 시각 확인 필요(입력 화면 미연결)',
    upload: 'ok',
    run: { ...FULL_RUN, view: TIME_REVIEW_RESULT },
  },
  plateFailed: {
    label: '번호판 판독 실패(시스템 오류)',
    upload: 'ok',
    run: { frames: walk(STEPS.length, PLATE), end: 'result', view: PLATE_FAILED_RESULT },
  },
  videoNotGenerated: {
    label: '신고용 영상 미생성',
    upload: 'ok',
    // 실패가 아니라 시작하지 않은 것이다 — 마지막 단계는 실패가 아니라 대기로 남는다.
    run: { frames: walk(PACKAGE), end: 'result', view: VIDEO_NOT_GENERATED_RESULT },
  },
  notObserved: {
    label: '찾은 장면에서 위반 미관찰',
    upload: 'ok',
    // 1순위 장면을 자세히 본 「후보 확인」에서 끝난다. 번호판·시각은 읽지 않는다(#168 [A], #171 B).
    run: { frames: walk(STEPS.indexOf('candidate_review') + 1), end: 'notObserved', view: NOT_OBSERVED },
  },
  notFound: {
    label: '결과 없음(장면 0개)',
    upload: 'ok',
    // 장면 찾기에서 후보 0개로 끝난다. 그 뒤 단계는 하지 않는다(#197).
    run: { frames: walk(COARSE + 1), end: 'notFound', view: NOT_FOUND },
  },
  searchFailed: {
    label: '장면 찾기 실패(시스템 오류)',
    upload: 'ok',
    run: { frames: walk(COARSE + 1, COARSE), end: 'failed', view: SEARCH_FAILED },
  },
  uploadPartial: { label: '업로드 일부 실패(나머지로 계속)', upload: 'partial', run: FULL_RUN },
  uploadFail: { label: '업로드 실패', upload: 'fail', run: FULL_RUN },
}
// ponytail: 일부 실패 시연용 — 실제로는 업로드 응답이 건너뛴 파일을 알려 준다.
const DEMO_SKIPPED = ['FILE_017.mp4']

type Main =
  | { kind: 'upload'; state: UploadState }
  | { kind: 'flow'; run: Run; frame: number; startedAt: number }
  | { kind: 'done'; run: Run }
type Sub = 'candidates' | 'plate' | 'plateEdit' | 'details'
// 시연에서 연결한 notice 동작. 나머지(시각 직접 입력·시각 확인하기·설명 고치기)는 입력 화면과 command가
// 아직 없어(contract-case-command §32 「입력형 action은 다음 판본」) 사용 불가로 보인다.
// ponytail: 연결한 것도 실제 command(RUN_NOTICE_ACTION)를 보내지 않는다 — 시연용 재진행·화면 안 반영이다.
const DEMO_ACTIONS = new Set<Action>(['RETRY_PLATE_READ', 'GENERATE_REPORT_VIDEO', 'RETRY_SEARCH', 'MANUAL_PLATE_INPUT'])
const canRun = (a: Action) => DEMO_ACTIONS.has(a)

// 사용자가 직접 입력한 번호판을 결과 CaseView에 얹는다.
// ponytail: 직접 입력을 case로 보내는 경로가 아직 계약에 없다(MANUAL_PLATE_INPUT, #212·#217).
// 시연에서는 화면 안에서만 반영한다 — command가 생기면 PlateCheck onEdit 자리에서 보낸다.
function withPlate(view: CaseView, plate: string | null): CaseView {
  if (!plate || !view.evidence) return view
  if (!view.package)
    return {
      ...view,
      evidence: {
        ...view.evidence,
        plate_display: { value: plate, needs_review: false, info_state: 'INFO_USER_CONFIRMED', source_label_key: null },
      },
    }
  return {
    ...view,
    evidence: {
      ...view.evidence,
      plate_display: { value: plate, needs_review: false, info_state: 'INFO_USER_CONFIRMED', source_label_key: null },
    },
    package: {
      ...view.package,
      report_fields: { ...view.package.report_fields, vehicle_number: plate },
      report_field_states: {
        ...view.package.report_field_states,
        vehicle_number: { info_state: 'INFO_USER_CONFIRMED', source_label_key: null },
      },
    },
  }
}

export function DemoFlow(): JSX.Element {
  const [caseKey, setCaseKey] = useState('main')
  const [main, setMain] = useState<Main>({ kind: 'upload', state: 'idle' })
  const [subs, setSubs] = useState<Sub[]>([])
  const [files, setFiles] = useState<File[]>([])
  const [situation, setSituation] = useState('')
  const [plate, setPlate] = useState<string | null>(null)
  const [uploadLeaving, setUploadLeaving] = useState(false)
  const demo = CASES[caseKey]

  useEffect(() => {
    if (!uploadLeaving) return
    const t = setTimeout(() => setUploadLeaving(false), UPLOAD_EXIT_MS)
    return () => clearTimeout(t)
  }, [uploadLeaving])

  // 업로드가 끝나면 완료/실패로 넘어간다. 일부만 실패하면 나머지로 계속한다.
  useEffect(() => {
    if (main.kind !== 'upload' || main.state !== 'uploading') return
    const t = setTimeout(() => setMain({ kind: 'upload', state: demo.upload === 'fail' ? 'fail' : 'done' }), UPLOAD_MS)
    return () => clearTimeout(t)
  }, [main, demo])

  // 다음 CaseView가 오면 화면이 바뀌고, 마지막까지 흐르면 마지막 화면으로 간다.
  // 후보를 바꾼 뒤에는 그 후보·그 case_rev 결과만 받는다 — 늦게 온 이전 후보 결과가 새 화면을 덮지 않게.
  const expected = useRef<{ caseRev: number; candidateId: string | null }>({ caseRev: 0, candidateId: null })
  useEffect(() => {
    if (main.kind !== 'flow') return
    const last = main.frame >= main.run.frames.length - 1
    const t = setTimeout(() => {
      if (last && !acceptView(main.run.view, expected.current)) return
      setMain(last ? { kind: 'done', run: main.run } : { ...main, frame: main.frame + 1 })
    }, STEP_MS)
    return () => clearTimeout(t)
  }, [main])

  // 새 진행은 새 초안이다 — 직접 입력한 번호판도 넘기지 않는다(#173).
  const start = (run: Run, expect: { caseRev: number; candidateId: string | null } = { caseRev: 0, candidateId: null }) => {
    expected.current = expect
    setSubs([])
    setReturnY([])
    setPlate(null)
    setMain({ kind: 'flow', run, frame: 0, startedAt: Date.now() })
  }
  const newReport = () => {
    setUploadLeaving(false)
    setMain({ kind: 'upload', state: 'idle' })
    setSubs([])
    setReturnY([])
    setPlate(null)
    setFiles([])
    setSituation('')
  }
  // 하위 화면은 맨 위에서 열고, 뒤로 오면 결과 화면을 보던 자리로 돌아간다.
  const [returnY, setReturnY] = useState<number[]>([])
  const open = (sub: Sub) => {
    setReturnY((y) => [...y, window.scrollY])
    setSubs((s) => [...s, sub])
  }
  const back = () => setSubs((s) => s.slice(0, -1))
  const sub = subs[subs.length - 1]
  const done = main.kind === 'done' ? main.run : null
  const doneView = done && withPlate(done.view, plate)
  // 화면이 바뀌면 맨 위에서 시작한다 — 업로드 화면 아래쪽 버튼을 누른 스크롤 위치가 다음 화면에
  // 그대로 남지 않게. 하위 화면에서 돌아올 때만 저장해 둔 자리로 간다.
  const screenKey = main.kind === 'done' ? `done-${done?.end}-${subs.join('/')}` : main.kind
  useEffect(() => {
    const y = subs.length < returnY.length ? returnY[returnY.length - 1] : 0
    if (subs.length < returnY.length) setReturnY((r) => r.slice(0, subs.length))
    if (window.scrollY !== y) window.scrollTo(0, y)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 화면이 바뀔 때만
  }, [screenKey])
  // 고른 후보를 기준 후보로 바꿔 번호판부터 다시 준비한다. 결과는 그 후보 것만 쓴다(resultFor).
  // API가 생기면 여기서 SELECT_OTHER_CANDIDATE { candidate_id } + expected_case_rev를 보낸다(#216).
  const reselect = (candidateId: string) => {
    const view = resultFor(candidateId)
    start({ ...rerunFrom(PLATE, '새 후보 기준으로 신고자료를 다시 준비하고 있어요'), view }, { caseRev: view.case_rev, candidateId })
  }
  // notice actions[] → 다시 하기. 실패한 단계부터 이어서 한다.
  // API가 생기면 RUN_NOTICE_ACTION { notice_code, action }으로 보낸다 — 그래서 code도 받아 둔다.
  const onAction = (_noticeCode: string, a: Action) => {
    if (a === 'MANUAL_PLATE_INPUT') return open('plateEdit')
    if (a === 'RETRY_PLATE_READ') start(rerunFrom(PLATE, '번호판을 다시 읽고 있어요'))
    if (a === 'GENERATE_REPORT_VIDEO') start(rerunFrom(PACKAGE, '신고용 영상을 만들고 있어요'))
    if (a === 'RETRY_SEARCH') start(rerunFrom(COARSE, '장면을 다시 찾고 있어요'))
  }

  return (
    <>
      <AppHeader onNewReport={newReport} />
      <main className="web-main rs-page">
        {main.kind === 'upload' && (
          <>
            <UploadScreen
              state={main.state}
              files={files}
              skipped={demo.upload === 'partial' ? DEMO_SKIPPED : []}
              situation={situation}
              onFiles={(f) => {
                setFiles(f)
                setMain({ kind: 'upload', state: 'uploading' })
              }}
              onSituation={setSituation}
              onSearch={() => {
                setUploadLeaving(true)
                start(demo.run)
              }}
            />
            <label className="kv-src demo-pick">
              시연할 경우{' '}
              <select value={caseKey} onChange={(e) => setCaseKey(e.target.value)}>
                {Object.entries(CASES).map(([key, c]) => (
                  <option key={key} value={key}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        {main.kind === 'flow' && uploadLeaving && (
          // 겉모습만 남긴 업로드 화면 — 누를 수도, 읽히지도 않는다. 진행 화면은 이미 아래에 열려 있다.
          <div className="rs-upload-exit" aria-hidden inert>
            <UploadScreen
              state="done"
              files={files}
              skipped={demo.upload === 'partial' ? DEMO_SKIPPED : []}
              situation={situation}
              onFiles={noop}
              onSituation={noop}
              onSearch={noop}
              departing
            />
          </div>
        )}
        {main.kind === 'flow' && (
          <FlowScreen
            view={main.run.frames[main.frame]}
            files={files}
            skipped={demo.upload === 'partial' ? DEMO_SKIPPED : []}
            situation={situation}
            startedAt={main.startedAt}
            title={main.run.title}
            pushIn={uploadLeaving}
          />
        )}

        {done?.end === 'notFound' && (
          <div className="rs rs-screen state-page noresult">
            <NoResultScreen
              view={{ ...done.view, hints: { time: null, vehicle: null, location: null, situation: situation || null } }}
            />
            {/* 다시 찾기는 새 탐색이다(core-user-flow §4-2). 시연에서는 찾아지는 경우로 다시 돈다. */}
            <RetrySearch situation={situation} onSituation={setSituation} onRetry={() => start(FULL_RUN)} />
          </div>
        )}
        {done?.end === 'failed' && <FailedScreen view={done.view} onAction={onAction} canRun={canRun} />}
        {done?.end === 'notObserved' && !sub && <NotObservedScreen view={done.view} onSelect={reselect} restyled />}
        {done?.end === 'result' && !sub && doneView && (
          <ResultScreen
            view={doneView}
            onCandidates={() => open('candidates')}
            onPlate={() => open('plate')}
            onDetails={() => open('details')}
            onAction={onAction}
            canRun={canRun}
            plateEditedLocally={plate !== null}
          />
        )}

        {done && sub === 'candidates' && <CandidateCompare view={done.view} onBack={back} onSelect={reselect} />}
        {doneView && (sub === 'plate' || sub === 'plateEdit') && (
          <PlateCheck
            view={doneView}
            aiValue={done.view.evidence?.plate_display.value ?? null}
            startEditing={sub === 'plateEdit'}
            onBack={back}
            onEdit={setPlate}
          />
        )}
        {doneView && sub === 'details' && <DetailsCheck view={doneView} onBack={back} />}
      </main>
    </>
  )
}
