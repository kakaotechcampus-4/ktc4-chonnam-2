// @vitest-environment jsdom
//
// 결과 화면 규칙: 일시 나누기, 신고용 영상 상태, 늦게 온 이전 후보 결과 거르기, 연결 안 된 notice 동작.

import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CaseView, Notice } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { ResultScreen } from '../screens/ResultScreen'
import { acceptView, reportVideoState, splitDateTime } from '../state/resultModel'

afterEach(cleanup)

const HAPPY = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.index === 2)!.view
const notice = (code: string): Notice => SNAPSHOTS.flatMap((s) => s.view.notices).find((n) => n.code === code)!

describe('발생 일시 나누기', () => {
  it('RFC3339 한 값을 일자·시간으로 나눈다', () => {
    expect(splitDateTime('2026-08-24T18:05:12+09:00')).toEqual({ date: '2026-08-24', time: '18:05:12' })
  })
  it('시간만 있으면 일자를 추측하지 않는다', () => {
    expect(splitDateTime('18:05')).toEqual({ date: null, time: '18:05' })
  })
  it('일자만, 없음, 읽을 수 없는 모양', () => {
    expect(splitDateTime('2026-08-24')).toEqual({ date: '2026-08-24', time: null })
    expect(splitDateTime(null)).toEqual({ date: null, time: null })
    expect(splitDateTime('어제 저녁')).toEqual({ date: null, time: null })
  })
})

describe('신고용 영상 상태', () => {
  it('영상 참조가 있어도 파일로 받을 경로가 없으면 「연결 미완료」다 — 다운로드 가능이 아니다', () => {
    expect(reportVideoState(HAPPY)).toBe('unlinked')
  })
  it('아직 없음 · 만드는 중 · 실패를 구분한다', () => {
    expect(reportVideoState({ ...HAPPY, package: { ...HAPPY.package!, artifact_ref: null } })).toBe('none')
    expect(
      reportVideoState({
        ...HAPPY,
        running_jobs: [{ job_id: 'j1', kind: 'REPORT_VIDEO_EXPORT', label_key: 'job.report_video_export', status: 'RUNNING' }],
      }),
    ).toBe('preparing')
    expect(
      reportVideoState({
        ...HAPPY,
        notices: [{ code: 'recording.report_video_export_failed', severity: 'ERROR', blocking: true, message_key: 'x', actions: [] }],
      }),
    ).toBe('failed')
  })
  it('결과 화면의 다운로드 버튼은 파일이 없으면 누를 수 없고 이유를 함께 읽힌다', () => {
    const r = render(<ResultScreen view={HAPPY} onCandidates={vi.fn()} onPlate={vi.fn()} onDetails={vi.fn()} onAction={vi.fn()} canRun={() => true} />)
    const btn = r.getByText('신고용 영상 다운로드').closest('button')!
    expect(btn.disabled).toBe(true)
    expect(document.getElementById(btn.getAttribute('aria-describedby')!)!.textContent).toContain('연결이 아직 준비되지 않았어요')
  })
})

describe('늦게 온 이전 후보 결과', () => {
  const pick = (id: string, rev: number): CaseView => ({
    ...HAPPY,
    case_rev: rev,
    candidates: [
      { ...HAPPY.candidates[0], candidate_id: 'A', selected: id === 'A' },
      { ...HAPPY.candidates[0], candidate_id: 'B', selected: id === 'B' },
    ],
  })
  it('B를 고른 뒤 도착한 A의 결과는 받지 않는다', () => {
    expect(acceptView(pick('A', 3), { caseRev: 3, candidateId: 'B' })).toBe(false)
    expect(acceptView(pick('B', 3), { caseRev: 3, candidateId: 'B' })).toBe(true)
  })
  it('더 낮은 case_rev는 stale이다(같은 후보로 되돌아가도)', () => {
    expect(acceptView(pick('A', 2), { caseRev: 4, candidateId: 'A' })).toBe(false)
  })
})

describe('notice 동작', () => {
  it('연결 안 된 동작은 눌러도 아무 일 없는 버튼으로 두지 않고, 사용 불가와 이유를 보인다', () => {
    const onAction = vi.fn()
    const view = { ...HAPPY, notices: [notice('evidence.time_needs_user_confirmation')] }
    const r = render(
      <ResultScreen view={view} onCandidates={vi.fn()} onPlate={vi.fn()} onDetails={vi.fn()} onAction={onAction} canRun={(a) => a !== 'EDIT_EVENT_TIME'} />,
    )
    const btn = r.getByText('시각 직접 입력').closest('button')!
    expect(btn.disabled).toBe(true)
    expect(r.getByText('아직 이 화면에서 할 수 없어요')).toBeTruthy()
    fireEvent.click(btn)
    expect(onAction).not.toHaveBeenCalled()
  })
})
