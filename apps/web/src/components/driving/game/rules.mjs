import { LANES, speedAt, courseBetween } from './course.mjs'
export { LANES, speedAt, courseBetween } from './course.mjs'
export const DOUBLE_WINDOW = 0.3
export const GRAVITY = 31.2
export const MAX_HOLD = 1.65
export const ROLL_HOLD = 0.48
export const ROLL_DURATION = 0.78
export const COINS_PER_SHIELD = 10
export const MAX_SHIELDS = 3
export const clamp = (n, a, b) => Math.max(a, Math.min(b, n))
export function createRun(seed = 17) {
  return {
    phase: 'ready',
    seed,
    time: 0,
    distance: 0,
    x: 0,
    lane: 1,
    height: 0,
    vy: 0,
    airborne: false,
    speed: 18,
    combo: 0,
    passed: new Set(),
    collected: new Set(),
    coinFlights: [],
    coins: 0,
    coinCharge: 0,
    shields: 0,
    shieldsUsed: 0,
    coinAt: -100,
    shieldAt: -100,
    shieldHitAt: -100,
    protectedRows: new Set(),
    protectedGroups: new Set(),
    jumpAt: -100,
    jumpDuration: 0,
    jumpCount: 0,
    doubleAt: -100,
    jumpKind: 'short',
    nextJump: 0,
    jumpBufferUntil: -100,
    jumpHeld: false,
    boostActive: false,
    boostAt: -100,
    rollAt: -100,
    rollProgress: 0,
    rolls: 0,
    airPassed: 0,
    totalAir: 0,
    highJumps: 0,
    jumps: 0,
    lastMove: -100,
    moveDirection: 0,
    landingAt: -100,
    landingStrength: 0,
    jumpX: 0,
    jumpDistance: 0,
    landingX: 0,
    landingDistance: 0,
    clearAt: -100,
    lastEvent: '',
    eventUntil: 0,
    failReason: '',
    level: 1,
    levelAt: -100,
  }
}
export function announce(s, text, duration = 1) {
  s.lastEvent = text
  s.eventUntil = s.time + duration
}
export function move(s, d) {
  if (s.phase !== 'playing') return false
  const lane = clamp(s.lane + Math.sign(d), 0, 2)
  if (lane === s.lane) return false
  s.lane = lane
  s.lastMove = s.time
  s.moveDirection = Math.sign(d)
  return true
}
// Nearby traffic informs the warning only. It never controls flight time.
export function jumpPlan(s) {
  const rows = courseBetween(s.distance - 3, s.distance + 65, s.seed).rows
  const row = rows.find(
    (r) =>
      !s.protectedGroups.has(r.groupId) &&
      r.cars.some((c) => c.lane === s.lane),
  )
  if (!row) return { count: 0, car: null, row: null, gap: Infinity }
  const cars = row.cars.filter((c) => c.lane === s.lane),
    car =
      cars.find((c) => c.type === 'wall') ??
      cars.find((c) => c.type !== 'gate') ??
      cars[0]
  return {
    count: rows.filter((r) => r.groupId === row.groupId && r.kind === 'queue')
      .length,
    car,
    row,
    gap: row.distance - s.distance,
  }
}
export function canDouble(s) {
  return (
    s.phase === 'playing' &&
    s.airborne &&
    s.jumpCount === 1 &&
    s.time - s.jumpAt <= DOUBLE_WINDOW
  )
}
export function jump(s) {
  if (s.phase !== 'playing') return false
  if (s.airborne) {
    if (canDouble(s)) {
      s.jumpCount = 2
      s.doubleAt = s.time
      s.highJumps++
      s.vy = Math.sqrt(2 * GRAVITY * Math.max(0.1, 4.6 - s.height))
      s.jumpKind = 'high'
      return 'double'
    }
    if (s.height < 0.7 && s.vy < 0) {
      s.jumpBufferUntil = s.time + 0.14
      return 'buffered'
    }
    return false
  }
  if (s.time < s.nextJump) {
    s.jumpBufferUntil = s.nextJump + 0.14
    return 'buffered'
  }
  s.airborne = true
  s.vy = 13.2
  s.jumpAt = s.time
  s.doubleAt = -100
  s.jumpCount = 1
  s.jumpKind = 'short'
  s.airPassed = 0
  s.jumps++
  s.jumpBufferUntil = -100
  s.jumpX = s.x
  s.jumpDistance = s.distance
  s.boostActive = false
  s.jumpDuration = 0
  s.rollAt = -100
  s.rollProgress = 0
  return 'single'
}
export function setJumpHeld(s, held) {
  s.jumpHeld = s.phase === 'playing' && held
  if (!s.jumpHeld) s.boostActive = false
}
export function advance(s, dt) {
  if (s.phase !== 'playing') return s
  dt = clamp(dt, 0, 0.05)
  if (!dt) return s
  const prev = { t: s.time, d: s.distance, x: s.x, h: s.height, vy: s.vy },
    speed = speedAt(s.distance),
    nextD = s.distance + speed * dt,
    nextX = s.x + (LANES[s.lane] - s.x) * (1 - Math.exp(-dt * 20)),
    age = s.time - s.jumpAt
  s.boostActive = s.airborne && s.jumpHeld && age >= 0.18 && age < MAX_HOLD
  let acceleration = -GRAVITY
  if (s.boostActive) {
    if (s.boostAt < s.jumpAt) s.boostAt = s.time
    s.jumpKind = s.jumpCount === 2 ? 'high-boost' : 'boost'
    const target = s.jumpCount === 2 ? 4.3 : 2.65
    acceleration = clamp(65 * (target - s.height) - 16 * s.vy, -GRAVITY, 42)
  }
  const predictedHeight = (f) =>
    s.airborne
      ? Math.max(
          0,
          prev.h + prev.vy * dt * f + 0.5 * acceleration * (dt * f) ** 2,
        )
      : 0
  const nextH = predictedHeight(1),
    nextV = s.airborne ? prev.vy + acceleration * dt : 0,
    course = courseBetween(prev.d - 6, nextD + 6, s.seed)
  let hit = null
  for (let n = 1; n <= 5 && !hit; n++) {
    const f = n / 5,
      d = prev.d + (nextD - prev.d) * f,
      x = prev.x + (nextX - prev.x) * f,
      h = predictedHeight(f)
    for (const row of course.rows)
      for (const c of row.cars) {
        if (s.protectedGroups.has(row.groupId)) continue
        const margin =
          c.type === 'truck'
            ? 4.4
            : c.type === 'gate'
              ? 3
              : c.type === 'wall'
                ? 3.2
                : 3.9
        if (
          Math.abs(d - c.distance) < margin &&
          Math.abs(x - c.x) < 1.7 &&
          (c.type === 'gate'
            ? h > c.clearance && h < c.height + 0.08
            : h < c.height + 0.08)
        ) {
          hit = { fraction: (n - 1) / 5, car: c, row }
          break
        }
      }
  }
  if (hit && s.shields > 0 && s.shieldsUsed < MAX_SHIELDS) {
    s.shields--
    s.shieldsUsed++
    s.shieldHitAt = prev.t
    s.protectedRows.add(hit.row.id)
    s.protectedGroups.add(hit.row.groupId)
    announce(s, `보호막 발동 · ${s.shields}개 남음`, 1.2)
    hit = null
  }
  if (hit) {
    const f = hit.fraction
    s.time = prev.t + dt * f
    s.distance = prev.d + (nextD - prev.d) * f
    s.x = prev.x + (nextX - prev.x) * f
    s.height = predictedHeight(f)
    s.phase = 'over'
    s.jumpHeld = false
    s.boostActive = false
    s.jumpBufferUntil = -100
    s.failReason =
      hit.car.type === 'gate'
        ? 'clearance'
        : hit.car.type === 'wall'
          ? 'lane'
          : hit.car.type === 'truck'
            ? 'tall'
            : 'traffic'
    return s
  }
  s.time += dt
  s.distance = nextD
  s.x = nextX
  s.height = nextH
  s.vy = nextV
  s.speed = speed
  // The stunt is visual only: it never changes height, steering, or collision rules.
  if (
    s.airborne &&
    s.boostActive &&
    age >= ROLL_HOLD &&
    s.height > 2 &&
    s.rollAt < s.jumpAt
  ) {
    s.rollAt = s.time
    s.rolls++
  }
  if (s.airborne && s.rollAt >= s.jumpAt && s.rollProgress < 1) {
    let rate = 1 / ROLL_DURATION
    if (!s.boostActive) {
      const uprightIn =
        (s.vy +
          Math.sqrt(s.vy * s.vy + 2 * GRAVITY * Math.max(0, s.height - 0.8))) /
        GRAVITY
      rate = Math.max(rate, (1 - s.rollProgress) / Math.max(0.02, uprightIn))
    }
    s.rollProgress =
      s.height <= 0.8 ? 1 : Math.min(1, s.rollProgress + dt * rate)
  }

  for (const row of course.rows)
    if (s.distance > row.distance + 4.5 && !s.passed.has(row.id)) {
      s.passed.add(row.id)
      s.combo++
      s.clearAt = s.time
      if (s.airborne && row.lanes.some((l) => Math.abs(s.x - LANES[l]) < 1.7)) {
        s.airPassed++
        s.totalAir++
      }
      if (s.combo % 5 === 0) announce(s, `${s.combo}연속 통과`, 0.75)
    }
  if (s.airborne && s.height === 0 && s.vy < 0) {
    s.airborne = false
    s.landingStrength = Math.min(1, Math.abs(s.vy) / 16)
    s.vy = 0
    s.boostActive = false
    s.jumpHeld = s.jumpHeld && s.jumpBufferUntil >= s.time
    s.landingAt = s.time
    s.landingX = s.x
    s.landingDistance = s.distance
    s.jumpDuration = s.time - s.jumpAt
    s.nextJump = s.time + 0.035
    if (s.airPassed > 1) announce(s, `${s.airPassed}대 통과`, 0.8)
  }
  const level = 1 + Math.floor(s.distance / 420)
  if (level > s.level) {
    s.level = level
    s.levelAt = s.time
  }
  s.coinFlights = s.coinFlights.filter((p) => s.time - p.at < 0.36)
  for (const p of course.pickups) {
    if (s.collected.has(p.id)) continue
    const f = clamp((p.distance - prev.d) / (nextD - prev.d), 0, 1),
      d = prev.d + (nextD - prev.d) * f,
      x = prev.x + (nextX - prev.x) * f,
      h = predictedHeight(f)
    if (
      Math.abs(d - p.distance) > 1.8 ||
      Math.abs(x - p.x) > 1.05 ||
      Math.abs(h - p.height) > 0.95
    )
      continue
    s.collected.add(p.id)
    s.coins++
    if (s.shields + s.shieldsUsed < MAX_SHIELDS) s.coinCharge++
    s.coinAt = s.time
    s.coinFlights.push({ ...p, at: s.time })
    if (s.coinCharge === COINS_PER_SHIELD) {
      s.coinCharge = 0
      s.shields++
      s.shieldAt = s.time
      announce(s, '보호막 +1 · 한 판 최대 3회', 1.5)
    } else if (s.coins === 1) announce(s, '동전 10개를 모으면 보호막', 1.5)
  }
  if (s.collected.size > 100) s.collected = new Set([...s.collected].slice(-60))
  if (s.protectedGroups.size > 40)
    s.protectedGroups = new Set([...s.protectedGroups].slice(-20))
  if (s.protectedRows.size > 40)
    s.protectedRows = new Set([...s.protectedRows].slice(-20))
  if (s.passed.size > 100) s.passed = new Set([...s.passed].slice(-40))
  if (!s.airborne && s.jumpBufferUntil >= s.time && s.time >= s.nextJump)
    jump(s)
  return s
}
