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
  it.each([
    ['2026-10-29T23:30:00Z', '2026-10-30', '08:30:00'],
    ['2026-12-31T23:30:00-05:00', '2027-01-01', '13:30:00'],
    ['2026-01-01T02:30:00+14:00', '2025-12-31', '21:30:00'],
  ])('다른 오프셋의 %s도 한국 시간으로 표시한다', (value, date, time) => {
    expect(splitDateTime(value)).toEqual({ date, time })
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
    // Tab으로 닿도록 disabled 대신 aria-disabled다(#509 #5)
    expect(btn.getAttribute('aria-disabled')).toBe('true')
    expect(btn.disabled).toBe(false)
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
    expect(button(r).getAttribute('aria-disabled')).toBe('true')
    expect(r.container.textContent).toContain('내려받는 연결이 아직 준비되지 않았어요')
  })

  it('받을 주소가 있으면 열려 있고, 누르면 그 주소를 받는다', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['mp4']) })
    vi.stubGlobal('fetch', fetchMock)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const names: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download)
    })
    const r = show('/cases/c1/assets/ref1')
    expect(button(r).getAttribute('aria-disabled')).toBe('false')
    fireEvent.click(button(r))
    fireEvent.click(button(r)) // 받는 동안은 막혀 있어 한 번만 받는다
    await vi.waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalled(), { timeout: 3000 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/cases/c1/assets/ref1')
    expect(names).toEqual([expect.stringMatching(/^daesingo_clip_\d{8}_\d{6}\.mp4$/)])
    expect(button(r).getAttribute('aria-disabled')).toBe('false')
  })

  it('받지 못하면 실패 안내를 보이고 버튼은 열어 둔다. 다시 누르면 안내를 지우고 다시 받는다(#563 리뷰)', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockRejectedValueOnce(new TypeError('network'))
      .mockResolvedValueOnce({ ok: true, blob: async () => new Blob(['mp4']) })
    vi.stubGlobal('fetch', fetchMock)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const r = show('/cases/c1/assets/ref1')
    const failed = '신고용 영상을 받지 못했어요. 다시 눌러 받아 주세요.'
    fireEvent.click(button(r))
    await r.findByText(failed)
    expect(button(r).getAttribute('aria-disabled')).toBe('false')
    // 연결이 끊긴 실패도 같다
    fireEvent.click(button(r))
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    await r.findByText(failed)
    fireEvent.click(button(r))
    await vi.waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalled(), { timeout: 3000 })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(r.queryByText(failed)).toBeNull()
  })
})

describe('번호판 이미지 다운로드', () => {
  const noop = vi.fn()
  const show = (plateImageHref?: string) =>
    render(<ResultScreen view={HAPPY} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} videoHref="/cases/c1/assets/v1" plateImageHref={plateImageHref} />)
  const query = (r: ReturnType<typeof show>) => r.queryByRole('button', { name: '번호판 이미지 다운로드' })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('받을 주소가 없으면(서버가 아직 안 내림 · 못 만듦) 버튼을 두지 않는다', () => {
    expect(query(show())).toBeNull()
  })

  it('주소가 있으면 누를 때 png로 받고, 실패하면 이유를 말하고 다시 받을 수 있게 둔다. 영상 버튼은 그대로다', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, blob: async () => new Blob(['png']) }).mockResolvedValueOnce({ ok: false })
    vi.stubGlobal('fetch', fetchMock)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const names: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download)
    })
    const r = show('/cases/c1/assets/p1')
    const btn = query(r)!
    expect(btn.getAttribute('aria-disabled')).toBe('false')
    fireEvent.click(btn)
    await vi.waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalled(), { timeout: 3000 })
    expect(fetchMock).toHaveBeenCalledWith('/cases/c1/assets/p1')
    expect(names).toEqual([expect.stringMatching(/^daesingo_plate_\d{8}_\d{6}\.png$/)])
    fireEvent.click(query(r)!)
    await r.findByText('번호판 이미지를 받지 못했어요. 다시 눌러 받아 주세요.')
    expect(query(r)!.getAttribute('aria-disabled')).toBe('false')
    expect(r.getByRole('button', { name: '신고용 영상 다운로드' }).getAttribute('aria-disabled')).toBe('false')
  })
})

describe('번호판 장면 다운로드 (#600)', () => {
  const noop = vi.fn()
  const frameSrc = (ref: string) => `/cases/c1/frames/${ref}`
  const show = (view = HAPPY, demo = false) =>
    render(<ResultScreen view={view} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} videoHref="/cases/c1/assets/v1" frameSrc={demo ? undefined : frameSrc} />)
  const query = (r: ReturnType<typeof show>) => r.queryByRole('button', { name: '번호판 장면 다운로드' })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('번호판을 읽은 장면(plate_preview_ref)이 없거나 시연(frameSrc 없음)이면 버튼을 두지 않는다', () => {
    expect(query(show({ ...HAPPY, evidence: { ...HAPPY.evidence!, plate_preview_ref: null } }))).toBeNull()
    cleanup()
    expect(query(show(HAPPY, true))).toBeNull()
  })

  it('번호판 확인 화면과 같은 frame 주소를 png로 받고, 실패하면 이유를 말하고 다시 받을 수 있게 둔다. 번호판 이미지 버튼과 따로다', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, blob: async () => new Blob(['png']) }).mockResolvedValueOnce({ ok: false })
    vi.stubGlobal('fetch', fetchMock)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const names: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download)
    })
    const r = show()
    expect(r.queryByRole('button', { name: '번호판 이미지 다운로드' })).toBeNull()
    fireEvent.click(query(r)!)
    await vi.waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalled(), { timeout: 3000 })
    expect(fetchMock).toHaveBeenCalledWith(`/cases/c1/frames/${HAPPY.evidence!.plate_preview_ref}`)
    expect(names).toEqual([expect.stringMatching(/^daesingo_plate_scene_\d{8}_\d{6}\.png$/)])
    fireEvent.click(query(r)!)
    await r.findByText('번호판 장면을 받지 못했어요. 다시 눌러 받아 주세요.')
    expect(query(r)!.getAttribute('aria-disabled')).toBe('false')
  })
})

describe('동영상 칸 — 후보 미리보기를 둘 수 없을 때 (#636)', () => {
  const noop = vi.fn()
  const frameSrc = (ref: string) => `/frames/${ref}`
  const withThumb = (thumb: string | null): CaseView => ({
    ...HAPPY,
    candidates: HAPPY.candidates.map((c) => (c.selected ? { ...c, thumb_ref: thumb } : c)),
  })
  // videoSrc가 없으면 후보 미리보기(CandidateVideo)를 두지 않는다
  const show = (view: CaseView) =>
    render(<ResultScreen view={view} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} videoHref="/cases/c1/assets/v1" frameSrc={frameSrc} />)
  const preview = (r: ReturnType<typeof show>) => r.container.querySelector('.res-preview')!

  it('고른 후보의 썸네일을, 없으면 근거 장면을 보이고, 이미지를 못 불러오면 지금의 안내로 돌아간다', () => {
    const r = show(withThumb('fr_thumb'))
    expect(preview(r).querySelector('img')?.getAttribute('src')).toBe('/frames/fr_thumb')
    expect(preview(r).querySelector('img')?.getAttribute('alt')).toBe('고른 후보 장면')
    cleanup()
    const r2 = show(withThumb(null))
    expect(preview(r2).querySelector('img')?.getAttribute('src')).toBe(`/frames/${HAPPY.evidence!.preview_ref}`)
    fireEvent.error(preview(r2).querySelector('img')!)
    expect(preview(r2).querySelector('img')).toBeNull()
    expect(preview(r2).querySelector('svg')).not.toBeNull()
  })

  it('장면 이미지가 하나도 없으면 지금처럼 아이콘과 안내만 둔다', () => {
    const r = show({ ...withThumb(null), evidence: { ...HAPPY.evidence!, preview_ref: null } })
    expect(preview(r).querySelector('img')).toBeNull()
    expect(preview(r).querySelector('svg')).not.toBeNull()
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

  it('번호판 확대 칸은 신고자료의 번호판 이미지(다운로드와 같은 plate_image_ref)를 보인다. 주소가 없으면 자리 표시만 둔다 (#446)', () => {
    const withImage = render(<PlateCheck view={HAPPY} onBack={vi.fn()} plateImageSrc="/assets/plate.png" />)
    const crop = withImage.container.querySelector('.plate-crop')
    expect(crop?.querySelector('img')?.getAttribute('src')).toBe('/assets/plate.png')
    expect(crop?.querySelector('img')?.getAttribute('alt')).toBe('번호판 확대')
    expect(withImage.container.textContent).not.toContain('번호판 이미지가 없어요')
    withImage.unmount()
    const without = render(<PlateCheck view={{ ...HAPPY, running_jobs: [] }} onBack={vi.fn()} />)
    expect(without.container.querySelector('.plate-crop img')).toBeNull()
    expect(without.container.textContent).toContain('번호판 이미지가 없어요')
  })

  it('이미지가 없을 때 도는 job이 있으면 「준비 중」, 없으면 「없어요」 — 오지 않을 이미지를 기다리게 하지 않는다', () => {
    const noImage = { ...HAPPY, evidence: { ...HAPPY.evidence!, plate_preview_ref: null } }
    const done = render(<PlateCheck view={{ ...noImage, running_jobs: [] }} onBack={vi.fn()} />)
    expect(done.container.textContent).toContain('장면 이미지가 없어요')
    expect(done.container.textContent).toContain('번호판 이미지가 없어요')
    expect(done.container.textContent).not.toContain('준비 중')
    done.unmount()
    const job = { job_id: 'j1', kind: 'PLATE_READ', label_key: 'job.plate_read', status: 'RUNNING' as const }
    const running = render(<PlateCheck view={{ ...noImage, running_jobs: [job] }} onBack={vi.fn()} />)
    expect(running.container.textContent).toContain('장면 이미지 준비 중')
  })

  // #487에 올린 통과 · 차단 사례
  it('번호판 형식이 어긋나도 저장은 막지 않고 경고만 한다(core-user-flow §12). 빈 값만 막고, 입력한 값은 공백까지 그대로 보낸다', () => {
    const onEdit = vi.fn()
    const { container, getByText } = render(<PlateCheck view={HAPPY} onBack={vi.fn()} onEdit={onEdit} startEditing />)
    const input = container.querySelector('.plate-input') as HTMLInputElement
    const save = getByText('저장') as HTMLButtonElement
    fireEvent.change(input, { target: { value: '  ' } })
    expect(save.disabled).toBe(true)
    fireEvent.submit(input.form!)
    expect(onEdit).not.toHaveBeenCalled()
    fireEvent.change(input, { target: { value: '12가34?6' } })
    expect(save.disabled).toBe(false)
    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(container.textContent).toContain('번호판 형식을 확인해 주세요')
    fireEvent.submit(input.form!)
    expect(onEdit).toHaveBeenLastCalledWith('12가34?6')
    // 저장하면 입력칸이 닫히므로 새로 연다
    const again = render(<PlateCheck view={HAPPY} onBack={vi.fn()} onEdit={onEdit} startEditing />)
    const input2 = again.container.querySelector('.plate-input') as HTMLInputElement
    for (const good of ['123가4567', '서울12가3456', '12가 3456']) {
      fireEvent.change(input2, { target: { value: good } })
      expect(input2.getAttribute('aria-invalid')).toBe('false')
    }
    fireEvent.submit(input2.form!)
    expect(onEdit).toHaveBeenLastCalledWith('12가 3456')
  })
})

describe('#597 — 응답 없이 초안 · 번호판 장면 · 최종 검토 기록', () => {
  afterEach(cleanup)
  const noop = vi.fn()
  const job = { job_id: 'j', kind: 'REPORT_VIDEO_EXPORT', label_key: 'job.report_video_export', status: 'RUNNING' } as const
  // 묶음 전, 영상을 만드는 중 — 상황 응답 대기 notice가 없다
  const draftView: CaseView = {
    ...HAPPY,
    stage: 'EVIDENCE_REVIEW',
    package: null,
    notices: [],
    running_jobs: [job],
    report_draft: { title: '초안 제목', description: '초안 신고 내용' },
    evidence: { ...HAPPY.evidence!, plate_preview_ref: 'frame_plate' },
  }

  it('묶음 전에는 report_draft를 보이고, 영상을 만드는 중이면 「준비하고 있어요」다', () => {
    const r = render(<ResultScreen view={draftView} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} />)
    expect(r.getByRole('heading', { level: 1 }).textContent).toBe('신고자료를 준비하고 있어요.')
    expect(r.getByText('초안 제목')).toBeTruthy()
    expect(r.getByText('초안 신고 내용')).toBeTruthy()
    expect(r.queryByRole('button', { name: '맞아요' })).toBeNull()
  })

  it('번호판을 읽은 장면을 썸네일로 두고, 누르면 번호판 확인 화면으로 간다 — 장면 주소가 없으면(시연) 두지 않는다', () => {
    const onPlate = vi.fn()
    const r = render(
      <ResultScreen view={draftView} onCandidates={noop} onPlate={onPlate} onDetails={noop} onAction={noop} canRun={() => true} frameSrc={(ref) => `/f/${ref}`} />,
    )
    const thumb = r.getByAltText('번호판을 읽은 장면 — 눌러서 크게 보기')
    expect(thumb.getAttribute('src')).toBe('/f/frame_plate')
    fireEvent.click(thumb)
    expect(onPlate).toHaveBeenCalledTimes(1)
    // 안내는 하나만 — 「번호가 틀렸다면…」 대신 확인 문구
    expect(r.getByText('신고할 차량의 번호판인지 확인해 주세요')).toBeTruthy()
    expect(r.queryByText('번호가 틀렸다면 여기서 고칠 수 있어요')).toBeNull()
    cleanup()
    const demo = render(<ResultScreen view={draftView} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} />)
    expect(demo.queryByAltText('번호판을 읽은 장면 — 눌러서 크게 보기')).toBeNull()
    expect(demo.getByText('번호가 틀렸다면 여기서 고칠 수 있어요')).toBeTruthy()
  })

  const withType = (code: string | null, confirmation: 'NOT_ASKED' | 'USER_UNSURE'): CaseView => ({
    ...draftView,
    evidence: { ...draftView.evidence!, case_type_display: { ...draftView.evidence!.case_type_display, code } },
    candidates: draftView.candidates.map((c) => (c.selected ? { ...c, situation_confirmation: confirmation } : c)),
  })

  it('「다른 상황이었어요」는 지금 유형을 뺀 상황 설명 중에서 골라 CORRECTED로 보낸다', () => {
    const onCorrect = vi.fn()
    const r = render(<ResultScreen view={withType('SIGNAL', 'NOT_ASKED')} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} onCorrect={onCorrect} />)
    fireEvent.click(r.getByRole('button', { name: /다른 상황이었어요/ }))
    // 고르기 전에 무엇이 바뀌는지 밝힌다
    expect(r.getByText('고르시면 AI가 판별한 유형 대신 고른 상황으로 신고자료를 다시 준비해요.')).toBeTruthy()
    expect(r.queryByLabelText('신호를 지키지 않고 지나갔어요')).toBeNull()
    expect(r.getByRole('button', { name: '이 상황으로 고치기' }).hasAttribute('disabled')).toBe(true)
    fireEvent.click(r.getByLabelText('중앙선을 넘었어요'))
    fireEvent.click(r.getByRole('button', { name: '이 상황으로 고치기' }))
    expect(onCorrect).toHaveBeenCalledWith('CENTER_LINE_CROSSING')
    // 폼이 닫히면 초점은 「다른 상황이었어요」로 돌아오고, 보낸 것을 알린다
    expect(document.activeElement).toBe(r.getByRole('button', { name: /다른 상황이었어요/ }))
    expect(r.getByText('고친 상황으로 다시 준비하고 있어요.').getAttribute('role')).toBe('status')
  })


  it('「잘 모르겠어요」로 남긴 판별 유형은 다시 확인하거나 고칠 수 있다 — 유형이 없으면(UNCERTAIN) 고치기를 두지 않는다', () => {
    const onRespond = vi.fn()
    const props = { onCandidates: noop, onPlate: noop, onDetails: noop, onAction: noop, canRun: () => true, onCorrect: noop, onRespond }
    const r = render(<ResultScreen view={withType('SIGNAL', 'USER_UNSURE')} {...props} />)
    fireEvent.click(r.getByRole('button', { name: '이 상황이 맞아요' }))
    expect(onRespond).toHaveBeenCalledWith('CONFIRMED')
    cleanup()
    const uncertain = render(<ResultScreen view={withType(null, 'USER_UNSURE')} {...props} />)
    expect(uncertain.queryByRole('button', { name: /다른 상황이었어요/ })).toBeNull()
    expect(uncertain.queryByRole('button', { name: '이 상황이 맞아요' })).toBeNull()
  })

  it('안전신문고로 이동하면 최종 검토를 한 번만 기록한다', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const onReviewed = vi.fn()
    const ready = { ...HAPPY, user_reviewed: false, notices: HAPPY.notices.filter((n) => !n.blocking) }
    const r = render(<ResultScreen view={ready} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} onReviewed={onReviewed} />)
    fireEvent.click(r.getByRole('button', { name: /안전신문고로 이동/ }))
    fireEvent.click(r.getByRole('button', { name: /안전신문고로 이동/ })) // 새 view가 오기 전 두 번째 클릭
    expect(open).toHaveBeenCalled()
    expect(onReviewed).toHaveBeenCalledTimes(1)
    // 다른 후보를 골라 기록이 바뀌면 그 기록의 검토는 다시 보낸다
    const other = { ...ready, evidence: { ...ready.evidence!, record_id: 'ev_other' } }
    r.rerender(<ResultScreen view={other} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} onReviewed={onReviewed} />)
    fireEvent.click(r.getByRole('button', { name: /안전신문고로 이동/ }))
    expect(onReviewed).toHaveBeenCalledTimes(2)
    onReviewed.mockClear()
    cleanup()
    const again = render(
      <ResultScreen view={{ ...ready, user_reviewed: true }} onCandidates={noop} onPlate={noop} onDetails={noop} onAction={noop} canRun={() => true} onReviewed={onReviewed} />,
    )
    fireEvent.click(again.getByRole('button', { name: /안전신문고로 이동/ }))
    expect(onReviewed).not.toHaveBeenCalled()
    open.mockRestore()
  })
})
