import { it } from 'vitest'
import assert from 'node:assert/strict'
import { motion } from '../components/driving/game/motion.mjs'
import {
  createRun,
  jump,
  advance,
  setJumpHeld,
  courseBetween,
  speedAt,
} from '../components/driving/game/rules.mjs'
it('a held jump rolls once and respects reduced motion', () => {
  const run = createRun(17)
  run.phase = 'playing'
  setJumpHeld(run, true)
  jump(run)
  for (let i = 0; i < 96; i++) advance(run, 1 / 120)
  assert.equal(run.rolls, 1)
  assert.ok(motion(run).stuntRoll < -0.1)
  assert.equal(motion(run, true).stuntRoll, 0)
  for (let i = 0; i < 65; i++) advance(run, 1 / 120)
  assert.equal(run.rolls, 1)
  assert.equal(run.rollProgress, 1)
  assert.ok(Math.abs(motion(run).stuntRoll + Math.PI * 2) < 1e-6)
})
it('short, held and double jumps', () => {
  const step = (s, t) => {
    while (t > 1e-8) {
      const dt = Math.min(1 / 120, t)
      advance(s, dt)
      t -= dt
    }
  }
  const at = (d) => {
    const s = createRun(17)
    s.phase = 'playing'
    s.distance = d
    s.speed = speedAt(d)
    return s
  }
  const short = at(0)
  jump(short)
  step(short, 1)
  assert.equal(short.airborne, false)
  assert.ok(short.jumpDuration > 0.8 && short.jumpDuration < 0.9)
  const hold = at(0)
  setJumpHeld(hold, true)
  jump(hold)
  step(hold, 1.1)
  assert.ok(hold.airborne && hold.boostActive && hold.height > 2.5)
  const h = hold.height
  setJumpHeld(hold, false)
  assert.equal(hold.height, h)
  step(hold, 0.5)
  assert.equal(hold.airborne, false)
  const capped = at(0)
  setJumpHeld(capped, true)
  jump(capped)
  step(capped, 2.2)
  assert.equal(capped.airborne, false)
  const all = courseBetween(0, 1500, 17),
    truck = all.rows.find((r) => r.kind === 'tall')
  const tall = at(truck.distance - speedAt(truck.distance) * 0.64)
  jump(tall)
  step(tall, 0.14)
  const before = tall.height
  assert.equal(jump(tall), 'double')
  assert.equal(tall.height, before)
  assert.equal(jump(tall), false)
  step(tall, 1.5)
  assert.equal(tall.phase, 'playing')
  const queue = all.segments.find((s) => s.kind === 'long'),
    first = queue.rows[0].distance,
    last = queue.rows.at(-1).distance
  const early = at(first - speedAt(first) * 0.43)
  jump(early)
  step(early, 1.8)
  assert.equal(early.phase, 'over', 'a tap cannot automatically clear a queue')
  const long = at(first - speedAt(first) * 0.43)
  setJumpHeld(long, true)
  jump(long)
  while (long.distance < last + 4.8 && long.phase === 'playing')
    step(long, 1 / 120)
  setJumpHeld(long, false)
  step(long, 0.5)
  assert.equal(long.phase, 'playing')
  assert.equal(long.airPassed, queue.rows.length)
}, 60000)
