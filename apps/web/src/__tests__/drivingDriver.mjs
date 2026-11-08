// Input driver for verification and demonstration only; live play has no autopilot.
export function drive(s, course, move, jump, hold = () => {}) {
  if (s.phase !== 'playing') return
  if (s.distance < 28 && !s.airborne) {
    if (s.lane !== 1) move(Math.sign(1 - s.lane))
    return
  }
  const view = course(s.distance - 5, s.distance + 140),
    row = view.rows.find((r) => r.distance > s.distance - 4.8),
    age = s.time - s.jumpAt
  if (!row || row.distance - s.distance > 55) {
    const coin = view.pickups.find(
      (p) => p.distance > s.distance && p.height === 0,
    )
    if (
      coin &&
      coin.distance - s.distance < 40 &&
      coin.lane !== s.lane &&
      s.time - s.lastMove > 0.16
    )
      move(Math.sign(coin.lane - s.lane))
    if (s.airborne) hold(false)
    return
  }
  const gap = row.distance - s.distance,
    walls = row.cars.filter((c) => c.type === 'wall'),
    available = [0, 1, 2].filter((l) => !walls.some((c) => c.lane === l))
  let target = s.lane
  if (walls.length)
    target =
      row.kind === 'choice'
        ? row.cars.find((c) => c.type === 'truck').lane
        : available[0]
  else {
    const nextWall = view.rows.find(
      (r) =>
        r.distance > row.distance &&
        r.groupId === row.groupId &&
        r.cars.some((c) => c.type === 'wall'),
    )
    const coin = view.pickups.find(
      (p) => p.id.startsWith(row.groupId + 'p') && p.distance >= s.distance - 2,
    )
    if (nextWall && row.kind === 'low')
      target = [0, 1, 2].find(
        (l) => !nextWall.cars.some((c) => c.lane === l && c.type === 'wall'),
      )
    else if (coin) target = coin.lane
  }
  if (row.routeLane !== undefined) target = row.routeLane
  if (target !== s.lane && gap > 7 && s.time - s.lastMove > 0.16)
    move(Math.sign(target - s.lane))
  const car = row.cars.find((c) => c.lane === s.lane && c.type !== 'gate')
  if (s.airborne) {
    if (car?.type === 'truck' && s.jumpCount === 1 && age >= 0.14 && age <= 0.3)
      jump()
    if (s.jumpHeld && (row.kind !== 'queue' || gap > 25)) hold(false)
    return
  }
  if (
    car &&
    car.type !== 'wall' &&
    gap < s.speed * (car.type === 'truck' ? 0.64 : 0.43) &&
    gap > 0
  ) {
    hold(row.kind === 'queue')
    jump()
  }
}
