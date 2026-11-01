import { useLayoutEffect, useRef, useState, type JSX } from 'react'
import type { CaseView } from '../contracts/caseView'
import '../styles/candidates.css'

// 후보 비교 시간축(core-user-flow §8-2, PROTOTYPE-SPEC §6 SearchAxis). 막대 아래 번호 원이
// 후보 위치를 가리키고, 번호는 카드 번호와 같다(CandidateCard — case의 `rank`, 없으면 배열 순서 + 1). 마커에는 시각을 쓰지 않는다 — 카드에서 읽는다.
// 위치는 `marker_ms / timeline_duration_ms` 그대로다. `marker_ms`가 없는 후보(stale)는 마커만 빠지고, 길이가 없거나 마커가 하나도 없으면 시간축을 그리지 않는다.
const PIN = 28
const GAP = 6

/** 겹치는 원은 아래 줄로 내린다(1단계 목업 규칙). 왼쪽부터 놓고, 앞 원과 원 하나만큼 떨어지지 않으면 다음 줄이다. */
export function axisRows(pcts: number[], widthPx: number): number[] {
  const lastX: number[] = []
  return pcts.map((pct) => {
    const x = (pct / 100) * widthPx
    let row = lastX.findIndex((prev) => x - prev >= PIN + GAP)
    if (row < 0) row = lastX.length
    lastX[row] = x
    return row
  })
}

export function CandidateAxis(props: { view: CaseView }): JSX.Element | null {
  const duration = props.view.timeline_duration_ms ?? 0
  const pins =
    duration > 0
      ? props.view.candidates
          .map((c, i) => ({ id: c.candidate_id, n: c.rank ?? i + 1, selected: c.selected, ms: c.marker_ms }))
          .filter((p): p is { id: string; n: number; selected: boolean; ms: number } => p.ms != null)
          .map((p) => ({ ...p, pct: Math.min(100, Math.max(0, (p.ms / duration) * 100)) }))
          .sort((a, b) => a.pct - b.pct)
      : []
  const shown = pins.length > 0
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    setWidth(el.clientWidth)
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [shown])
  if (!shown) return null
  const rows = width > 0 ? axisRows(pins.map((p) => p.pct), width) : pins.map(() => 0)
  // 기준 후보는 채운 원으로만 보이므로 라벨에도 적는다(#509 #6)
  const label = pins.map((p) => `${p.n}번 ${clock(p.ms)}${p.selected ? ' (지금 기준)' : ''}`).join(', ')
  const [from, to] = axisEnds(props.view.manifest_summary.range, duration)
  return (
    <div className="cand-axis" ref={ref} role="img" aria-label={`시간축(${from}–${to})에서 후보 위치: ${label}`}>
      <div className="cand-axis-ends" aria-hidden>
        <span>{from}</span>
        <span>{to}</span>
      </div>
      <div className="cand-axis-bar" />
      <div className="cand-axis-pins" style={{ height: PIN + 14 + Math.max(...rows) * (PIN + GAP) }}>
        {pins.map((p, i) => (
          <span
            key={p.id}
            className={`cand-axis-pin${p.selected ? ' sel' : ''}`}
            style={{ left: `${p.pct}%`, ['--row' as string]: rows[i] }}
          >
            <i />
            <b>{p.n}</b>
          </span>
        ))}
      </div>
    </div>
  )
}

function clock(ms: number): string {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}분 ${s % 60}초`
}

/** 막대 양 끝 기준. 촬영 시각 범위(`manifest_summary.range`)가 있으면 그 시각, 없으면 영상 안 시간(0:00 · 전체 길이)이다.
 *  range는 ISO 문자열이든 「18:03」이든 시각 부분만 쓴다 — 날짜는 카드에 있다. */
export function axisEnds(range: [string, string] | null, durationMs: number): [string, string] {
  const hm = (v: string) => v.match(/\d{2}:\d{2}(:\d{2})?/)?.[0]
  const a = range && hm(range[0])
  const b = range && hm(range[1])
  if (a && b) return [a, b]
  const s = Math.floor(durationMs / 1000)
  const h = Math.floor(s / 3600)
  const mm = String(Math.floor((s % 3600) / 60)).padStart(h ? 2 : 1, '0')
  const ss = String(s % 60).padStart(2, '0')
  return ['0:00', h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`]
}
