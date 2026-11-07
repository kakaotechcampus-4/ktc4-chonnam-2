// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { OfficialSampleEntry } from '../screens/OfficialSampleEntry'
import { createPublicSamplesApi } from '../api/publicSamples'
import { SNAPSHOTS } from '../contracts/fixtures'
afterEach(cleanup)

it('null 샘플 항목을 invalid response로 반환한다', async () => {
  const client = createPublicSamplesApi({ fetch: vi.fn(async () => new Response(JSON.stringify({ samples: [null] }), { status: 200 })) })
  await expect(client.listSamples()).resolves.toMatchObject({ ok: false, error: { code: 'web.invalid_response' } })
})

it('깨진 등록 CaseView를 화면에 전달하지 않는다', async () => {
  const client = createPublicSamplesApi({ fetch: vi.fn(async () => new Response(JSON.stringify({ case_id: 'owned', case_view: {} }), { status: 201 })) })
  await expect(client.registerSample('owned', 'test-only')).resolves.toMatchObject({ ok: false, error: { code: 'web.invalid_response' } })
})

it.each(['candidates', 'progress', 'notices', 'running_jobs'])('%s의 null 항목은 거부한다', async field => {
  const body = { case_id: 'owned', case_view: { ...SNAPSHOTS[0].view, case_id: 'owned', [field]: [null] } }
  const client = createPublicSamplesApi({ fetch: vi.fn(async () => new Response(JSON.stringify(body), { status: 201 })) })
  await expect(client.registerSample('owned', 'test-only')).resolves.toMatchObject({ ok: false, error: { code: 'web.invalid_response' } })
})

it('실제 ApiFlow의 재조회가 지연돼도 A1에서 파일 입력을 노출하지 않는다', async () => {
  history.replaceState(null, '', '/?case=owned')
  const view = { ...SNAPSHOTS[0].view, case_id: 'owned', case_rev: 1, stage: 'SEARCHING',
    manifest_summary: { ...SNAPSHOTS[0].view.manifest_summary, file_count: 10, ok_file_count: 10 } }
  let reads = 0
  const client = createPublicSamplesApi({ fetch: vi.fn(async input => {
    if (String(input) === '/public/samples') return new Response(JSON.stringify({ samples: [] }), { status: 200 })
    reads++
    if (reads > 1) return new Promise<Response>(() => {})
    return new Response(JSON.stringify(view), { status: 200 })
  }) })
  render(<OfficialSampleEntry client={client} caseId="owned" />)
  await waitFor(() => expect(reads).toBeGreaterThan(1))
  expect(document.querySelector('input[type=file]')).toBeNull()
  expect(screen.queryByText('영상을 먼저 올려 주세요.')).toBeNull()
})
