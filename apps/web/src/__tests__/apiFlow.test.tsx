// @vitest-environment jsdom
//
// `?api` 흐름 — 화면은 CaseView로 고르고, 버튼은 command로 이어진다(contract-case-command · contract-http-api §6).
// 서버가 없으므로 Api를 가짜로 끼운다.

import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
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
const AWAITING = SNAPSHOTS.map((s) => s.view).find((v) => v.notices.some((n) => n.code === 'case.situation_response_pending'))!

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
  const api = { ...m, frameUrl: () => '', assetUrl: () => '' } as unknown as Api
  return { m, api }
}

it('영상을 고르면 올라가고, [영상에서 찾아보기]에서 상황 설명과 함께 분석을 시작한다', async () => {
  const { m, api } = setup()
  m.sendCommand.mockResolvedValue(ok(SEARCHING, 202))
  const { container, getByRole, getByText, findByText } = render(<ApiFlow api={api} />)

  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['x'], 'a.mp4')] } })
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
  const { container, findByText, queryByText } = render(<ApiFlow api={api} />)
  const input = container.querySelector('input[type=file]')!

  fireEvent.change(input, { target: { files: [new File(['x'], 'a.mp4')] } })
  await findByText('업로드 중')
  fireEvent.change(input, { target: { files: [new File(['x'], 'b.mp4')] } })
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

  m.sendCommand.mockResolvedValue(ok({ ...SEARCHING, case_rev: 4 })) // 다시 찾으면 rev가 오른다
  fireEvent.click(getByText('다시 찾기'))
  await findByText('분석 중단')
  expect(m.sendCommand).toHaveBeenLastCalledWith('c1', 3, {
    kind: 'RUN_NOTICE_ACTION',
    payload: { notice_code: 'case.analysis_stopped', action: 'RETRY_SEARCH' },
  })
})

it('case 대기 timeout(#358)은 중단 화면에 timeout 문구로 보이고, [다시 찾기]는 RETRY_SEARCH다', async () => {
  const timedOut = view({ case_rev: 3, stage: 'SEARCHING', notices: [notice('case.analysis_timed_out', ['RETRY_SEARCH'])] })
  const { m, api } = setup({ get: timedOut })
  m.sendCommand.mockResolvedValue(ok({ ...SEARCHING, case_rev: 4 }, 202))
  const { findByText, getByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText('장면을 찾는 시간이 오래 걸려 멈췄어요.')
  expect(queryByText('분석을 중단했어요.')).toBeNull()
  fireEvent.click(getByText('다시 찾기'))
  await findByText('분석 중단')
  expect(m.sendCommand).toHaveBeenCalledWith('c1', 3, { kind: 'RUN_NOTICE_ACTION', payload: { notice_code: 'case.analysis_timed_out', action: 'RETRY_SEARCH' } })
})

it('찾는 중이 아닐 때(SEARCHING이 아닐 때)는 중단 버튼을 두지 않는다', async () => {
  const { api } = setup({ get: view({ case_rev: 5, stage: 'CANDIDATE_REVIEW', running_jobs: JOBS, candidates: BASE.candidates }) })
  const { findByText, queryByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText(/신고자료를 준비하고 있어요|사건을 찾고 있어요/)
  expect(queryByText('분석 중단')).toBeNull()
})

it('신고 상황 응답은 RECORD_SITUATION_RESPONSE로 보낸다', async () => {
  const { m, api } = setup({ get: AWAITING })
  m.sendCommand.mockResolvedValue(ok({ ...AWAITING, case_rev: AWAITING.case_rev + 1 }))
  const { findByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('맞아요'))
  await waitFor(() => expect(m.sendCommand).toHaveBeenCalled())
  expect(m.sendCommand).toHaveBeenCalledWith('c1', AWAITING.case_rev, { kind: 'RECORD_SITUATION_RESPONSE', payload: { value: 'CONFIRMED' } })
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

it('command가 없는 알림 버튼(직접 입력류)은 보내지 않고 안내한다', async () => {
  const stopped = view({ case_rev: 3, stage: 'SEARCHING', notices: [notice('case.analysis_stopped', ['MANUAL_PLATE_INPUT'])] })
  const { m, api } = setup({ get: stopped })
  const { findByText } = render(<ApiFlow api={api} caseId="c1" />)
  fireEvent.click(await findByText('번호판 직접 입력'))
  await findByText('이 동작은 아직 연결되지 않았어요.')
  expect(m.sendCommand).not.toHaveBeenCalled()
})

it('[영상에서 찾아보기] 뒤 진행 화면이 열리면 업로드 겉모습 복사본에서 자동차가 출발한다', async () => {
  const { m, api } = setup()
  m.sendCommand.mockResolvedValue(ok(SEARCHING, 202))
  const { container, getByText, findByText } = render(<ApiFlow api={api} />)
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['x'], 'a.mp4')] } })
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

it('위반 미관찰에 다른 후보가 없으면 [설명 고치기]를 강조한다', async () => {
  const v = notObserved([])
  const { api } = setup({ get: v })
  const { container, findByText } = render(<ApiFlow api={api} caseId="c1" />)
  await findByText('설명 고치기')
  const buttons = [...container.querySelectorAll('.notobs .state-actions button')].map((b) => [b.textContent, b.className])
  expect(buttons).toEqual([
    ['설명 고치기', 'rs-btn pri'],
    ['처음으로', 'rs-btn sec'],
  ])
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
