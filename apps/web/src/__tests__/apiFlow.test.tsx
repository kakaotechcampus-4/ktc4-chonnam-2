// @vitest-environment jsdom
//
// `?api` 흐름 — 화면은 CaseView로 고르고, 버튼은 command로 이어진다(contract-case-command · contract-http-api §6).
// 서버가 없으므로 Api를 가짜로 끼운다.

import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { Api, ApiResult } from '../api/client'
import type { CaseView, Notice } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { ApiFlow } from '../screens/ApiFlow'

afterEach(cleanup)
beforeEach(() => history.replaceState(null, '', '/?api'))

const BASE = SNAPSHOTS[0].view
const JOBS = [
  { job_id: 'j1', kind: 'COARSE_SEARCH', label_key: 'job.generic_processing', status: 'RUNNING' },
] as CaseView['running_jobs']
const notice = (code: string, actions: string[]): Notice => ({
  code,
  severity: 'INFO',
  blocking: false,
  message_key: code.replace('case.', 'notice.'),
  actions,
})
const view = (patch: Partial<CaseView>): CaseView => ({
  ...BASE,
  case_rev: 1,
  stage: 'INTAKE',
  running_jobs: [],
  notices: [],
  manifest_summary: { ...BASE.manifest_summary, file_count: 0, ok_file_count: 0 },
  ...patch,
})
const ok = <T,>(data: T, status = 200): ApiResult<T> => ({ ok: true, status, data })
const NETWORK_DOWN: ApiResult<never> = { ok: false, status: 0, error: { code: 'web.network_error', message_key: 'web.network_error' }, caseView: null }

const SEARCHING = view({ case_rev: 2, stage: 'SEARCHING', running_jobs: JOBS, manifest_summary: { ...BASE.manifest_summary, file_count: 1, ok_file_count: 1 } })
const STOPPED = view({
  case_rev: 3,
  stage: 'SEARCHING',
  notices: [notice('case.analysis_stopped', ['RETRY_SEARCH'])],
})
// 응답 대기(UNCERTAIN) — B안 fixture에는 이 스냅샷이 없어 결과 스냅샷에서 만든다: 조립 전(record_id null) + 응답 대기 notice
const AWAITING_BASE = SNAPSHOTS.map((s) => s.view).find((v) => v.package && v.evidence)!
const AWAITING: CaseView = {
  ...AWAITING_BASE,
  stage: 'EVIDENCE_REVIEW',
  package: null,
  evidence: { ...AWAITING_BASE.evidence!, record_id: null },
  candidates: AWAITING_BASE.candidates.map((c) => (c.selected ? { ...c, situation_confirmation: 'NOT_ASKED' } : c)),
  notices: [notice('case.situation_response_pending', [])],
}

function setup(views: { get?: CaseView } = {}) {
  const m = {
    createCase: vi.fn().mockResolvedValue(ok({ case_id: 'c1', case_view: view({}) }, 201)),
    uploadSource: vi
      .fn()
      .mockResolvedValue(
        ok({ case_id: 'c1', source_asset_ref: 'sa', case_view: view({ manifest_summary: { ...BASE.manifest_summary, file_count: 1, ok_file_count: 1 } }) }, 201),
      ),
    sendCommand: vi.fn(),
    getView: vi.fn().mockResolvedValue(ok(views.get ?? view({}))),
  }
  const api = { ...m, frameUrl: () => '', assetUrl: () => '', candidateVideoUrl: (_case: string, ref: string) => `/candidate-video/${ref}` } as unknown as Api
  return { m, api }
}

it('영상을 고르면 올라가고, [영상에서 찾아보기]에서 상황 설명과 함께 분석을 시작한다', async () => {
  const { m, api } = setup()
  m.sendCommand.mockResolvedValue(ok(SEARCHING, 202))
  const { container, getByRole, getByText, findByText } = render(<ApiFlow api={api} />)

  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['x'], 'a.mp4')] } })
  expect(m.uploadSource).not.toHaveBeenCalled() // 개인정보·외부 처리 안내에 동의하기 전에는 서버로 보내지 않는다
  fireEvent.click(getByText('동의하고 올리기'))
  await findByText(/^업로드 완료/)
  expect(m.createCase).toHaveBeenCalledOnce()
  expect(m.uploadSource).toHaveBeenCalledWith('c1', expect.objectContaining({ name: 'a.mp4' }))
  expect(m.sendCommand).not.toHaveBeenCalled() // 고르는 것만으로 분석이 시작되지 않는다

  fireEvent.change(getByRole('textbox'), { target: { value: '흰 SUV가 끼어들었어요' } })
  fireEvent.click(getByText('영상에서 찾아보기'))
  await findByText('분석 중단')
  expect(m.sendCommand).toHaveBeenCalledWith('c1', 1, { kind: 'START_ANALYSIS', payload: { description: '흰 SUV가 끼어들었어요' } })
  expect(location.search).toContain('case=c1') // 새로고침해도 이어진다
})

it('올리는 중에 고른 파일은 받지 않고 목록에도 올리지 않는다', async () => {
  const { m, api } = setup()
  let finish!: (r: unknown) => void
  m.uploadSource.mockImplementationOnce(() => new Promise((r) => (finish = r)))
  const { container, findByText, getByText, queryByText } = render(<ApiFlow api={api} />)
  const input = container.querySelector('input[type=file]')!

  fireEvent.change(input, { target: { files: [new File(['x'], 'a.mp4')] } })
  fireEvent.click(getByText('동의하고 올리기'))
  await findByText('업로드 중')
  fireEvent.change(input, { target: { files: [new File(['x'], 'b.mp4')] } })
  expect(queryByText('동의하고 올리기')).toBeNull() // 받지 않을 파일이라 동의도 묻지 않는다(#606 리뷰)
  finish(ok({ case_id: 'c1', source_asset_ref: 'sa', case_view: view({ manifest_summary: { ...BASE.manifest_summary, file_count: 1, ok_file_count: 1 } }) }, 201))
  await findByText(/^업로드 완료/)

  expect(m.uploadSource).toHaveBeenCalledOnce()
  expect(queryByText(/b\.mp4/)).toBeNull()
})

it('시작 전에 이어받은 case는 서버에 있는 영상을 개수로 보이고 바로 시작할 수 있다 — 다시 올리지 않는다', async () => {
  const intake = view({ case_rev: 2, manifest_summary: { ...BASE.manifest_summary, file_count: 1, ok_file_count: 1 } })
  const { m, api } = setup({ get: intake })
  m.sendCommand.mockResolvedValue(ok(SEARCHING, 202))
  const { findByText, getByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText('이미 올린 영상 1개')
  expect(getByText(/^업로드 완료/)).toBeTruthy()
  fireEvent.click(getByText('영상에서 찾아보기'))
  await findByText('분석 중단')
  expect(m.uploadSource).not.toHaveBeenCalled()
  expect(m.sendCommand).toHaveBeenCalledWith('c1', 2, { kind: 'START_ANALYSIS', payload: { description: '' } })
})

it('[분석 중단]은 STOP_ANALYSIS를 보내고, 중단 화면에서 [다시 찾기]는 RETRY_SEARCH 알림 동작이다', async () => {
  const { m, api } = setup({ get: SEARCHING })
  m.sendCommand.mockResolvedValue(ok(STOPPED))
  const { findByText, getByText } = render(<ApiFlow api={api} caseId="c1" />)

  fireEvent.click(await findByText('분석 중단'))
  await findByText('분석을 중단했어요.')
  expect(m.sendCommand).toHaveBeenCalledWith('c1', 2, { kind: 'STOP_ANALYSIS', payload: {} })
  // 중단 화면으로 바뀌면 그 제목에 초점이 간다(#509 #2)
  expect(document.activeElement?.textContent).toBe('분석을 중단했어요.')

  m.sendCommand.mockResolvedValue(ok({ ...SEARCHING, case_rev: 4 })) // 다시 찾으면 rev가 오른다
  fireEvent.click(getByText('다시 찾기'))
  await findByText('분석 중단')
  expect(m.sendCommand).toHaveBeenLastCalledWith('c1', 3, {
    kind: 'RUN_NOTICE_ACTION',
    payload: { notice_code: 'case.analysis_stopped', action: 'RETRY_SEARCH' },
  })
})

it('case 대기 timeout(#358)은 중단 화면에 timeout 문구로 보이고, [다시 찾기]는 RETRY_SEARCH다', async () => {
  const clock = vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-31T00:00:00Z'))
  try {
    const timedOut = view({ case_rev: 3, stage: 'SEARCHING', notices: [notice('case.analysis_timed_out', ['RETRY_SEARCH'])] })
    const { m, api } = setup({ get: timedOut })
    m.sendCommand.mockResolvedValue(ok({ ...SEARCHING, case_rev: 4 }, 202))
    const { container, findByText, getByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
    await findByText('장면을 찾는 시간이 오래 걸려 멈췄어요.')
    expect(queryByText('분석을 중단했어요.')).toBeNull()
    clock.mockReturnValue(Date.parse('2026-10-31T00:05:00Z'))
    fireEvent.click(getByText('다시 찾기'))
    await findByText('분석 중단')
    expect(container.querySelector('.flow-elapsed span')?.textContent).toBe('00:00')
    expect(m.sendCommand).toHaveBeenCalledWith('c1', 3, { kind: 'RUN_NOTICE_ACTION', payload: { notice_code: 'case.analysis_timed_out', action: 'RETRY_SEARCH' } })
  } finally {
    clock.mockRestore()
  }
})

it('진행 화면 대표 영상 자리는 원본이 없으면 고른 후보 썸네일, 그것도 없으면 근거 장면을 보인다(#634 리뷰)', async () => {
  const selected = { ...BASE.candidates[0], selected: true }
  const evidence = { ...BASE.evidence!, preview_ref: 'fr_evidence' }
  // #621: evidence가 있는 EVIDENCE_REVIEW는 결과 초안이다. 이 검사는 후보 준비 진행 화면을 사용한다.
  const shown = async (thumb: string | null) => {
    const { api } = setup({ get: view({ case_rev: 5, stage: 'CANDIDATE_REVIEW', running_jobs: JOBS, candidates: [{ ...selected, thumb_ref: thumb }], evidence }) })
    ;(api as { frameUrl: (c: string, r: string) => string }).frameUrl = (_c, r) => `/frames/${r}`
    const r = render(<ApiFlow api={api} caseId="c1" />)
    await waitFor(() => expect(r.container.querySelector('.flow-thumb img')).not.toBeNull())
    const src = r.container.querySelector('.flow-thumb img')!.getAttribute('src')
    cleanup()
    return src
  }
  expect(await shown('fr_thumb')).toBe('/frames/fr_thumb')
  expect(await shown(null)).toBe('/frames/fr_evidence')
})

it('설명을 고쳐 다시 찾는 동안 원본이 없어도 대표 영상 자리는 이 case에서 보이던 장면을 둔다', async () => {
  vi.useFakeTimers()
  try {
    const shownView = view({ case_rev: 5, stage: 'CANDIDATE_REVIEW', running_jobs: JOBS, candidates: [{ ...BASE.candidates[0], selected: true, thumb_ref: 'fr_thumb' }] })
    const { m, api } = setup({ get: shownView })
    ;(api as { frameUrl: (c: string, r: string) => string }).frameUrl = (_c, r) => `/frames/${r}`
    // 다시 찾기로 후보가 비워진 view(같은 case)
    m.getView.mockResolvedValueOnce(ok(shownView)).mockResolvedValue(ok({ ...SEARCHING, case_rev: 6, case_id: shownView.case_id, candidates: [], evidence: null }))
    const { container, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
    await act(async () => {})
    expect(container.querySelector('.flow-thumb img')?.getAttribute('src')).toBe('/frames/fr_thumb')
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(queryByText('분석 중단')).toBeTruthy()
    expect(container.querySelector('.flow-thumb img')?.getAttribute('src')).toBe('/frames/fr_thumb')
    expect(queryByText('미리보기를 표시할 수 없어요')).toBeNull()
  } finally {
    cleanup()
    vi.useRealTimers()
  }
})

it('찾는 중이 아닐 때(SEARCHING이 아닐 때)는 중단 버튼을 두지 않는다', async () => {
  const { api } = setup({ get: view({ case_rev: 5, stage: 'CANDIDATE_REVIEW', running_jobs: JOBS, candidates: BASE.candidates }) })
  const { findByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText(/신고자료를 준비하고 있어요|사건을 찾고 있어요/)
  expect(queryByText('분석 중단')).toBeNull()
})

it('신고 상황 응답은 RECORD_SITUATION_RESPONSE로 보내고, 응답 대기(UNCERTAIN)에는 「맞아요」가 없다', async () => {
  const { m, api } = setup({ get: AWAITING })
  m.sendCommand.mockResolvedValue(ok({ ...AWAITING, case_rev: AWAITING.case_rev + 1 }))
  const { findByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('잘 모르겠어요'))
  expect(queryByText('맞아요')).toBeNull()
  await waitFor(() => expect(m.sendCommand).toHaveBeenCalled())
  expect(m.sendCommand).toHaveBeenCalledWith('c1', AWAITING.case_rev, { kind: 'RECORD_SITUATION_RESPONSE', payload: { value: 'USER_UNSURE' } })
})

it('요청이 실패하면 화면은 그대로 두고 알림만 띄운다', async () => {
  const { m, api } = setup({ get: SEARCHING })
  m.sendCommand.mockResolvedValue(NETWORK_DOWN)
  m.getView.mockResolvedValue(ok(SEARCHING)) // 반영 여부를 모르면 먼저 읽는다
  const { findByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('분석 중단'))
  await findByText('서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요.')
  expect(await findByText('분석 중단')).toBeTruthy()
})

it('진행 조회가 끊기면 진행 화면을 내리고, 조회 복구로 최신 화면을 되찾는다 — 분석은 다시 보내지 않는다', async () => {
  vi.useFakeTimers()
  try {
    const { m, api } = setup({ get: SEARCHING })
    m.getView.mockResolvedValueOnce(ok(SEARCHING)).mockResolvedValueOnce(NETWORK_DOWN).mockResolvedValue(ok(STOPPED))
    const { container, getByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
    await act(async () => {})
    expect(getByText('분석 중단')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(getByText('진행 상태를 확인할 수 없어요')).toBeTruthy()
    expect(container.querySelector('.flow')).toBeNull()
    expect(queryByText('다시 찾기')).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(getByText('분석을 중단했어요.')).toBeTruthy()
    expect(queryByText('진행 상태를 확인할 수 없어요')).toBeNull()
    expect(m.sendCommand).not.toHaveBeenCalled()
  } finally {
    cleanup()
    vi.useRealTimers()
  }
})

it('command가 없는 알림 버튼(시각 후보 고르기)은 보내지 않고 안내한다', async () => {
  const stopped = view({ case_rev: 3, stage: 'SEARCHING', notices: [notice('case.analysis_stopped', ['REVIEW_TIME'])] })
  const { m, api } = setup({ get: stopped })
  const { findByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('시각 확인하기'))
  await findByText('이 동작은 아직 연결되지 않았어요.')
  expect(m.sendCommand).not.toHaveBeenCalled()
})

it('[영상에서 찾아보기] 뒤 진행 화면이 열리면 업로드 겉모습 복사본에서 자동차가 출발한다', async () => {
  const { m, api } = setup()
  m.sendCommand.mockResolvedValue(ok(SEARCHING, 202))
  const { container, getByText, findByText } = render(<ApiFlow api={api} />)
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['x'], 'a.mp4')] } })
  fireEvent.click(getByText('동의하고 올리기'))
  await findByText(/^업로드 완료/)
  fireEvent.click(getByText('영상에서 찾아보기'))
  await findByText('분석 중단')
  const ghost = container.querySelector('.rs-upload-exit')!
  expect(ghost.getAttribute('aria-hidden')).toBe('true')
  expect(ghost.querySelector('.rs-depart')).not.toBeNull()
  expect(container.querySelector('.rs.flow.rs-push-in')).not.toBeNull()
  await waitFor(() => expect(container.querySelector('.rs-upload-exit')).toBeNull(), { timeout: 3000 })
})

it('진행에서 결과로 넘어오는 순간에만 자동차가 도착한다 — 이어받아 바로 결과면 제자리', async () => {
  const READY = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.view.stage === 'READY' && s.view.package !== null)!.view
  const first = setup({ get: READY })
  first.m.getView.mockResolvedValueOnce(ok(SEARCHING))
  const a = render(<ApiFlow api={first.api} caseId="c1" />)
  await a.findByText('분석 중단')
  await waitFor(() => expect(a.container.querySelector('.res-bgcar.is-arriving')).not.toBeNull(), { timeout: 5000 })
  cleanup()

  const again = setup({ get: READY })
  const b = render(<ApiFlow api={again.api} caseId="c1" />)
  await waitFor(() => expect(b.container.querySelector('.res-bgcar')).not.toBeNull())
  expect(b.container.querySelector('.res-bgcar.is-arriving')).toBeNull()
})

it('결과 없음·분석 중단도 새 모양 틀이고, 결과 없음에서는 「다시 찾기」(RETRY_SEARCH)와 「처음으로」를 둔다', async () => {
  const EMPTY = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_empty_001')!.view
  const { m, api } = setup({ get: EMPTY })
  m.sendCommand.mockResolvedValue(ok(SEARCHING, 202))
  const { container, findByText, getAllByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText(/말씀하신 장면을 찾지 못했어요/)
  expect(container.querySelector('.rs.state-page.noresult')).not.toBeNull()
  expect(getAllByText('새 신고')).toHaveLength(1) // 헤더
  expect(getAllByText('처음으로')).toHaveLength(1) // 본문 고정 출구(#410)
  // case가 실은 동작 중 보낼 수 있는 것(RETRY_SEARCH)만 버튼으로 — 같은 조건으로 다시 찾는다
  const retry = EMPTY.notices.find((n) => n.actions.includes('RETRY_SEARCH'))
  if (retry) {
    fireEvent.click(getAllByText('다시 찾기')[0])
    await waitFor(() =>
      expect(m.sendCommand).toHaveBeenCalledWith('c1', EMPTY.case_rev, { kind: 'RUN_NOTICE_ACTION', payload: { notice_code: retry.code, action: 'RETRY_SEARCH' } }),
    )
  }
  expect(retry).toBeDefined()
  cleanup()

  const s = setup({ get: STOPPED })
  const r = render(<ApiFlow api={s.api} caseId="c1" />)
  await r.findByText('다시 찾기')
  expect(r.container.querySelector('.rs.state-page.stopped .state-head')).not.toBeNull()
  expect(r.container.querySelector('.panel-t, .page-title')).toBeNull()
})

it('클립 준비 실패(#482)는 실패 화면에서 다시 시도 안내 없이 다른 후보와 「처음으로」를 두고, 후보를 고르면 SELECT_OTHER_CANDIDATE다', async () => {
  // 클립은 후보를 고른 뒤에 만든다 — 고른 후보 하나와 다른 후보 하나를 둔다
  const c = SNAPSHOTS.map((s) => s.view).find((v) => v.candidates.length > 0)!.candidates[0]
  const two = { candidates: [{ ...c, selected: true }, { ...c, candidate_id: 'cand_other', selected: false }] }
  const failedView = view({
    ...two,
    case_rev: 9,
    stage: 'EVIDENCE_REVIEW',
    evidence: null,
    notices: [{ code: 'recording.incident_clip_build_failed', severity: 'ERROR', blocking: true, message_key: 'notice.incident_clip_build_failed', actions: [] }],
  })
  const { m, api } = setup({ get: failedView })
  m.sendCommand.mockResolvedValue(ok(SEARCHING, 202))
  const { container, findByText, getByText, getAllByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText('이 장면의 영상을 준비하지 못했어요.')
  expect(container.textContent).not.toContain('다시 시도하면')
  expect(getByText('처음으로')).toBeTruthy()
  const other = two.candidates.find((c) => !c.selected)!
  fireEvent.click(getAllByText('이 장면으로 다시 준비')[0])
  await waitFor(() =>
    expect(m.sendCommand).toHaveBeenCalledWith('c1', 9, { kind: 'SELECT_OTHER_CANDIDATE', payload: { candidate_id: other.candidate_id } }),
  )
})

it('결과 없음에서 [다시 찾기]를 누르면 탐색 job이 도는 동안 진행 화면이고 [다시 찾기]가 사라진다(#426)', async () => {
  // case는 stage를 CANDIDATE_REVIEW에 두고 결과 없음 notice도 남긴다 — running_jobs만 달라진다
  const EMPTY = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_empty_001')!.view
  const { m, api } = setup({ get: EMPTY })
  m.sendCommand.mockResolvedValue(ok({ ...EMPTY, case_rev: EMPTY.case_rev + 1, running_jobs: [{ ...JOBS[0], status: 'QUEUED' }] }, 202))
  const { container, findByText, getByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText(/말씀하신 장면을 찾지 못했어요/)
  fireEvent.click(getByText('다시 찾기'))
  await waitFor(() => expect(container.querySelector('.rs.flow')).not.toBeNull())
  expect(queryByText('다시 찾기')).toBeNull()
  expect(m.sendCommand).toHaveBeenCalledTimes(1)
})

// #410 — 설명 고쳐 다시 찾기. notice가 EDIT_HINT를 실으면 입력 화면을 열고, 거기서 EDIT_HINT command로 보낸다.
const EMPTY = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_empty_001')!.view

it('결과 없음에서 [설명 고치기]는 이전 설명을 채운 입력 화면을 열고, [고친 내용으로 찾기]는 EDIT_HINT command를 보낸다', async () => {
  const empty = { ...EMPTY, description: '저녁에 흰 차가 끼어들었어요' }
  const { m, api } = setup({ get: empty })
  m.sendCommand.mockResolvedValue(ok({ ...SEARCHING, case_rev: empty.case_rev + 1 }, 202))
  const { container, findByText, getByText, getByLabelText } = render(<ApiFlow api={api} caseId="c1" />)

  fireEvent.click(await findByText('설명 고치기'))
  const input = getByLabelText('어떤 상황이었나요?') as HTMLTextAreaElement
  expect(input.value).toBe('저녁에 흰 차가 끼어들었어요')
  // 「고친 내용으로 찾기」가 먼저 · 강조, 「처음으로」는 약하게
  const buttons = [...container.querySelectorAll('.hint-page .rs-actions button')].map((b) => [b.textContent, b.className])
  expect(buttons).toEqual([
    ['고친 내용으로 찾기', 'rs-btn pri'],
    ['처음으로', 'rs-btn sec'],
  ])

  fireEvent.change(input, { target: { value: '  저녁 6시쯤 흰 SUV가 실선을 넘어 끼어들었어요 ' } })
  fireEvent.click(getByText('고친 내용으로 찾기'))
  await findByText('분석 중단')
  expect(m.sendCommand).toHaveBeenCalledWith('c1', empty.case_rev, {
    kind: 'EDIT_HINT',
    payload: { description: '저녁 6시쯤 흰 SUV가 실선을 넘어 끼어들었어요' },
  })
})

it('설명이 비어 있으면 [고친 내용으로 찾기]를 누를 수 없고, 뒤로 가면 결과 없음 화면이다', async () => {
  const { m, api } = setup({ get: { ...EMPTY, description: '' } })
  const { findByText, getByText, getByLabelText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('설명 고치기'))
  expect(getByText('고친 내용으로 찾기').closest('button')!.disabled).toBe(true)
  fireEvent.change(getByLabelText('어떤 상황이었나요?'), { target: { value: '   ' } })
  expect(getByText('고친 내용으로 찾기').closest('button')!.disabled).toBe(true)
  fireEvent.click(getByLabelText('뒤로'))
  await findByText(/말씀하신 장면을 찾지 못했어요/)
  expect(m.sendCommand).not.toHaveBeenCalled()
})

it('결과 없음에 hint_unclear가 함께 붙으면 그 문구도 보이고, [설명 고치기]는 하나다', async () => {
  const both = { ...EMPTY, notices: [...EMPTY.notices, { ...notice('search.hint_unclear', ['EDIT_HINT']), message_key: 'notice.hint_unclear' }] }
  const { api } = setup({ get: both })
  const { findAllByText, getByText } = render(<ApiFlow api={api} caseId="c1" />)
  expect(await findAllByText('설명 고치기')).toHaveLength(1)
  expect(getByText(/입력하신 내용에서 확실한 단서를 찾지 못해 넓게 찾아봤어요/)).toBeTruthy()
})

// #431 — 위반 미관찰도 EDIT_HINT를 싣는다. 주 출구는 「다른 후보 보기」라, 다른 후보가 있으면 버튼은 둘 다 보조다
const NOT_OBSERVED_BASE = SNAPSHOTS.map((s) => s.view).find((v) => v.stage === 'EVIDENCE_REVIEW' && v.evidence === null)!
const notObserved = (candidates: CaseView['candidates']): CaseView => ({
  ...NOT_OBSERVED_BASE,
  description: '흰 차',
  candidates,
  notices: [{ ...notice('evidence.visual_event_not_observed', ['EDIT_HINT']), message_key: 'notice.visual_event_not_observed' }],
})

it('위반 미관찰에서 [설명 고치기]는 입력 화면을 열고 EDIT_HINT command를 보낸다 — 다른 후보가 있으면 버튼은 보조', async () => {
  const first = SNAPSHOTS.flatMap((s) => s.view.candidates)[0]
  const v = notObserved([
    { ...first, selected: true },
    { ...first, candidate_id: `${first.candidate_id}-2`, selected: false },
  ])
  const { m, api } = setup({ get: v })
  m.sendCommand.mockResolvedValue(ok({ ...SEARCHING, case_rev: v.case_rev + 1 }, 202))
  const { container, findByText, getByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText('설명 고치기')
  const buttons = [...container.querySelectorAll('.notobs .state-actions button')].map((b) => [b.textContent, b.className])
  expect(buttons).toEqual([
    ['설명 고치기', 'rs-btn sec'],
    ['처음으로', 'rs-btn sec'],
  ])

  fireEvent.click(getByText('설명 고치기'))
  fireEvent.click(getByText('고친 내용으로 찾기'))
  await findByText('분석 중단')
  expect(m.sendCommand).toHaveBeenCalledWith('c1', v.case_rev, { kind: 'EDIT_HINT', payload: { description: '흰 차' } })
})

it('위반 미관찰에 다른 후보가 없으면 설명 입력란을 화면에 바로 두고, [고친 내용으로 찾기]는 EDIT_HINT command를 보낸다', async () => {
  const v = notObserved([])
  const { m, api } = setup({ get: v })
  m.sendCommand.mockResolvedValue(ok({ ...SEARCHING, case_rev: v.case_rev + 1 }, 202))
  const { container, findByText, getByLabelText, getByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText('고친 내용으로 찾기') // 불러오기 전 업로드 화면에도 같은 이름의 입력칸이 있다
  const input = getByLabelText('어떤 상황이었나요?') as HTMLTextAreaElement
  expect(input.value).toBe('흰 차')
  expect(queryByText('설명 고치기')).toBeNull()
  const buttons = [...container.querySelectorAll('.notobs .rs-actions button')].map((b) => [b.textContent, b.className])
  expect(buttons).toEqual([
    ['고친 내용으로 찾기', 'rs-btn pri'],
    ['처음으로', 'rs-btn sec'],
  ])

  fireEvent.change(input, { target: { value: '흰 SUV가 실선을 넘었어요' } })
  fireEvent.click(getByText('고친 내용으로 찾기'))
  await waitFor(() =>
    expect(m.sendCommand).toHaveBeenCalledWith('c1', v.case_rev, { kind: 'EDIT_HINT', payload: { description: '흰 SUV가 실선을 넘었어요' } }),
  )
})

it('단서 정리 중 중단(EDIT_HINT만 실림)에서도 [설명 고치기]로 다시 찾는다', async () => {
  const stopped = view({ case_rev: 3, stage: 'SEARCHING', description: '흰 차', notices: [notice('case.analysis_stopped', ['EDIT_HINT'])] })
  const { m, api } = setup({ get: stopped })
  m.sendCommand.mockResolvedValue(ok({ ...SEARCHING, case_rev: 4 }, 202))
  const { findByText, getByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('설명 고치기'))
  fireEvent.click(getByText('고친 내용으로 찾기'))
  await findByText('분석 중단')
  expect(m.sendCommand).toHaveBeenCalledWith('c1', 3, { kind: 'EDIT_HINT', payload: { description: '흰 차' } })
  expect(queryByText('이 동작은 아직 연결되지 않았어요.')).toBeNull()
})

// #449 — 입력형 command. 결과 화면에서 번호판 · 시각을 직접 넣으면 새 값만 보낸다(case-command §12)
const RESULT = SNAPSHOTS.map((s) => s.view).find((v) => v.package && v.evidence)!

it.each([
  ['2026-10-29T23:30:00Z', '2026-10-30T08:30:00+09:00'],
  ['2026-12-31T23:30:00-05:00', '2027-01-01T13:30:00+09:00'],
  ['2026-08-24T18:05:12+09:00', '2026-08-24T18:05:12+09:00'],
])('발생시각 %s를 수정 없이 저장해도 같은 순간을 보낸다', async (original, expected) => {
  const current = structuredClone(RESULT)
  current.evidence!.event_time_display.value = original
  current.package!.report_fields.occurred_at = original
  const { m, api } = setup({ get: current })
  m.sendCommand.mockResolvedValue(ok({ ...current, case_rev: current.case_rev + 1 }))
  const { findByText, getByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('시각 수정하기'))
  fireEvent.click(getByText('저장'))
  await waitFor(() => expect(m.sendCommand).toHaveBeenCalledWith('c1', current.case_rev, {
    kind: 'EDIT_EVENT_TIME', payload: { value: expected },
  }))
  expect(Date.parse(expected)).toBe(Date.parse(original))
})

it('「번호판 직접 입력」은 번호판 확인 화면의 입력칸을 바로 열고, 저장하면 MANUAL_PLATE_INPUT을 보낸다', async () => {
  const abstained = { ...RESULT, notices: [{ ...notice('evidence.plate_abstained', ['MANUAL_PLATE_INPUT']), message_key: 'notice.plate_abstained' }] }
  const { m, api } = setup({ get: abstained })
  m.sendCommand.mockResolvedValue(ok({ ...abstained, case_rev: abstained.case_rev + 1 }))
  const { findByText, getByRole, getByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('번호판 직접 입력'))
  fireEvent.change(getByRole('textbox', { name: '차량 번호' }), { target: { value: ' 12가3456 ' } })
  fireEvent.click(getByText('저장'))
  await waitFor(() => expect(m.sendCommand).toHaveBeenCalled())
  expect(m.sendCommand).toHaveBeenCalledWith('c1', abstained.case_rev, { kind: 'MANUAL_PLATE_INPUT', payload: { value: '12가3456' } })
})

it('시각이 없어 묶음이 막힌 알림의 「시각 직접 입력」은 시각 입력 화면을 열고, 한국 시간 오프셋을 붙여 EDIT_EVENT_TIME을 보낸다', async () => {
  const missing = {
    ...RESULT,
    notices: [{ code: 'evidence.event_time_missing', severity: 'WARN', blocking: true, message_key: 'notice.event_time_missing', actions: ['EDIT_EVENT_TIME'] } as Notice],
  }
  const { m, api } = setup({ get: missing })
  m.sendCommand.mockResolvedValue(ok({ ...missing, case_rev: missing.case_rev + 1, notices: [] }))
  const { findByText, getByLabelText, getByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
  expect(await findByText('발생 시각을 알 수 없어요. 시각을 직접 입력하면 신고자료를 완성할 수 있어요.')).toBeTruthy()
  fireEvent.click(getByText('시각 직접 입력'))
  fireEvent.change(getByLabelText('날짜'), { target: { value: '2026-08-24' } })
  fireEvent.change(getByLabelText('시간'), { target: { value: '18:31' } })
  fireEvent.click(getByText('저장'))
  await waitFor(() => expect(m.sendCommand).toHaveBeenCalled())
  expect(m.sendCommand).toHaveBeenCalledWith('c1', missing.case_rev, { kind: 'EDIT_EVENT_TIME', payload: { value: '2026-08-24T18:31:00+09:00' } })
  expect(queryByText('한국 시간 기준으로 저장해요.')).toBeNull() // 결과 화면으로 돌아간다
})

it('시각 입력 화면의 날짜·시간 칸은 「한국 시간 기준」 안내를 설명으로 읽는다(#559)', async () => {
  const { api } = setup({ get: RESULT })
  const { findByText, getByLabelText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('시각 수정하기'))
  for (const name of ['날짜', '시간']) {
    const id = getByLabelText(name).getAttribute('aria-describedby')!
    expect(document.getElementById(id)?.textContent?.trim()).toBe('한국 시간 기준으로 저장해요.')
  }
})

it('결과 화면 발생 시간의 「시각 수정하기」는 지금 값을 채운 입력 화면을 열고, 취소하면 보내지 않는다', async () => {
  const { m, api } = setup({ get: RESULT })
  const { findByText, getByLabelText, getByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('시각 수정하기'))
  // fixture 값은 2026-08-24T18:05:12+09:00
  expect((getByLabelText('날짜') as HTMLInputElement).value).toBe('2026-08-24')
  expect((getByLabelText('시간') as HTMLInputElement).value).toBe('18:05:12')
  fireEvent.click(getByText('취소'))
  await findByText('시각 수정하기')
  expect(m.sendCommand).not.toHaveBeenCalled()
})

it('결과 화면에서 고친 제목은 command 없이 화면에만 남고, 「일자 수정하기」도 같은 시각 입력 화면을 연다', async () => {
  const { m, api } = setup({ get: RESULT })
  const { findByText, getByLabelText, getByText, container } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('제목 수정하기'))
  fireEvent.change(getByLabelText('제목'), { target: { value: '끼어들기 신고' } })
  fireEvent.click(getByText('저장'))
  expect(container.textContent).toContain('끼어들기 신고')
  expect(container.textContent).toContain('이 화면에서만 바꿨어요')
  fireEvent.click(getByText('일자 수정하기'))
  expect((getByLabelText('날짜') as HTMLInputElement).value).toBe('2026-08-24')
  fireEvent.click(getByText('취소'))
  await findByText('끼어들기 신고')
  expect(m.sendCommand).not.toHaveBeenCalled()
})

it('서버가 돌려준 case를 이 브라우저에 기억하고, 없는 case 주소를 열어도 기억은 덮지 않는다', async () => {
  localStorage.clear()
  const live = setup({ get: SEARCHING })
  const a = render(<ApiFlow api={live.api} caseId="c1" />)
  await a.findByText('분석 중단')
  expect(localStorage.getItem('daesingo.lastCase')).toBe(SEARCHING.case_id)
  a.unmount()

  const gone = setup()
  gone.m.getView.mockResolvedValue({ ok: false, status: 404, error: { code: 'http.not_found', message_key: 'http.not_found' }, caseView: null })
  const b = render(<ApiFlow api={gone.api} caseId="other" />)
  await b.findByText('진행 정보를 찾을 수 없어요')
  expect(localStorage.getItem('daesingo.lastCase')).toBe(SEARCHING.case_id)
})

it('기억한 case가 서버에서 지워졌으면 잊는다 — 「찾을 수 없어요」 대신 새 신고로 시작한다', async () => {
  localStorage.setItem('daesingo.lastCase', 'old')
  const { m, api } = setup()
  m.getView.mockResolvedValue({ ok: false, status: 404, error: { code: 'http.not_found', message_key: 'http.not_found' }, caseView: null })
  const { queryByText } = render(<ApiFlow api={api} caseId="old" remembered />)
  await waitFor(() => expect(localStorage.getItem('daesingo.lastCase')).toBeNull())
  expect(queryByText('진행 정보를 찾을 수 없어요')).toBeNull()
})

it('candidate video request and polling keep the failure comparison visible without selecting', async () => {
  const c = SNAPSHOTS.flatMap((s) => s.view.candidates)[0]
  const initial = view({
    case_rev: 8, stage: 'EVIDENCE_REVIEW', evidence: null,
    candidates: [
      { ...c, candidate_id: 'first', rank: 1, selected: true, video_preview: { status: 'NOT_REQUESTED', clip_ref: null } },
      { ...c, candidate_id: 'second', rank: 2, selected: false, video_preview: { status: 'NOT_REQUESTED', clip_ref: null } },
    ],
    notices: [{ code: 'recording.incident_clip_build_failed', severity: 'ERROR', blocking: true, message_key: 'notice.incident_clip_build_failed', actions: [] }],
  })
  const pending: CaseView = { ...initial, case_rev: 9,
    candidates: initial.candidates.map((candidate) => candidate.selected ? candidate : { ...candidate, video_preview: { status: 'PREPARING', clip_ref: null } }),
    running_jobs: [{ job_id: 'preview', kind: 'CANDIDATE_VIDEO_PREVIEW', label_key: 'job.candidate_video_preview', status: 'RUNNING' }],
  }
  const ready: CaseView = { ...pending, running_jobs: [], candidates: pending.candidates.map((candidate) => candidate.selected ? candidate : { ...candidate, video_preview: { status: 'READY', clip_ref: 'clip_second' } }) }
  const { m, api } = setup({ get: initial })
  const screen = render(<ApiFlow api={api} caseId="c1" />)
  await screen.findByRole('button', { name: '2번 후보 영상 보기' })
  m.sendCommand.mockResolvedValue(ok(pending, 202))
  m.getView.mockResolvedValue(ok(ready))
  fireEvent.click(screen.getByRole('button', { name: '2번 후보 영상 보기' }))
  await screen.findByText('영상 준비 중')
  expect(screen.getByRole('button', { name: '이 장면으로 다시 준비' }).hasAttribute('disabled')).toBe(false)
  await waitFor(() => expect(screen.container.querySelector('video')?.getAttribute('src')).toBe('/candidate-video/clip_second'), { timeout: 4000 })
  expect(m.sendCommand).toHaveBeenCalledExactlyOnceWith('c1', 8, { kind: 'REQUEST_CANDIDATE_VIDEO_PREVIEW', payload: { candidate_id: 'second' } })
  expect(screen.getByText('이 장면의 영상을 준비하지 못했어요.')).toBeTruthy()
})

it('결과 화면에서 연 「어떻게 정했는지」는 기준 후보 영상을 보인다 — ApiFlow가 playback을 넘긴다', async () => {
  const initial: CaseView = { ...RESULT, case_id: 'c1', running_jobs: [],
    candidates: RESULT.candidates.map((c) => c.selected ? { ...c, video_preview: { status: 'READY', clip_ref: 'basis-clip' } } : c),
  }
  const { api } = setup({ get: initial })
  const screen = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await screen.findByRole('button', { name: '신고서를 어떻게 작성했는지 궁금하신가요?' }))
  await waitFor(() => expect(screen.container.querySelector('.details-scene video')?.getAttribute('src')).toBe('/candidate-video/basis-clip'))
})

it.each(['result', 'not-observed', 'failed', 'awaiting'] as const)('a single candidate has a playback entry on the %s screen', async (surface) => {
  const original = surface === 'result' ? RESULT : surface === 'awaiting' ? AWAITING : notObserved(RESULT.candidates)
  const selected = original.candidates.find((c) => c.selected) ?? RESULT.candidates[0]
  const initial: CaseView = { ...original, case_id: 'c1', case_rev: 8, running_jobs: [],
    candidates: [{ ...selected, candidate_id: 'only', rank: 1, selected: true,
      video_preview: { status: 'NOT_REQUESTED', clip_ref: null } }],
    ...(surface === 'failed' ? { evidence: null, package: null, notices: [{
      code: 'recording.incident_clip_build_failed', severity: 'ERROR', blocking: true,
      message_key: 'notice.incident_clip_build_failed', actions: [],
    }] } : {}),
  }
  const { m, api } = setup({ get: initial })
  const pending: CaseView = { ...initial, case_rev: 9,
    candidates: initial.candidates.map((c) => ({ ...c, video_preview: { status: 'PREPARING', clip_ref: null } })),
    running_jobs: [{ job_id: 'preview', kind: 'CANDIDATE_VIDEO_PREVIEW', label_key: 'job.candidate_video_preview', status: 'RUNNING' }],
  }
  m.sendCommand.mockResolvedValue(ok(pending, 202))
  m.getView.mockResolvedValueOnce(ok(initial)).mockResolvedValue(ok({ ...pending, running_jobs: [],
    candidates: pending.candidates.map((c) => ({ ...c, video_preview: { status: 'READY', clip_ref: 'only-clip' } })),
  }))
  const screen = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await screen.findByRole('button', { name: '1번 후보 영상 보기' }))
  await waitFor(() => expect(screen.container.querySelector('video')?.getAttribute('src')).toBe('/candidate-video/only-clip'), { timeout: 4000 })
  expect(screen.queryByRole('button', { name: /다른 후보/ })).toBeNull()
  expect(m.sendCommand).toHaveBeenCalledExactlyOnceWith('c1', 8, { kind: 'REQUEST_CANDIDATE_VIDEO_PREVIEW', payload: { candidate_id: 'only' } })
})

// 하위 화면(다른 후보 · 번호판 · 시각 · 근거)은 브라우저 기록에 한 칸씩 남는다 — 브라우저 뒤로가기도 결과 화면으로 돌아온다
// 「다른 장면이었나요?」는 신고 상황 응답 전 화면에 있다
const WITH_OTHER = {
  ...AWAITING,
  candidates: [...AWAITING.candidates, { ...AWAITING.candidates[0], candidate_id: 'cand_other', selected: false }],
}
const backTo = async (findByText: (t: RegExp) => Promise<HTMLElement>) => {
  act(() => history.back())
  await findByText(/다른 장면이었나요\?/)
}

it('결과 화면에서 「다른 장면이었나요?」로 연 다른 후보 화면은 브라우저 뒤로가기로 결과 화면에 돌아온다', async () => {
  const { api } = setup({ get: WITH_OTHER })
  const { findByText, getByRole } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText(/다른 장면이었나요\?/))
  expect(getByRole('heading', { name: '다른 후보' })).toBeTruthy()
  await backTo(findByText)
})

it('화면 안 「뒤로」로 닫으면 브라우저 기록도 한 칸 돌아가 빈칸이 남지 않는다', async () => {
  const { api } = setup({ get: WITH_OTHER })
  const { findByText, getByLabelText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText(/다른 장면이었나요\?/))
  expect(history.state?.sub).toBe(1)
  fireEvent.click(getByLabelText('뒤로'))
  await findByText(/다른 장면이었나요\?/)
  await waitFor(() => expect(history.state?.sub ?? 0).toBe(0))
  // 다시 열어도 깊이는 1이다 — 닫은 칸 위에 쌓이지 않는다
  fireEvent.click(await findByText(/다른 장면이었나요\?/))
  expect(history.state?.sub).toBe(1)
})

it('다른 후보를 고르면 하위 화면이 닫히고 쌓인 기록도 함께 정리된다', async () => {
  const { m, api } = setup({ get: WITH_OTHER })
  m.sendCommand.mockResolvedValue(ok(SEARCHING, 202))
  const { findByText, getAllByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText(/다른 장면이었나요\?/))
  fireEvent.click(getAllByText('이 장면으로 다시 준비')[0])
  await waitFor(() => expect(m.sendCommand).toHaveBeenCalled())
  await waitFor(() => expect(history.state?.sub ?? 0).toBe(0))
})

it('결과 없음에서 연 「설명 고치기」도 브라우저 뒤로가기로 결과 없음 화면에 돌아온다', async () => {
  const { m, api } = setup({ get: { ...EMPTY, description: '흰 차' } })
  const { findByText, getByLabelText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('설명 고치기'))
  expect(getByLabelText('어떤 상황이었나요?')).toBeTruthy()
  act(() => history.back())
  await findByText(/말씀하신 장면을 찾지 못했어요/)
  expect(m.sendCommand).not.toHaveBeenCalled()
})

it('하위 화면을 연 채 새로고침해 남은 기록 깊이는 처음 열 때 0으로 맞춘다', async () => {
  history.replaceState({ sub: 1 }, '', '/?api')
  const { api } = setup({ get: WITH_OTHER })
  const { findByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText(/다른 장면이었나요\?/)
  expect(history.state?.sub).toBe(0)
})

it('서버가 업로드를 거절하면 그 이유를 업로드 칸에 보인다', async () => {
  const { m, api } = setup()
  m.uploadSource.mockResolvedValue({ ok: false, status: 413, error: { code: 'http.payload_too_large', message_key: 'http.payload_too_large' }, caseView: null })
  const { container, findByText, getByText } = render(<ApiFlow api={api} />)
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['x'], 'big.mp4')] } })
  fireEvent.click(getByText('동의하고 올리기'))
  expect(await findByText(/서버가 받을 수 있는 크기보다 커요/)).toBeTruthy()
})

it('업로드 전 동의에서 취소하면 서버에 아무것도 보내지 않는다', () => {
  const { m, api } = setup()
  const { container, getByText, queryByText } = render(<ApiFlow api={api} />)
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['x'], 'a.mp4')] } })
  fireEvent.click(getByText('취소'))
  expect(m.createCase).not.toHaveBeenCalled()
  expect(m.uploadSource).not.toHaveBeenCalled()
  expect(queryByText(/^업로드 중/)).toBeNull()
})

it('같은 신고에서는 한 번 동의하면 파일을 더 골라도 다시 묻지 않는다(새 신고는 페이지를 새로 열어 다시 묻는다)', async () => {
  const { m, api } = setup()
  const { container, findByText, getByText, queryByText } = render(<ApiFlow api={api} />)
  const input = container.querySelector('input[type=file]')!
  fireEvent.change(input, { target: { files: [new File(['x'], 'a.mp4')] } })
  fireEvent.click(getByText('동의하고 올리기'))
  await findByText(/^업로드 완료/)
  fireEvent.change(input, { target: { files: [new File(['x'], 'b.mp4')] } })
  expect(queryByText('동의하고 올리기')).toBeNull()
  await waitFor(() => expect(m.uploadSource).toHaveBeenCalledTimes(2))
})

it('동의 창을 닫으면 포커스가 「파일 선택」으로 돌아온다', () => {
  const { api } = setup()
  const { container, getByText } = render(<ApiFlow api={api} />)
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['x'], 'a.mp4')] } })
  fireEvent.click(getByText('취소'))
  expect(document.activeElement?.textContent).toBe('파일 선택')
})
