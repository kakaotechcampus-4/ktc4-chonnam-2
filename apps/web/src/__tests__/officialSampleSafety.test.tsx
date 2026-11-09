// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { OfficialSampleEntry } from '../screens/OfficialSampleEntry'
import { createPublicSamplesApi } from '../api/publicSamples'
import { SNAPSHOTS } from '../contracts/fixtures'
import { ApiFlow } from '../screens/ApiFlow'
import { deferredWork } from '../screens/ResultScreen'
afterEach(cleanup)

it('저장된 정정과 미발주 영상 생성을 기존 notice로 구분한다', async () => {
  const view = { ...SNAPSHOTS[0].view, case_id: 'owned', case_rev: 2, stage: 'SEARCHING' as const,
    notices: [{ code: 'public.local_work_not_queued', severity: 'WARN' as const, blocking: false,
      message_key: 'notice.public_local_jobs_stopped', actions: [] }] }
  const fetcher = vi.fn(async (_input: RequestInfo | URL) => new Response(JSON.stringify(view), { status: 200 }))
  const client = createPublicSamplesApi({ fetch: fetcher })
  render(<ApiFlow api={client.cases} caseId="owned" />)
  const saved = await screen.findByText(/수정 내용은 저장했어요.*긴급 중단/)
  expect(saved.textContent).toContain('이번 요청에서는 영상 생성을 시작하지 않았어요')
  expect(saved.textContent).not.toContain('자동으로 다시 만들지 않아요')
  expect(fetcher.mock.calls.every(args => !String(args[0]).endsWith('/commands'))).toBe(true)
})

it('결과 화면은 보류 안내를 카드에 한 번만, 영상 상태에 맞게 보인다 (#676)', async () => {
  const happy = SNAPSHOTS.find((s) => s.view.stage === 'READY' && s.view.package?.artifact_ref)!.view
  const notices = [...happy.notices, { code: 'public.local_work_not_queued', severity: 'WARN' as const, blocking: false,
    message_key: 'notice.public_local_local_concurrent', actions: [] }]
  const view = { ...happy, case_id: 'owned', notices, package: { ...happy.package!, plate_image_ref: null } }
  const client = createPublicSamplesApi({ fetch: vi.fn(async () => new Response(JSON.stringify(view), { status: 200 })) })
  render(<ApiFlow api={client.cases} caseId="owned" />)
  expect(await screen.findAllByText('번호판 이미지는 만들지 않았어요. 없어도 신고자료는 완성돼요.')).toHaveLength(1)
  expect(screen.queryByText(/영상 생성은 요청하지 않았어요/)).toBeNull()
  // 영상이 없으면 영상이 보류됐다고 말하고 다음 행동을 알린다
  const none = { ...view, package: { ...view.package, artifact_ref: null } }
  expect(deferredWork(none, false)?.text).toBe('다른 작업이 진행 중이라 신고용 영상을 만들지 않았어요. 작업이 끝나면 「신고용 영상 만들기」를 눌러 주세요.')
  // 영상·이미지 작업이 진행 중이면 무엇이 보류됐는지 모른다 — 「만들지 않았어요」로 진행 중인 작업을 가리지 않는다
  const neutral = '다른 작업이 진행 중이라 영상·이미지를 새로 만들지 않았어요. 진행 중인 작업이 끝나면 다시 확인해 주세요.'
  for (const kind of ['REPORT_VIDEO_EXPORT', 'PLATE_IMAGE_EXPORT']) {
    const running = { ...view, running_jobs: [{ job_id: 'j1', kind, status: 'RUNNING', label_key: null }] } as unknown as typeof view
    expect(deferredWork(running, false)).toEqual({ text: neutral, tone: 'review' })
  }
})

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
