import { LANES, clamp } from './rules.mjs'
export function motion(s, reduced = false, pressed = false) {
  const land = s.time - s.landingAt
  const suspension =
    land >= 0 && land < 0.3
      ? Math.sin(land * 32) * Math.exp(-land * 13) * 0.085 * s.landingStrength
      : 0
  const p = s.airborne && s.rollAt >= s.jumpAt ? s.rollProgress : 0,
    turn = p * p * p * (10 - 15 * p + 6 * p * p)
  return {
    pitch: reduced ? 0 : s.airborne ? -clamp(s.vy * 0.012, -0.075, 0.12) : 0,
    yaw: reduced ? 0 : -(LANES[s.lane] - s.x) * 0.033,
    roll: reduced ? 0 : -(LANES[s.lane] - s.x) * 0.022,
    stuntRoll: reduced ? 0 : -Math.PI * 2 * turn,
    dip: reduced ? 0 : suspension + (pressed && !s.airborne ? 0.025 : 0),
    boost: s.boostActive,
  }
}
