export const LANES = [-3.5, 0, 3.5]
const SPEED_STAGES = [
  [0, 65],
  [840, 85],
  [1680, 105],
  [2520, 120],
  [3780, 135],
  [5460, 140],
]
export function speedAt(d) {
  for (let i = 1; i < SPEED_STAGES.length; i++) {
    const [a, v] = SPEED_STAGES[i - 1],
      [b, w] = SPEED_STAGES[i]
    if (d < b) return (v + ((w - v) * Math.max(0, d - a)) / (b - a)) / 3.6
  }
  return 140 / 3.6
}
// Level 31 tightens expert walls again, leaving 0.8 s after the camera clears.
export const wallGapAt = (d) =>
  d < 6720
    ? 14 + Math.max(18 + Math.min(10, (d + 100) / 130), speedAt(d + 100)) * 1.8
    : d >= 12600
      ? 14 + speedAt(d + 100) * 0.8
      : 14 +
        speedAt(d + 100) * (1.15 - Math.min(0.2, ((d - 6720) / 3360) * 0.2))
export const PATTERNS = [
  'short',
  'high',
  'long',
  'weave',
  'choice',
  'lowpass',
  'switch',
]
export const COMBOS = ['hop-switch', 'air-shift', 'switchback']
const hash = (n, seed) => {
  let x = (Math.imul(n, 374761393) + Math.imul(seed, 668265263)) | 0
  x = Math.imul(x ^ (x >>> 13), 1274126177)
  return (x ^ (x >>> 16)) >>> 0
}
const permutation = (bag, seed) =>
  PATTERNS.map((kind, i) => ({ kind, key: hash(bag * 31 + i, seed) }))
    .sort((a, b) => a.key - b.key)
    .map((x) => x.kind)
function patternAt(index, seed) {
  const bag = Math.floor(index / PATTERNS.length),
    order = permutation(bag, seed)
  if (bag && order[0] === permutation(bag - 1, seed).at(-1))
    [order[0], order[1]] = [order[1], order[0]]
  return order[index % order.length]
}
function makeSegment(index, start, seed, previousKind, previousLevel) {
  const rand = (n) => hash(index * 97 + n, seed),
    level = 1 + Math.floor(start / 420),
    id = `s${index}`,
    lane = rand(2) % 3,
    rows = [],
    pickups = []
  const slot = Math.max(0, index - 4) % 8,
    cycle = Math.floor(Math.max(0, index - 4) / 8),
    firstRest = (level >= 17 ? 4 : 2) + (hash(cycle, seed) % 3)
  const rest = index >= 4 && (slot === firstRest || (level < 17 && slot === 7)),
    challenge = cycle * 6 + slot - (slot > firstRest ? 1 : 0)
  const lessons = [
    'short',
    ...(hash(1, seed) % 2 ? ['weave', 'high'] : ['high', 'weave']),
    'long',
  ]
  let kind = rest
    ? 'rest'
    : index < 4
      ? lessons[index]
      : patternAt(challenge, seed)
  if (
    !rest &&
    level >= 4 &&
    rand(19) % 100 < Math.min(82, 25 + (level - 4) * 6)
  )
    kind =
      COMBOS[
        (rand(20) + Math.floor(level / 3)) % (level < 5 ? 1 : level < 7 ? 2 : 3)
      ]
  if (!rest && level >= 17 && (previousLevel < 17 || rand(24) % 100 < 72))
    kind = 'screened'
  if (!rest && kind === previousKind)
    kind =
      kind === 'screened'
        ? COMBOS[rand(20) % 3]
        : COMBOS.includes(kind)
          ? COMBOS[(COMBOS.indexOf(kind) + 1) % (level < 7 ? 2 : 3)]
          : patternAt(challenge + 1, seed)
  const lead = Math.max(22, 30 - (level - 1) * 0.6) + (rand(3) % 7),
    d = start + lead,
    speed = speedAt(d + 100),
    gap = speed * (0.95 + (rand(4) % 5) * 0.025),
    all = [0, 1, 2],
    other = all.filter((l) => l !== lane)
  let last = d,
    step = 0
  const add = (at, role, specs, routeLane) => {
    last = Math.max(last, at)
    const row = {
      id: `${id}r${step++}`,
      groupId: id,
      kind: role,
      distance: at,
      routeLane,
      lanes: specs.filter((c) => c.type !== 'gate').map((c) => c.lane),
      cars: [],
    }
    row.cars = specs.map((c, i) => ({
      id: `${row.id}c${i}`,
      groupId: id,
      distance: at,
      x: LANES[c.lane],
      height: c.type === 'truck' ? 3.1 : c.type === 'wall' ? 6.2 : 1.57,
      color: rand(step + i + 7) % 4,
      ...c,
    }))
    rows.push(row)
    return row
  }
  const car = (l, type = 'car') => ({ lane: l, type }),
    gate = (l, clearance) => ({
      lane: l,
      type: 'gate',
      clearance,
      height: clearance + 1.92,
    })
  const closed = (at, safe) =>
    add(
      at,
      'dodge',
      all
        .filter((l) => l !== safe)
        .map((l) => ({ ...car(l, 'wall'), safeLane: safe })),
    )
  const coins = (at, l, height, count = 2, spacing = 5) => {
    for (let i = 0; i < count; i++)
      pickups.push({
        id: `${id}p${pickups.length}`,
        distance: at + i * spacing,
        lane: l,
        x: LANES[l],
        height,
      })
  }
  // Truck + height bar closes a lane while keeping the road beyond visible.
  const blocked = (l) => [car(l, 'truck'), gate(l, 3.05)]
  const dodge = (at, safe) =>
    add(at, 'dodge', all.filter((l) => l !== safe).flatMap(blocked), safe)
  const adjacent = lane === 1 ? (rand(18) % 2 ? 0 : 2) : 1
  const single = (at, tall = false) =>
    add(at, tall ? 'tall' : 'short', [
      ...all.map((l) => car(l, tall ? 'truck' : 'car')),
      ...(tall ? [] : all.map((l) => gate(l, 3.05))),
    ])
  if (kind === 'rest') {
    coins(start + 9, lane, 0, level < 5 ? 2 : 1, 6)
    return {
      id,
      index,
      kind,
      level,
      start,
      end: start + speed * (level < 4 ? 1.35 : 1.05) + (rand(5) % 5),
      rows,
      pickups,
    }
  }
  if (kind === 'short') {
    add(d, 'short', [
      ...all.map((l) => car(l)),
      ...all.map((l) => gate(l, 3.05)),
    ])
    add(
      d + Math.max(24, speed * 1.05),
      'landing',
      all.map((l) => gate(l, 1.25)),
    )
    coins(d + Math.max(24, speed * 1.05) + 3, lane, 0, level < 5 ? 2 : 1)
  }
  if (kind === 'high') {
    add(
      d,
      'tall',
      all.map((l) => car(l, 'truck')),
    )
    coins(d - 1, lane, 4.3, 2, 4)
  }
  if (kind === 'long') {
    const count = level === 1 ? 3 : 3 + (rand(6) % (level >= 3 ? 3 : 2)),
      spacing =
        (speed * (level === 1 ? 0.72 : 0.9 + (rand(8) % 5) * 0.035)) /
        (count - 1)
    for (let n = 0; n < count; n++)
      add(d + n * spacing, 'queue', [
        ...all.map((l) => car(l)),
        ...(n === 0 ? all.map((l) => gate(l, 3.05)) : []),
      ])
    coins(d + 2, lane, 2.65, 3, ((count - 1) * spacing) / 3)
  }
  if (kind === 'weave') {
    const safe = rand(9) % 2 ? 0 : 2,
      path = level >= 3 ? [safe, 1, 2 - safe] : level === 1 ? [safe] : [safe, 1]
    let at = d
    path.forEach((l) => {
      closed(at, l)
      coins(at - 2, l, 0, 1)
      at += wallGapAt(at)
    })
  }
  if (kind === 'choice') {
    const high = other[0],
      wall = other[1]
    add(d, 'choice', [
      car(lane),
      gate(lane, 3.05),
      car(high, 'truck'),
      car(wall, 'wall'),
    ])
    coins(d, lane, 2.6, 1)
    coins(d - 2, high, 4.3, 3, 3)
  }
  if (kind === 'lowpass') {
    add(
      d,
      'low',
      all.map((l) => gate(l, 1.25)),
    )
    closed(d + gap, lane)
    coins(d + gap - 2, lane, 0, 2)
  }
  if (kind === 'switch') {
    const afterWall = d + wallGapAt(d)
    closed(d, lane)
    add(afterWall, 'short', [
      ...all.map((l) => car(l)),
      ...all.map((l) => gate(l, 3.05)),
    ])
    coins(afterWall, lane, 2.6, 2, 4)
  }
  if (kind === 'hop-switch') {
    single(d)
    dodge(d + speed * (1.03 + (rand(21) % 3) * 0.05), adjacent)
    coins(d, lane, 2.6, 2, 4)
    if (level >= 7) {
      single(d + speed * 2.1, true)
      coins(d + speed * 2.1, adjacent, 4.3, 3, 4)
    }
  }
  if (kind === 'air-shift') {
    add(
      d,
      'queue',
      [
        car(lane),
        ...other.map((l) => car(l, 'truck')),
        ...all.map((l) => gate(l, 3.05)),
      ],
      lane,
    )
    add(
      d + speed * 0.28,
      'queue',
      all.map((l) => car(l)),
      lane,
    )
    add(
      d + speed * 0.72,
      'queue',
      [
        car(adjacent),
        ...all.filter((l) => l !== adjacent).map((l) => car(l, 'truck')),
        ...all.map((l) => gate(l, 3.05)),
      ],
      adjacent,
    )
    add(
      d + speed * 1.14,
      'queue',
      all.map((l) => car(l)),
      adjacent,
    )
    coins(d + 1, lane, 2.65, 2, 4)
    coins(d + speed * 0.75, adjacent, 2.65, 3, 4)
  }
  if (kind === 'switchback') {
    dodge(d, lane)
    single(d + speed * 1.05, rand(22) % 2 === 0)
    dodge(d + speed * 2.05, adjacent)
    coins(d + speed * 1.05, lane, rand(22) % 2 === 0 ? 4.3 : 2.6, 3, 4)
  }
  if (kind === 'screened') {
    closed(d, lane)
    const variant = rand(26) % 3,
      count = 3 + (rand(27) % (level >= 22 ? 3 : 2))
    let at = d,
      safe = lane,
      action = 'dodge'
    for (let i = 1; i < count; i++) {
      at += wallGapAt(at) + (rand(30 + i) % 3)
      safe = (safe + 1 + (rand(40 + i) % 2)) % 3
      action =
        i === 1
          ? ['dodge', 'short', 'tall'][variant]
          : i === count - 1
            ? variant === 2
              ? 'short'
              : 'tall'
            : ['dodge', 'short', 'tall'][rand(50 + i) % 3]
      const walls = all
        .filter((l) => l !== safe)
        .map((l) => ({ ...car(l, 'wall'), safeLane: safe }))
      add(
        at,
        action,
        [
          ...walls,
          ...(action === 'dodge'
            ? []
            : [car(safe, action === 'tall' ? 'truck' : 'car')]),
          ...(action === 'short' ? [gate(safe, 3.05)] : []),
        ],
        safe,
      )
      coins(
        at,
        safe,
        action === 'dodge' ? 0 : action === 'tall' ? 4.3 : 2.6,
        action === 'dodge' ? 1 : 2,
        4,
      )
    }
    const reveal = at + wallGapAt(at),
      exit = (safe + 1 + (rand(28) % 2)) % 3
    single(reveal, action !== 'tall')
    coins(reveal, safe, action !== 'tall' ? 4.3 : 2.6, 2, 4)
    dodge(reveal + speed * 1.1, exit)
  }
  const wall = rows.findLast((r) => r.cars.some((c) => c.type === 'wall'))
  const breath =
    level < 4
      ? 1.9
      : level < 7
        ? 1.65
        : level < 10
          ? 1.45
          : level < 17
            ? 1.3
            : 1.2
  const end = Math.max(
    Math.max(last, ...pickups.map((p) => p.distance)) +
      Math.max(14, 32 - (level - 1) * 1.5) +
      (rand(10) % 6),
    last + speedAt(last + 120) * breath - 22,
    wall ? wall.distance + wallGapAt(wall.distance) - 22 : 0,
  )
  return { id, index, kind, level, start, end, rows, pickups }
}
// Keep only the nearby course. A backward query regenerates the same seeded sequence.
let cache = {
  seed: null,
  segments: [],
  nextStart: 20,
  nextIndex: 0,
  lastKind: '',
  lastLevel: 0,
}
export function courseBetween(start, end, seed = 17) {
  if (
    cache.seed !== seed ||
    (cache.segments[0]?.index > 0 && start < cache.segments[0].start)
  )
    cache = {
      seed,
      segments: [],
      nextStart: 20,
      nextIndex: 0,
      lastKind: '',
      lastLevel: 0,
    }
  while (cache.nextStart <= end) {
    const s = makeSegment(
      cache.nextIndex++,
      cache.nextStart,
      seed,
      cache.lastKind,
      cache.lastLevel,
    )
    cache.segments.push(s)
    cache.nextStart = s.end
    if (s.kind !== 'rest') {
      cache.lastKind = s.kind
      cache.lastLevel = s.level
    }
  }
  while (cache.segments.length > 1 && cache.segments[0].end < start - 512)
    cache.segments.shift()
  const segments = cache.segments.filter(
      (s) => s.end >= start && s.start <= end,
    ),
    rows = segments
      .flatMap((s) => s.rows)
      .filter((r) => r.distance >= start && r.distance <= end),
    pickups = segments
      .flatMap((s) => s.pickups)
      .filter((p) => p.distance >= start && p.distance <= end)
  for (let i = 0; i < 3; i++) {
    const distance = 12 + i * 6
    if (distance >= start && distance <= end)
      pickups.push({ id: `intro${i}`, distance, lane: 1, x: 0, height: 0 })
  }
  return {
    rows: rows.sort((a, b) => a.distance - b.distance),
    pickups: pickups.sort((a, b) => a.distance - b.distance),
    segments,
  }
}
