// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { ProgressPanel } from '../components/ProgressPanel'
import { SNAPSHOTS } from '../contracts/fixtures'
import type { CaseView } from '../contracts/caseView'

afterEach(cleanup)
const BASE = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.index === 1)!.view
const start = Date.parse('2026-10-30T01:00:00Z')
function view(phase: NonNullable<CaseView['scene_search']>['phase'] = 'SEARCHING'): CaseView {
  return { ...BASE, notices: [], progress: [{ step: 'coarse_search', state: 'RUNNING' }],
    scene_search: { job_id: 'search_1', phase, search_started_at: phase === 'PREPARING' ? null : new Date(start).toISOString() },
    running_jobs: [{ job_id: 'search_1', kind: 'COARSE_SEARCH', status: 'RUNNING', label_key: 'job.coarse_search' }] }
}
const panel = (v: CaseView, now = start) => <ProgressPanel view={v} jobs={v.running_jobs} sceneNow={now} />

it('120초 경계에만 지연 안내로 바뀌며 재조회·자동 재시도에도 누적 시간을 유지한다', () => {
  const v = view()
  const r = render(panel(v, start + 119_999))
  expect(r.getByRole('status').textContent).toBe('말씀하신 상황을 찾고 있어요')
  r.rerender(panel(v, start + 120_000))
  expect(r.getByRole('status').textContent).toBe('장면을 찾는 데 시간이 더 걸리고 있어요')
  r.rerender(panel({ ...v, running_jobs: v.running_jobs.map(j => ({ ...j, attempt: 2 })) }, start + 150_000))
  expect(r.getByRole('status').textContent).toBe('장면을 찾는 데 시간이 더 걸리고 있어요')
  expect(r.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('1')
  r.rerender(panel(view('ORGANIZING'), start + 150_000))
  expect(r.getByRole('status').textContent).toBe('찾은 장면을 정리하고 있어요')
  expect(r.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('2')
})

it('준비는 회전 표시, 탐색·정리는 고정된 원형 단계, 완료는 체크로 표시한다', () => {
  const r = render(panel(view('PREPARING'), start + 500_000))
  expect(r.getByRole('progressbar').getAttribute('aria-valuenow')).toBeNull()
  expect(r.getByRole('status').textContent).toBe('영상을 준비하고 있어요')
  expect(r.container.querySelector('.is-active.is-preparing')).not.toBeNull()
  const done = { ...view(), progress: [{ step: 'coarse_search', state: 'DONE' as const }] }
  r.rerender(panel(done))
  expect(r.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('3')
  expect(r.container.querySelector('.scene-search-ring')).toBeNull()
  expect(r.getByRole('status').textContent).toBe('장면 찾기를 마쳤어요')
})

it('이전 서버는 단계를 지어내지 않고 기존 진행 상태를 표시한다', () => {
  const r = render(panel({ ...view(), scene_search: undefined }, start + 500_000))
  expect(r.getByRole('status').textContent).toBe('장면을 찾고 있어요')
  expect(r.getByRole('progressbar').getAttribute('aria-valuenow')).toBeNull()
})

it('실패·시간 초과에는 모션이 없고 사용자가 다시 찾으면 이전 지연 안내를 지운다', () => {
  const v = view()
  const r = render(panel({ ...v, progress: [{ step: 'coarse_search', state: 'FAILED' }] }))
  expect(r.container.querySelector('.scene-search-ring, .scene-search-detail.is-running')).toBeNull()
  r.rerender(panel({ ...v, notices: [{ code: 'case.analysis_timed_out', blocking: false, severity: 'INFO', message_key: '', actions: ['RETRY_SEARCH'] }] }))
  expect(r.container.querySelector('.is-active, .scene-search-detail.is-running')).toBeNull()
  r.rerender(panel({ ...view('PREPARING'), scene_search: { job_id: 'new_job', phase: 'PREPARING', search_started_at: null },
    notices: [{ code: 'search.candidate_search_failed', blocking: true, severity: 'ERROR', message_key: '', actions: [] }] }, start + 500_000))
  expect(r.getByRole('status').textContent).toBe('영상을 준비하고 있어요')
  expect(r.container.querySelector('.is-active.is-preparing')).not.toBeNull()
})
