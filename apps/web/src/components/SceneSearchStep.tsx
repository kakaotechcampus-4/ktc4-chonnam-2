import { Check } from 'lucide-react'
import type { CaseView } from '../contracts/caseView'
import { SCENE_SEARCH_DELAY_MS, SCENE_SEARCH_MESSAGES as COPY } from '../contracts/labels.flow'

export function SceneSearchStep({ state, progress, now, active }: {
  state: 'RUNNING' | 'DONE'
  progress: CaseView['scene_search']
  now: number
  active: boolean
}) {
  const done = state === 'DONE'
  const phase = progress?.phase
  const completed = done ? 3 : phase === 'ORGANIZING' ? 2 : phase === 'SEARCHING' ? 1 : 0
  const preparing = !done && completed === 0
  const startedAt = progress?.search_started_at ? Date.parse(progress.search_started_at) : NaN
  const delayed = active && phase === 'SEARCHING' && Number.isFinite(startedAt) && now - startedAt >= SCENE_SEARCH_DELAY_MS
  const message = done ? COPY.DONE : delayed ? COPY.DELAYED : (phase && COPY[phase]) || COPY.UNKNOWN

  return (
    <li className={`tl-${state.toLowerCase()} scene-search-step${active ? ' is-active' : ''}${preparing ? ' is-preparing' : ''}`}>
      <span
        className="scene-search-mark"
        role="progressbar"
        aria-label="장면 찾기"
        aria-valuemin={0}
        aria-valuemax={3}
        aria-valuenow={preparing ? undefined : completed}
        aria-valuetext={preparing ? message : `3개 작업 중 ${completed}개 완료. ${message}`}
      >
        {done ? <Check aria-hidden /> : (
          <svg className="scene-search-ring" viewBox="0 0 32 32" aria-hidden>
            <circle className="scene-search-track" cx="16" cy="16" r="13" />
            <circle className="scene-search-fill" cx="16" cy="16" r="13" pathLength="100"
              strokeDasharray="100" strokeDashoffset={preparing ? 75 : 100 - completed / 3 * 100} />
          </svg>
        )}
      </span>
      <span className="tl-label">장면 찾기</span>
      <span className="kv-src">{done ? '완료' : '진행 중'}</span>
      <p className={`scene-search-detail${done ? ' is-done' : active ? ' is-running' : ''}`} role="status" aria-atomic="true">
        <span>{message}</span>
      </p>
    </li>
  )
}
