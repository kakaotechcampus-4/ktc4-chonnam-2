import { it } from 'vitest'
import assert from 'node:assert/strict'
import {
  courseBetween,
  wallGapAt,
  speedAt,
} from '../components/driving/game/course.mjs'
import {
  createRun,
  advance,
  move,
  jump,
  setJumpHeld,
} from '../components/driving/game/rules.mjs'
import { drive } from './drivingDriver.mjs'
it('level 31 wall spacing remains passable', () => {
  for (const [distance, gap] of [
    [0, 47.7846153846],
    [6720, 58.7222222222],
    [10080, 50.9444444444],
    [12599, 50.9444444444],
    [12600, 45.1111111111],
  ]) {
    assert.ok(Math.abs(wallGapAt(distance) - gap) < 1e-6)
  }
  assert.equal(wallGapAt(50000), wallGapAt(12600), 'cap the final difficulty')
  for (let seed = 0; seed < 40; seed++) {
    const course = courseBetween(9000, 18500, seed),
      rest = course.segments.findLast(
        (s) => s.kind === 'rest' && s.start < 12600,
      )
    assert.ok(rest)
    for (let i = 0; i < course.rows.length - 1; i++) {
      const row = course.rows[i],
        next = course.rows[i + 1]
      if (row.distance >= 12600 && row.cars.some((c) => c.type === 'wall')) {
        assert.ok(
          next.distance - row.distance >= wallGapAt(row.distance) - 1e-6,
          'wall gap also holds at encounter boundaries',
        )
      }
    }
    const s = Object.assign(createRun(seed), {
      phase: 'playing',
      distance: rest.start,
      speed: speedAt(rest.start),
      level: 1 + Math.floor(rest.start / 420),
    })
    while (s.phase === 'playing' && s.distance < 18500) {
      const prev = courseBetween(
        s.distance - 22,
        s.distance,
        seed,
      ).rows.findLast((r) => r.cars.some((c) => c.type === 'wall'))
      const hidden = prev && s.distance < prev.distance + 14 + s.speed * 0.15
      if (!hidden)
        drive(
          s,
          (a, b) => courseBetween(a, b, seed),
          (d) => move(s, d),
          () => jump(s),
          (h) => setJumpHeld(s, h),
        )
      advance(s, 1 / 120)
    }
    assert.equal(
      s.phase,
      'playing',
      `failed at ${s.distance}m, seed ${seed}, ${s.failReason}`,
    )
    assert.equal(s.shieldsUsed, 0, `needed a shield, seed ${seed}`)
  }
}, 60000)
