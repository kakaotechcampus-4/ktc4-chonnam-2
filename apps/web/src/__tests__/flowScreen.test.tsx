// @vitest-environment jsdom
//
// 진행 화면: 큰 제목·상태 줄·「나머지 작업은 계속」 안내는 progress와 notices에서만 읽는다.

import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import type { CaseView, Notice } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { FlowScreen } from '../screens/FlowScreen'

afterEach(cleanup)

const BASE = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.index === 1)!.view
type State = CaseView['progress'][number]['state']

// 단계 이름 → 상태. 적지 않은 단계는 PENDING이다.
function view(states: Record<string, State>, notices: Notice[] = []): CaseView {
  return {
    ...BASE,
    notices,
    running_jobs: [],
    progress: BASE.progress.map((p) => ({ step: p.step, state: states[p.step] ?? 'PENDING' })),
  }
}
const DONE_TO_REVIEW = { file_intake: 'DONE', coarse_search: 'DONE', candidate_review: 'DONE' } as const

function show(v: CaseView, files = ['a.mp4']) {
  return render(<FlowScreen view={v} files={files} situation="" startedAt={Date.now()} />)
}

it('한 단계가 실패하고 다른 단계가 진행 중이면 그 단계 문구로 알린다', () => {
  const { container } = show(view({ ...DONE_TO_REVIEW, plate_read: 'FAILED', overlay_time_read: 'RUNNING' }))
  expect(container.querySelector('.flow-partial')!.textContent).toBe(
    '번호판을 읽지 못했어요. 나머지 작업은 계속하고 있어요.',
  )
  expect(container.querySelector('.flow-now')!.textContent).toBe('화면 시각 판독')
})

it('여러 단계가 실패하면 한 줄로 요약하고, 어느 단계인지는 목록에 남긴다', () => {
  const { container } = show(
    view({ ...DONE_TO_REVIEW, plate_read: 'FAILED', overlay_time_read: 'FAILED', evidence_assembly: 'RUNNING' }),
  )
  expect(container.querySelectorAll('.flow-partial')).toHaveLength(1)
  expect(container.querySelector('.flow-partial')!.textContent).toBe(
    '일부 작업을 마치지 못했어요. 나머지 작업은 계속하고 있어요.',
  )
  expect(container.querySelectorAll('.timeline .tl-failed')).toHaveLength(2)
})

it('진행 중인 단계가 잠깐 없으면 「계속」이라고도 「중단」이라고도 하지 않는다', () => {
  const r = show(view({ ...DONE_TO_REVIEW, plate_read: 'RUNNING' }))
  r.rerender(
    <FlowScreen
      view={view({ ...DONE_TO_REVIEW, plate_read: 'FAILED' })}
      files={['a.mp4']}
      situation=""
      startedAt={Date.now()}
    />,
  )
  expect(r.container.querySelector('.flow-partial')).toBeNull()
  // 제목은 마지막 단계를 유지하고, 상태 줄은 그 단계의 실제 상태다
  expect(r.container.querySelector('.flow-now')!.textContent).toBe('번호판 판독')
  expect(r.container.querySelector('.flow-status')!.textContent).toBe('이 단계 실패')
})

it('blocking notice가 있으면 「나머지 작업은 계속」을 내지 않는다', () => {
  const blocking: Notice = {
    code: 'search.candidate_search_failed',
    severity: 'ERROR',
    blocking: true,
    message_key: 'notice.candidate_search_failed',
    actions: ['RETRY_SEARCH'],
  }
  const { container } = show(view({ ...DONE_TO_REVIEW, plate_read: 'FAILED', overlay_time_read: 'RUNNING' }, [blocking]))
  expect(container.querySelector('.flow-partial')).toBeNull()
})

it('끝난 단계를 제목으로 둘 때는 「이 단계 완료」로 전체 완료와 구분한다', () => {
  const r = show(view({ file_intake: 'RUNNING' }))
  r.rerender(<FlowScreen view={view({ file_intake: 'DONE' })} files={['a.mp4']} situation="" startedAt={Date.now()} />)
  expect(r.container.querySelector('.flow-status')!.textContent).toBe('이 단계 완료')
})

it('파일이 하나면 이름을, 여럿이면 접힌 「영상 N개」를 보이고 펼친 상태는 단계가 바뀌어도 남는다', () => {
  expect(show(view({ file_intake: 'RUNNING' })).container.querySelector('details')).toBeNull()
  cleanup()

  const files = ['a.mp4', 'b.mp4', 'c.mp4']
  const r = show(view({ file_intake: 'RUNNING' }), files)
  const details = r.container.querySelector('details')!
  expect(details.open).toBe(false)
  expect(r.container.querySelector('summary')!.textContent).toBe('영상 3개')
  fireEvent.click(r.container.querySelector('summary')!)
  details.open = true // jsdom은 summary 클릭으로 open을 바꾸지 않는다
  r.rerender(
    <FlowScreen view={view({ file_intake: 'DONE', coarse_search: 'RUNNING' })} files={files} situation="" startedAt={Date.now()} />,
  )
  expect(r.container.querySelector('details')).toBe(details)
  expect(details.open).toBe(true)
})
