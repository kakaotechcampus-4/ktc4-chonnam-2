import { expect, it } from 'vitest'
import { nextDrivingFrame } from '../components/driving/frameTiming'

it.each([60, 120, 144])('keeps 30fps and elapsed time at %iHz with refresh jitter', hz => {
  let last = 0, deadline = 0, frames = 0, elapsed = 0
  for (let i = 0; i <= hz * 10; i++) {
    const now = 100 + i * 1000 / hz + (i % 3) * .1
    const frame = nextDrivingFrame(now, last, deadline)
    if (!frame) continue
    last = frame.last; deadline = frame.deadline
    elapsed += frame.dt
    if (frame.dt) frames++
  }
  expect(frames).toBeGreaterThanOrEqual(299)
  expect(frames).toBeLessThanOrEqual(301)
  expect(elapsed).toBeCloseTo(10, 1)
})

it('caps a stall and resets time when resuming', () => {
  expect(nextDrivingFrame(1000, 100, 134)?.dt).toBe(.08)
  expect(nextDrivingFrame(5000, 0, 134)?.dt).toBe(0)
})
