const INTERVAL_MS = 1000 / 30

export function nextDrivingFrame(now: number, last: number, deadline: number) {
  if (!last) return { last: now, deadline: now + INTERVAL_MS, dt: 0 }
  if (now < deadline) return null
  // Preserve the fractional frame interval instead of losing it on every refresh.
  return { last: now, deadline: now + INTERVAL_MS - ((now - deadline) % INTERVAL_MS), dt: Math.min((now - last) / 1000, .08) }
}
