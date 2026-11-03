// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { createApi } from '../api/client'
import type { Candidate, CaseView } from '../contracts/caseView'
import { SNAPSHOTS } from '../contracts/fixtures'
import { CandidatesScreen } from '../screens/CandidatesScreen'
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
  expect(screen.getByRole('status').textContent).toContain('영상 준비 중')
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

it('keeps playback available when its poster cannot be loaded', () => {
  const screen = render(<CandidatesScreen view={view([{ ...candidate(1), thumb_ref: 'broken' }])}
    frameSrc={(ref) => `/frame/${ref}`} onPreview={vi.fn()} />)
  fireEvent.error(screen.getByRole('img', { name: '1번 후보 장면' }))
  expect(screen.queryByRole('img', { name: '1번 후보 장면' })).toBeNull()
  expect(screen.getByRole('button', { name: '1번 후보 영상 보기' })).toBeTruthy()
})
