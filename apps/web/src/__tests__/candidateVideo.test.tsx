// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { createApi } from '../api/client'
import type { Candidate, CaseView } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { CandidatesScreen } from '../screens/CandidatesScreen'
import { FailedScreen } from '../screens/FailedScreen'
import { NotObservedScreen } from '../screens/NotObservedScreen'
import { ResultScreen } from '../screens/ResultScreen'
import { DetailsCheck, PlateCheck } from '../screens/SubScreens'
import { selectScreen } from '../state/selectScreen'

const base = SNAPSHOTS.find((s) => s.view.evidence !== null)!.view
const candidateBase = base.candidates[0]
const candidate = (rank: number, status: 'NOT_REQUESTED' | 'PREPARING' | 'READY' | 'FAILED' | 'UNAVAILABLE' = 'NOT_REQUESTED'): Candidate => ({
  ...candidateBase, candidate_id: `c${rank}`, rank, selected: rank === 1,
  video_preview: { status, clip_ref: status === 'READY' ? `clip${rank}` : null },
})
const view = (candidates: Candidate[]): CaseView => ({ ...base, stage: 'EVIDENCE_REVIEW', candidates, running_jobs: [] })
const videoSrc = (ref: string) => `/video/${ref}`
afterEach(cleanup)

it.each([0, 1, 2, 3, 5])('renders %i candidates without padding, only eligible videos have request buttons', (count) => {
  const candidates = Array.from({ length: count }, (_, i) => candidate(i + 1, i < 3 ? 'NOT_REQUESTED' : 'UNAVAILABLE'))
  const onPreview = vi.fn()
  const screen = render(<CandidatesScreen view={view(candidates)} onPreview={onPreview} videoSrc={videoSrc} />)
  expect(screen.container.querySelectorAll('.cand')).toHaveLength(count)
  expect(screen.queryAllByRole('button', { name: /영상 보기/ })).toHaveLength(Math.min(count, 3))
  if (count === 0) expect(screen.getByText('찾은 후보가 없어요.')).toBeTruthy()
})

it('requesting a preview does not select a candidate', () => {
  const onPreview = vi.fn(), onSelect = vi.fn()
  const screen = render(<CandidatesScreen view={view([candidate(1), candidate(2)])} onPreview={onPreview} onSelect={onSelect} videoSrc={videoSrc} />)
  fireEvent.click(screen.getAllByRole('button', { name: /영상 보기/ })[1])
  expect(onPreview).toHaveBeenCalledWith('c2')
  expect(onSelect).not.toHaveBeenCalled()
})

it('preparing preview keeps candidate selection enabled and shows local status', () => {
  const screen = render(<CandidatesScreen view={view([candidate(1), candidate(2, 'PREPARING')])} onPreview={vi.fn()} onSelect={vi.fn()} videoSrc={videoSrc} />)
  expect(screen.getByText('영상 준비 중')).toBeTruthy()
  expect(screen.getByRole('button', { name: '이 장면으로 다시 준비' }).hasAttribute('disabled')).toBe(false)
})

it('ready clips use native inline controls; playing another pauses the previous one', () => {
  const screen = render(<CandidatesScreen view={view([candidate(1, 'READY'), candidate(2, 'READY')])} videoSrc={videoSrc} />)
  const videos = screen.container.querySelectorAll('video')
  expect(videos).toHaveLength(2)
  expect(videos[0].getAttribute('src')).toBe('/video/clip1')
  expect(videos[0].controls && videos[0].playsInline).toBe(true)
  expect(videos[0].autoplay).toBe(false)
  Object.defineProperty(videos[0], 'paused', { value: false })
  const pause = vi.spyOn(videos[0], 'pause').mockImplementation(() => {})
  fireEvent.play(videos[1])
  expect(pause).toHaveBeenCalledOnce()
})

it('generation or source changes remove old video, and browser error is local', () => {
  const screen = render(<CandidatesScreen view={view([candidate(1, 'READY'), candidate(2, 'READY')])} videoSrc={videoSrc} />)
  fireEvent.error(screen.container.querySelector('video')!)
  expect(screen.getByText('영상을 재생할 수 없어요.')).toBeTruthy()
  expect(screen.container.querySelectorAll('video')).toHaveLength(1)
  screen.rerender(<CandidatesScreen view={view([candidate(1), candidate(2)])} videoSrc={videoSrc} onPreview={vi.fn()} />)
  expect(screen.container.querySelectorAll('video')).toHaveLength(0)
})

it('preview jobs keep report and failure surfaces visible', () => {
  const current = view([candidate(1)])
  const job: CaseView['running_jobs'][number] = { job_id: 'preview', kind: 'CANDIDATE_VIDEO_PREVIEW', label_key: 'job.candidate_video_preview', status: 'RUNNING' }
  expect(selectScreen({ ...current, running_jobs: [job] }).kind).toBe('EVIDENCE')
  expect(selectScreen({ ...current, evidence: null, running_jobs: [job], notices: [{ code: 'recording.incident_clip_build_failed', severity: 'WARN', blocking: false, message_key: 'notice.incident_clip_build_failed', actions: [] }] }).kind).toBe('SEARCH_FAILED')
})

it('candidate video URLs encode case and clip identifiers', () => {
  expect(createApi().candidateVideoUrl('case/a', 'clip/b')).toBe('/cases/case%2Fa/candidate-videos/clip%2Fb')
})

it('uses the selected evidence frame as the video poster when its thumbnail is absent', () => {
  const current = view([{ ...candidate(1), thumb_ref: null }])
  const screen = render(<CandidatesScreen view={current} frameSrc={(ref) => `/frame/${ref}`} onPreview={vi.fn()} />)
  expect(screen.getByRole('img', { name: '1번 후보 장면' }).getAttribute('src')).toBe(`/frame/${current.evidence?.preview_ref}`)
  expect(screen.getByRole('button', { name: '1번 후보 영상 보기' })).toBeTruthy()
})

it.each([
  ['not observed', NotObservedScreen],
  ['failed', FailedScreen],
])('%s screen hides the playback area when every preview is unavailable', (_, Screen) => {
  const only = (status: 'UNAVAILABLE' | 'NOT_REQUESTED') => ({ ...base, candidates: [candidate(1, status)], running_jobs: [] })
  const hidden = render(<Screen view={only('UNAVAILABLE')} videoSrc={videoSrc} onPreview={vi.fn()} onAction={vi.fn()} canRun={() => true} />)
  expect(hidden.container.querySelector('.cand')).toBeNull()
  cleanup()
  const shown = render(<Screen view={only('NOT_REQUESTED')} videoSrc={videoSrc} onPreview={vi.fn()} onAction={vi.fn()} canRun={() => true} />)
  expect(shown.container.querySelector('.cand')).not.toBeNull()
})

it('keeps playback available when its poster cannot be loaded', () => {
  const screen = render(<CandidatesScreen view={view([{ ...candidate(1), thumb_ref: 'broken' }])}
    frameSrc={(ref) => `/frame/${ref}`} onPreview={vi.fn()} />)
  fireEvent.error(screen.getByRole('img', { name: '1번 후보 장면' }))
  expect(screen.queryByRole('img', { name: '1번 후보 장면' })).toBeNull()
  expect(screen.getByRole('button', { name: '1번 후보 영상 보기' })).toBeTruthy()
})

// #554 web review (kim1034 · uminshin)
const clipJob = { job_id: 'clip', kind: 'INCIDENT_CLIP_BUILD', label_key: 'job.incident_clip_build', status: 'RUNNING' } as const
const previewJob = { job_id: 'preview', kind: 'CANDIDATE_VIDEO_PREVIEW', label_key: 'job.candidate_video_preview', status: 'RUNNING' } as const

it('keeps the thumbnail placeholder text when a preview card has no poster yet', () => {
  const noThumb = { ...candidate(2), thumb_ref: null }
  const pending = render(<CandidatesScreen view={{ ...view([candidate(1), noThumb]), running_jobs: [clipJob] }}
    frameSrc={(ref) => `/frame/${ref}`} onPreview={vi.fn()} />)
  expect(pending.getByText('미리보기 준비 중')).toBeTruthy()
  expect(pending.getByRole('button', { name: '2번 후보 영상 보기' })).toBeTruthy()
  cleanup()
  const done = render(<CandidatesScreen view={view([candidate(1), noThumb])} frameSrc={(ref) => `/frame/${ref}`} onPreview={vi.fn()} />)
  expect(done.getByText('미리보기가 없어요')).toBeTruthy()
})

const awaiting = (status: 'UNAVAILABLE' | 'NOT_REQUESTED'): CaseView => ({
  ...base, running_jobs: [],
  candidates: [{ ...candidate(1, status), situation_confirmation: 'NOT_ASKED' }],
  notices: [...base.notices, { code: 'case.situation_response_pending', severity: 'INFO', blocking: false,
    message_key: 'notice.situation_response_pending', actions: [] }],
})
const result = (v: CaseView) => render(<ResultScreen view={v} onCandidates={vi.fn()} onPlate={vi.fn()} onDetails={vi.fn()}
  onAction={vi.fn()} canRun={() => true} onRespond={vi.fn()} videoSrc={videoSrc} onPreview={vi.fn()} frameSrc={(ref) => `/frame/${ref}`} />)

it('situation card keeps the evidence image when the preview is unavailable', () => {
  const unavailable = result(awaiting('UNAVAILABLE'))
  expect(unavailable.queryByText('이 후보의 미리보기를 볼 수 없어요.')).toBeNull()
  expect(unavailable.getByRole('img', { name: '근거 장면' })).toBeTruthy()
  cleanup()
  expect(result(awaiting('NOT_REQUESTED')).getByRole('button', { name: '1번 후보 영상 보기' })).toBeTruthy()
})

it('plate check does not wait for images while only a preview job runs', () => {
  const plate = (jobs: CaseView['running_jobs']) =>
    render(<PlateCheck view={{ ...base, running_jobs: jobs, evidence: base.evidence && { ...base.evidence, preview_ref: null, plate_preview_ref: null } }} onBack={vi.fn()} />)
  expect(plate([previewJob]).getByText('장면 이미지가 없어요')).toBeTruthy()
  cleanup()
  expect(plate([clipJob]).getByText('장면 이미지 준비 중')).toBeTruthy()
})

it('labels the result video slot as a candidate preview, not the report video', () => {
  const happy = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.view.stage === 'READY' && s.view.package !== null)!.view
  const r = result({ ...happy, candidates: happy.candidates.map((c) => c.selected
    ? { ...c, video_preview: { status: 'READY' as const, clip_ref: 'clip1' } } : c) })
  expect(r.container.querySelector('video')?.getAttribute('src')).toBe('/video/clip1')
  expect(r.getByText('후보 미리보기')).toBeTruthy()
})

it('keeps focus and announces when a requested preview becomes ready', () => {
  const at = (s: 'NOT_REQUESTED' | 'PREPARING' | 'READY') => <CandidatesScreen view={view([candidate(1, s)])} onPreview={vi.fn()} videoSrc={videoSrc} />
  const screen = render(at('NOT_REQUESTED'))
  const button = screen.getByRole('button', { name: /영상 보기/ })
  button.focus()
  screen.rerender(at('PREPARING'))
  expect(document.activeElement?.textContent).toBe('영상 준비 중')
  const live = screen.getByRole('status')
  expect(live.textContent).toBe('')
  screen.rerender(at('READY'))
  expect(screen.getByRole('status')).toBe(live) // 새 알림 칸이면 스크린 리더가 읽지 않는다
  expect(document.activeElement?.tagName).toBe('VIDEO')
  expect(screen.getByRole('status').textContent).toBe('영상이 준비됐어요')
})

it('does not pull focus from elsewhere when a preview becomes ready', () => {
  const at = (s: 'PREPARING' | 'READY') => <><button type="button">다른 곳</button><CandidatesScreen view={view([candidate(1, s)])} onPreview={vi.fn()} videoSrc={videoSrc} /></>
  const screen = render(at('PREPARING'))
  screen.getByRole('button', { name: '다른 곳' }).focus()
  screen.rerender(at('READY'))
  expect(document.activeElement?.textContent).toBe('다른 곳')
})

it('moves focus to the retry button and announces when preparing fails', () => {
  const at = (s: 'NOT_REQUESTED' | 'PREPARING' | 'FAILED') => <CandidatesScreen view={view([candidate(1, s)])} onPreview={vi.fn()} videoSrc={videoSrc} />
  const screen = render(at('NOT_REQUESTED'))
  screen.getByRole('button', { name: /영상 보기/ }).focus()
  screen.rerender(at('PREPARING'))
  expect(document.activeElement?.textContent).toBe('영상 준비 중')
  screen.rerender(at('FAILED'))
  const retry = document.activeElement!
  expect(retry.getAttribute('aria-label')).toBe('1번 후보 영상 다시 준비')
  expect(document.getElementById(retry.getAttribute('aria-describedby')!)?.textContent).toBe('영상을 준비하지 못했어요.')
  expect(screen.getByRole('status').textContent).toBe('')
})

it('focuses the player again after reloading a clip the browser could not play', () => {
  const screen = render(<CandidatesScreen view={view([candidate(1, 'READY')])} videoSrc={videoSrc} />)
  fireEvent.error(screen.container.querySelector('video')!)
  expect(document.activeElement?.textContent).toBe('다시 불러오기')
  fireEvent.click(screen.getByRole('button', { name: '다시 불러오기' }))
  expect(document.activeElement?.tagName).toBe('VIDEO')
})

// 「어떻게 정했는지」의 기준 후보 카드도 다른 후보 화면과 같은 장면 · 영상 미리보기를 보인다
it('details page shows the basis candidate scene and video preview', () => {
  const frameSrc = (ref: string) => `/frame/${ref}`
  const basis = { ...candidate(1, 'READY'), thumb_ref: 'thumb1' }
  const ready = render(<DetailsCheck view={view([basis, candidate(2, 'READY')])} onBack={vi.fn()} videoSrc={videoSrc} frameSrc={frameSrc} />)
  const videos = ready.container.querySelectorAll('.details-scene video')
  expect(videos).toHaveLength(1)
  expect(videos[0].getAttribute('src')).toBe('/video/clip1')
  expect(videos[0].getAttribute('poster')).toBe('/frame/thumb1')
  cleanup()

  const onPreview = vi.fn()
  const idle = render(<DetailsCheck view={view([candidate(1)])} onBack={vi.fn()} videoSrc={videoSrc} onPreview={onPreview} />)
  fireEvent.click(idle.getByRole('button', { name: /영상 보기/ }))
  expect(onPreview).toHaveBeenCalledWith('c1')
})

it('details page without video preview still shows the basis scene image', () => {
  const frameSrc = (ref: string) => `/frame/${ref}`
  const basis = { ...candidateBase, candidate_id: 'c1', rank: 1, selected: true, thumb_ref: 'thumb1', video_preview: undefined }
  const screen = render(<DetailsCheck view={view([basis])} onBack={vi.fn()} frameSrc={frameSrc} />)
  expect(screen.container.querySelector('.details-scene img')?.getAttribute('src')).toBe('/frame/thumb1')
})
