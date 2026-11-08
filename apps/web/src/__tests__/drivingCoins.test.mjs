import { it } from 'vitest'
import assert from 'node:assert/strict'
import {
  createRun,
  move,
  jump,
  advance,
  setJumpHeld,
  courseBetween,
  COINS_PER_SHIELD,
} from '../components/driving/game/rules.mjs'
import { drive } from './drivingDriver.mjs'
it('coin pickup and shield rewards', () => {
  const run = () => {
    const s = createRun()
    s.phase = 'playing'
    return s
  }
  const until = (s, d, autopilot = false) => {
    while (s.distance < d && s.phase === 'playing') {
      if (autopilot)
        drive(
          s,
          (a, b) => courseBetween(a, b, s.seed),
          (d) => move(s, d),
          () => jump(s),
          (h) => setJumpHeld(s, h),
        )
      advance(s, 1 / 120)
    }
  }
  const s = run()
  until(s, 27)
  assert.equal(s.coins, 3)
  assert.equal(s.coinCharge, 3)
  assert.equal(s.shields, 0)
  assert.equal(s.collected.size, 3)
  while (s.coins < COINS_PER_SHIELD && s.phase === 'playing')
    until(s, s.distance + 1, true)
  assert.equal(s.coins, 10)
  assert.equal(s.shields, 1)
  assert.equal(s.coinCharge, 0)
  assert.equal(s.collected.size, 10)
  const missed = run()
  move(missed, -1)
  until(missed, 27)
  assert.equal(missed.coins, 0)
  const high = run()
  high.distance = 11
  high.height = 4
  high.airborne = true
  advance(high, 0.01)
  assert.equal(high.coins, 0)
  const paused = run()
  paused.phase = 'paused'
  advance(paused, 1)
  assert.equal(paused.coins, 0)
  const fresh = createRun()
  assert.equal(fresh.shields, 0)
  assert.equal(fresh.collected.size, 0)
}, 60000)

it('uses three shields automatically, then ends on the next collision', () => {
  const s = createRun(17)
  s.phase = 'playing'
  s.shields = 3
  const encounters = courseBetween(0, 2000, s.seed)
    .segments.filter((segment) => segment.rows.length)
    .slice(0, 4)
  assert.equal(encounters.length, 4)
  encounters.forEach((segment, index) => {
    const row = segment.rows[0],
      car = row.cars.find((car) => car.type !== 'gate')
    s.distance = car.distance - 1
    s.x = car.x
    s.lane = car.lane
    advance(s, 1 / 120)
    assert.equal(s.shields, Math.max(0, 2 - index))
    assert.equal(s.shieldsUsed, Math.min(3, index + 1))
    assert.equal(s.phase, index === 3 ? 'over' : 'playing')
    if (index < 3) {
      advance(s, 1 / 120)
      assert.equal(
        s.shieldsUsed,
        index + 1,
        'one encounter consumes only one shield',
      )
    }
  })
})

it('coins cannot refill shields after all three have been used', () => {
  const s = createRun()
  s.phase = 'playing'
  s.shieldsUsed = 3
  while (s.distance < 27) advance(s, 1 / 120)
  assert.equal(s.coins, 3)
  assert.equal(s.coinCharge, 0)
  assert.equal(s.shields, 0)
})
