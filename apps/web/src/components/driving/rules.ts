// A local simulation plan, not an analysis status or a real-road timing specification.
export const GRID = 96
type Kind = 'straight' | 'yellow' | 'clear' | 'left' | 'left-yellow'
interface Phase { axis: number; kind: Kind; seconds: number; start: number }
const sequence: [Kind, number][] = [['straight', 30], ['yellow', 3], ['clear', 2], ['left', 6], ['left-yellow', 3], ['clear', 3]]
export const signalStages: Phase[] = []
let duration = 0
for (const axis of [0, 1]) for (const [kind, seconds] of sequence) {
  signalStages.push({ axis, kind, seconds, start: duration })
  duration += seconds
}
export const SIGNAL_CYCLE = duration
const mod = (n: number, m: number) => ((n % m) + m) % m

export function signalState(time: number, x = 0, z = 0) {
  const offset = mod(Math.round(x / GRID) * 31 + Math.round(z / GRID) * 19 + 19, SIGNAL_CYCLE)
  const absolute = time + offset, t = mod(absolute, SIGNAL_CYCLE)
  const s = signalStages.find(p => t < p.start + p.seconds)!
  return { ...s, elapsed: t - s.start, remaining: s.start + s.seconds - t, t, cycle: Math.floor(absolute / SIGNAL_CYCLE) }
}

// The axis names the ROAD being crossed. Parallel walkers share the other road's straight phase.
export function pedestrianAspect(crossedAxis: number, time: number, x = 0, z = 0) {
  const s = signalState(time, x, z)
  const start = signalStages.find(p => p.axis !== crossedAxis && p.kind === 'straight')!.start
  const elapsed = s.t - start
  const phase = elapsed >= 0 && elapsed < 5 ? 'walk' : elapsed >= 5 && elapsed < 27 ? 'flash' : 'red'
  return { phase, elapsed, cycle: s.cycle, remaining: phase === 'walk' ? 5 - elapsed : phase === 'flash' ? 27 - elapsed : 0, untilWalk: mod(start - s.t, SIGNAL_CYCLE) }
}

export function signalAspect(dir: number, time: number, x = 0, z = 0) {
  const s = signalState(time, x, z), own = s.axis === dir % 2
  return { red: !own || !['straight', 'yellow'].includes(s.kind), yellow: own && ['yellow', 'left-yellow'].includes(s.kind), left: own && s.kind === 'left', straight: own && s.kind === 'straight', ...s }
}

export function signalPhase(dir: number, time: number, x = 0, z = 0) {
  const s = signalAspect(dir, time, x, z)
  return s.straight ? 'green' : s.yellow ? 'yellow' : 'red'
}

export function crossingPose(time: number, x: number, z: number, axis: number, armSide = 1) {
  const s = pedestrianAspect(axis, time, x, z), delay = .4 + axis * .8 + (armSide < 0 ? .6 : 0)
  const side = (s.cycle + (armSide < 0 ? 1 : 0)) % 2 ? -1 : 1
  const p = Math.max(0, Math.min(1, (s.elapsed - delay) / (21.6 / 1.05)))
  return { x: side * (10.8 - 21.6 * p), z: armSide * 10.5, side, moving: p > 0 && p < 1, progress: p, canStart: s.phase === 'walk' }
}

export function crossingOccupied(time: number, j: { x: number; z: number }, axis: number, armSide: number) {
  const p = crossingPose(time, j.x, j.z, axis, armSide)
  return p.moving || p.progress === 0 && p.canStart
}
