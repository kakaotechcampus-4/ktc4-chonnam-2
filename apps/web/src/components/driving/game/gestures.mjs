export function gestureAction(dx, dy, elapsed) {
  if (Math.abs(dx) >= 24 && Math.abs(dx) > Math.abs(dy) * 1.25)
    return dx < 0 ? 'left' : 'right'
  if (Math.hypot(dx, dy) <= 12 && elapsed <= 500) return 'jump'
  return null
}
