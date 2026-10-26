import type { CSSProperties, JSX } from 'react'

// 자동차 출발·진행·도착 연출에 쓰는 연기·속도선·파동. 모양과 움직임은 refresh.css(.rs-puff · .rs-speed ·
// .rs-ring)가 정하고, 여기서는 위치·크기·지연만 CSS 변수로 넘긴다. 매번 같은 모양이 나오게 고정 시드로
// 흩뿌린다(테스트·캡처가 흔들리지 않음). 모두 장식이라 읽기 도구에서는 숨긴다.

/** 연기 한 덩이 — x·y는 놓일 칸 기준 px, dx·dy는 퍼져 나가는 거리, d·t는 지연·길이(ms), g는 커지는 배율 */
export type Puff = { x: number; y: number; size: number; dx: number; dy: number; d: number; t: number; g?: number }

/** 0~1 고정 난수열 — 같은 seed면 늘 같은 값 */
export function seeded(seed: number): () => number {
  let s = seed % 2147483647 || 1
  return () => (s = (s * 48271) % 2147483647) / 2147483647
}

/** 한 점에서 n덩이를 흩뿌린다 — 지연은 from부터 gap 간격, 크기·퍼짐은 범위 안에서 */
export function burst(
  n: number,
  at: { x: number; y: number },
  o: { from: number; gap: number; size: [number, number]; dx: [number, number]; dy: [number, number]; t: number; g?: number; seed: number },
): Puff[] {
  const r = seeded(o.seed)
  const pick = ([a, b]: [number, number]) => a + (b - a) * r()
  return Array.from({ length: n }, (_, i) => ({
    x: at.x + (r() - 0.5) * 14,
    y: at.y + (r() - 0.5) * 6,
    size: pick(o.size),
    dx: pick(o.dx),
    dy: pick(o.dy),
    d: o.from + i * o.gap,
    t: o.t,
    g: o.g,
  }))
}

/** loop: 끝나면 같은 자리에서 다시 피어난다(진행 중 박스처럼 계속 도는 장면) */
export function Puffs(props: { items: Puff[]; loop?: boolean }): JSX.Element {
  return (
    <>
      {props.items.map((p, i) => (
        <span
          key={i}
          className={`rs-puff${props.loop ? ' is-loop' : ''}`}
          aria-hidden
          style={
            {
              '--x': `${p.x}px`,
              '--y': `${p.y}px`,
              '--s': `${p.size}px`,
              '--dx': `${p.dx}px`,
              '--dy': `${p.dy}px`,
              '--d': `${p.d}ms`,
              '--t': `${p.t}ms`,
              '--g': p.g ?? 3,
            } as CSSProperties
          }
        />
      ))}
    </>
  )
}

/** 속도선 — x·y 자리에서 w 길이로 나타나 뒤(오른쪽)로 흘러가며 사라진다 */
export type Speed = { x: number; y: number; w: number; d: number }

export function SpeedLines(props: { items: Speed[] }): JSX.Element {
  return (
    <>
      {props.items.map((l, i) => (
        <span
          key={i}
          className="rs-speed"
          aria-hidden
          style={{ '--x': `${l.x}px`, '--y': `${l.y}px`, '--w': `${l.w}px`, '--d': `${l.d}ms` } as CSSProperties}
        />
      ))}
    </>
  )
}
