// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { OfficialSampleEntry } from '../screens/OfficialSampleEntry'
import { createPublicSamplesApi } from '../api/publicSamples'
import { SNAPSHOTS } from '../contracts/fixtures'
import { errorMessage } from '../contracts/labels'

vi.mock('../screens/ApiFlow', () => ({ ApiFlow: (p: { caseId?: string | null }) => <p>기존 결과 흐름 {p.caseId}</p> }))
afterEach(cleanup)
beforeEach(() => { localStorage.clear(); history.replaceState(null, '', '/') })

const intake = { ...SNAPSHOTS[0].view, case_id: 'owned', case_rev: 1, stage: 'INTAKE' as const,
  manifest_summary: { ...SNAPSHOTS[0].view.manifest_summary, file_count: 10, ok_file_count: 10 }, running_jobs: [] }
const sample = { sample_id: 'test-only', label: '시험 샘플', example_hint: '시험 설명', duration_ms: 600000, byte_size: 100, file_count: 10 }
function setup(startStatus = 202) {
  const seen: { url: string; init?: RequestInit }[] = []
  const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input); seen.push({ url, init })
    let status = 200, body: unknown
    if (url === '/public/samples') body = { samples: [sample] }
    else if (url === '/public/session') { status = 201; body = { ok: true } }
    else if (url === '/cases') { status = 201; body = { case_id: 'owned', case_view: { ...intake, manifest_summary: { ...intake.manifest_summary, file_count: 0, ok_file_count: 0 } } } }
    else if (url.endsWith('/official-samples')) { status = 201; body = { case_id: 'owned', case_view: intake } }
    else if (url.endsWith('/commands')) {
      status = startStatus
      body = status === 202 ? { case_view: { ...intake, stage: 'SEARCHING', case_rev: 2 } }
        : { error: { code: 'public.budget', message_key: 'public.budget' }, case_view: null }
    } else body = intake
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  })
  const client = createPublicSamplesApi({ fetch: fetcher })
  render(<OfficialSampleEntry client={client} />)
  return { seen, fetcher, client }
}

it('서버 샘플→세션→Case→ID-only 등록 이후 명시적으로 분석하고 기존 흐름을 재사용한다', async () => {
  const { seen } = setup()
  fireEvent.click(await screen.findByRole('radio', { name: /시험 샘플/ }))
  fireEvent.click(screen.getByRole('button', { name: '샘플 준비' }))
  await screen.findByRole('button', { name: '분석 시작' })
  expect(seen.map(x => x.url)).toEqual(['/public/samples', '/public/session', '/cases', '/cases/owned/official-samples'])
  expect(JSON.parse(String(seen[3].init?.body))).toEqual({ sample_id: 'test-only' })
  expect(document.querySelector('input[type=file]')).toBeNull()
  expect(seen.every(x => x.init?.credentials === 'same-origin')).toBe(true)
  fireEvent.change(screen.getByRole('textbox', { name: '찾을 장면 설명' }), { target: { value: '시험 설명' } })
  fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
  await screen.findByText('기존 결과 흐름 owned')
  expect(seen.filter(x => x.url.endsWith('/commands'))).toHaveLength(1)
  expect(seen.some(x => x.url.endsWith('/sources'))).toBe(false)
})

it('429 예산 거부를 알리고 자동으로 분석을 재전송하지 않는다', async () => {
  const { seen } = setup(429)
  fireEvent.click(await screen.findByRole('radio', { name: /시험 샘플/ }))
  fireEvent.click(screen.getByRole('button', { name: '샘플 준비' }))
  fireEvent.click(await screen.findByRole('button', { name: '분석 시작' }))
  await screen.findByRole('alert')
  expect(screen.queryByText('기존 결과 흐름 owned')).toBeNull()
  expect(seen.filter(x => x.url.endsWith('/commands'))).toHaveLength(1)
})

it('다른 세션의 Case404를 새 세션 생성이나 임의 업로드로 우회하지 않는다', async () => {
  const seen: string[] = []
  const client = createPublicSamplesApi({ fetch: vi.fn(async input => {
    seen.push(String(input))
    return new Response(JSON.stringify(String(input) === '/public/samples' ? { samples: [sample] }
      : { error: { code: 'http.not_found', message_key: 'http.not_found' }, case_view: null }), { status: String(input) === '/public/samples' ? 200 : 404 })
  }) })
  render(<OfficialSampleEntry client={client} caseId="foreign" />)
  await screen.findByRole('alert')
  expect(seen).toEqual(expect.arrayContaining(['/public/samples', '/cases/foreign/view']))
  expect(seen).not.toContain('/public/session')
  expect(screen.queryByRole('button', { name: '샘플 준비' })).toBeNull()
})

it('준비 중 중복 클릭은 하나의 Case만 만들고 삭제202는 완료로 표시하지 않는다', async () => {
  const { client, seen } = setup()
  fireEvent.click(await screen.findByRole('radio', { name: /시험 샘플/ }))
  const button = screen.getByRole('button', { name: '샘플 준비' })
  fireEvent.click(button); fireEvent.click(button)
  await screen.findByRole('button', { name: '분석 시작' })
  expect(seen.filter(x => x.url === '/cases')).toHaveLength(1)
  vi.spyOn(client, 'deleteCase').mockResolvedValueOnce({ ok: true, status: 202, data: { state: 'DELETING' } })
    .mockResolvedValueOnce({ ok: true, status: 200, data: { state: 'DELETED' } })
  fireEvent.click(screen.getByRole('button', { name: '체험 데이터 삭제' }))
  await screen.findByText('삭제 중이에요. 완료 여부를 다시 확인할 수 있어요.')
  expect(screen.queryByText('삭제했어요.')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '삭제 다시 확인' }))
  await screen.findByText('삭제했어요.')
  await waitFor(() => expect(screen.queryByRole('button', { name: '분석 시작' })).toBeNull())
})

it.each([
  ['public.busy', 409, '이미 처리 중인 요청이 있어요. 진행 상태를 확인해 주세요.'],
  ['public.origin', 403, '이 주소에서는 요청을 보낼 수 없어요. 안내받은 체험 주소에서 다시 열어 주세요.'],
  ['public.stopped', 503, '지금은 새 분석을 받지 않고 있어요. 잠시 뒤 다시 확인해 주세요.'],
  ['public.jobs_stopped', 503, '서비스 점검으로 새 작업을 잠시 멈췄어요. 기존 결과를 확인해 주세요.'],
  ['public.unconfigured', 503, '지금은 체험을 열지 않았어요. 운영 준비가 끝난 뒤 다시 확인해 주세요.'],
  ['public.limit', 429, '체험 이용 한도에 도달했어요. 요청을 자동으로 다시 보내지 않아요.'],
] as const)('%s를 샘플과 결과 화면에서 구분하며 자동 재요청하지 않는다', async (code, status, text) => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify({ error: { code, message_key: code }, case_view: null }), { status }))
  render(<OfficialSampleEntry client={createPublicSamplesApi({ fetch: fetcher })} />)
  expect((await screen.findByRole('alert')).textContent).toContain(text)
  expect(errorMessage(code)).toBe(text) // ApiFlow의 결과/정정 오류도 같은 계약을 사용한다.
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('샘플 준비 전에 10분 한도와 보관 정책 미확정을 알리고 아직 요청하지 않는다', async () => {
  const { seen } = setup()
  await screen.findByRole('radio', { name: /시험 샘플/ })
  expect(screen.getByText(/한 번에 합계 10분까지/)).toBeTruthy()
  expect(screen.getByText(/보관·삭제 기간과 반복 횟수는 아직 확정되지 않았어요/)).toBeTruthy()
  expect(seen.map(x => x.url)).toEqual(['/public/samples'])
})

it('접근 거부 상태에서 사용자에게 Case라는 구현 용어를 표시하지 않는다', async () => {
  const client = createPublicSamplesApi({ fetch: vi.fn(async input => new Response(JSON.stringify(
    String(input) === '/public/samples' ? { samples: [] } : { error: { code: 'http.not_found', message_key: 'http.not_found' }, case_view: null }),
    { status: String(input) === '/public/samples' ? 200 : 404 })) })
  const result = render(<OfficialSampleEntry client={client} caseId="foreign" />)
  await screen.findByRole('alert')
  expect(result.container.textContent).not.toContain('Case')
})
