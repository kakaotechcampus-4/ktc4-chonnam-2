// @vitest-environment jsdom
//
// 결과 화면 규칙: 일시 나누기, 신고용 영상 상태, 늦게 온 이전 후보 결과 거르기, 연결 안 된 notice 동작.

import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CaseView, Notice } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { FrameSlot } from '../components/FrameSlot'
import { ResultScreen } from '../screens/ResultScreen'
import { PlateCheck } from '../screens/SubScreens'
import { acceptView, reportVideoState, splitDateTime } from '../state/resultModel'

afterEach(cleanup)

// 순번이 아니라 모양으로 고른다 — fixture에 스냅샷이 끼어들면 순번이 밀린다(#177, DemoFlow와 같은 방식)
const HAPPY = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.view.stage === 'READY' && s.view.package !== null)!.view
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
  it('영상 참조가 있으면 받을 수 있다', () => {
    expect(reportVideoState(HAPPY)).toBe('ready')
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
  it('묶음 전이라도 영상 check가 PASS면 「없음」이 아니라 「준비됨(받기 전)」이다', () => {
    const before = { ...HAPPY, package: null }
    const check = { code: 'package.asset.report_video.exists', outcome: 'PASS' }
    expect(reportVideoState({ ...before, requirements_package: { readiness: 'UNKNOWN', checks: [check] } } as CaseView)).toBe('held')
    expect(reportVideoState({ ...before, requirements_package: { readiness: 'UNKNOWN', checks: [{ ...check, outcome: 'UNKNOWN' }] } } as CaseView)).toBe('none')
    expect(reportVideoState({ ...before, requirements_package: null })).toBe('none')
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

describe('신고용 영상 다운로드', () => {
  const noop = vi.fn()
  const show = (videoHref?: string) =>
    render(<ResultScreen view={HAPPY} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} videoHref={videoHref} />)
  const button = (r: ReturnType<typeof show>) => r.getByRole('button', { name: '신고용 영상 다운로드' }) as HTMLButtonElement
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('받을 주소가 없으면(시연) 막아 두고 이유를 말한다', () => {
    const r = show()
    expect(button(r).disabled).toBe(true)
    expect(r.container.textContent).toContain('내려받는 연결이 아직 준비되지 않았어요')
  })

  it('받을 주소가 있으면 열려 있고, 누르면 그 주소를 받는다', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['mp4']) })
    vi.stubGlobal('fetch', fetchMock)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const r = show('/cases/c1/assets/ref1')
    expect(button(r).disabled).toBe(false)
    fireEvent.click(button(r))
    fireEvent.click(button(r)) // 받는 동안은 막혀 있어 한 번만 받는다
    await vi.waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalled(), { timeout: 3000 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/cases/c1/assets/ref1')
    expect(button(r).disabled).toBe(false)
  })

  it('서버가 못 준다고 하면 실패 안내로 바뀌고 버튼이 다시 막힌다. 다른 주소(다른 후보)면 다시 열린다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    const r = show('/cases/c1/assets/ref1')
    fireEvent.click(button(r))
    await r.findByText('신고용 영상을 받지 못했어요')
    expect(button(r).disabled).toBe(true)
    r.rerender(<ResultScreen view={HAPPY} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} videoHref="/cases/c1/assets/ref2" />)
    expect(button(r).disabled).toBe(false)
  })
})

describe('프레임 이미지', () => {
  it('ref가 없으면 자리 표시를 두고, 있으면 이미지를 그리고, 받지 못하면 자리 표시로 돌아간다', () => {
    const r = render(<FrameSlot className="f" src={null} alt="장면">자리</FrameSlot>)
    expect(r.container.textContent).toBe('자리')
    r.rerender(<FrameSlot className="f" src="/frames/a" alt="장면">자리</FrameSlot>)
    const img = r.container.querySelector('img')!
    expect(img.getAttribute('src')).toBe('/frames/a')
    fireEvent.error(img)
    expect(r.container.querySelector('img')).toBeNull()
    expect(r.container.textContent).toBe('자리')
    // 자리 표시가 없으면 칸 자체를 그리지 않는다(근거 장면 — 있을 때만 보인다)
    r.rerender(<FrameSlot className="f" src={null} alt="장면" />)
    expect(r.container.querySelector('.f')).toBeNull()
  })

  it('번호판 확인 화면의 장면은 대표 썸네일(preview_ref)이 아니라 번호판을 읽은 frame(plate_preview_ref)이다. frameSrc가 없으면(시연) 그리지 않는다', () => {
    expect(HAPPY.evidence?.plate_preview_ref).toBeTruthy()
    expect(HAPPY.evidence?.plate_preview_ref).not.toBe(HAPPY.evidence?.preview_ref)
    const frameSrc = (ref: string) => `/frames/${ref}`
    const withApi = render(<PlateCheck view={HAPPY} onBack={vi.fn()} frameSrc={frameSrc} />)
    expect([...withApi.container.querySelectorAll('img')].map((i) => i.getAttribute('src'))).toEqual([
      `/frames/${HAPPY.evidence!.plate_preview_ref}`,
    ])
    withApi.unmount()
    const demo = render(<PlateCheck view={HAPPY} onBack={vi.fn()} />)
    expect(demo.container.querySelector('img')).toBeNull()
  })

  // #487에 올린 통과 · 차단 사례
  it('번호판 입력은 형식이 맞을 때만 저장되고, 안쪽 공백은 지워서 보낸다', () => {
    const onEdit = vi.fn()
    const { container, getByText } = render(<PlateCheck view={HAPPY} onBack={vi.fn()} onEdit={onEdit} startEditing />)
    const input = container.querySelector('.plate-input') as HTMLInputElement
    const save = getByText('저장') as HTMLButtonElement
    for (const bad of ['12가34?6', 'abc', '12']) {
      fireEvent.change(input, { target: { value: bad } })
      expect(save.disabled).toBe(true)
      expect(input.getAttribute('aria-invalid')).toBe('true')
      expect(container.textContent).toContain('번호판 형식을 확인해 주세요')
      fireEvent.submit(input.form!)
    }
    expect(onEdit).not.toHaveBeenCalled()
    for (const good of ['123가4567', '서울12가3456', '12가 3456']) {
      fireEvent.change(input, { target: { value: good } })
      expect(save.disabled).toBe(false)
      expect(input.getAttribute('aria-invalid')).toBe('false')
    }
    fireEvent.submit(input.form!)
    expect(onEdit).toHaveBeenCalledWith('12가3456')
  })
})
