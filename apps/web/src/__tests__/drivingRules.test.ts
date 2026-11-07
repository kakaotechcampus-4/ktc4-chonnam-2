import { expect, it } from 'vitest'
import { SIGNAL_CYCLE, crossingPose, pedestrianAspect, signalAspect } from '../components/driving/rules'

it('교차하는 차량·보행자 및 보호 좌회전의 신호가 충돌하지 않는다', () => {
  for (const [x, z] of [[0, -96], [96, 0], [-96, -96]]) for (let t = 0; t < SIGNAL_CYCLE * 2; t += .25) {
    const ns = signalAspect(0, t, x, z), ew = signalAspect(1, t, x, z)
    expect(ns.straight && ew.straight).toBe(false)
    expect(ns.left && (ew.straight || ew.left)).toBe(false)
    expect(ew.left && ns.straight).toBe(false)
    for (const axis of [0, 1]) {
      const pedestrian = pedestrianAspect(axis, t, x, z)
      if (pedestrian.phase !== 'red') {
        expect(signalAspect(axis, t, x, z).straight).toBe(false)
        expect(ns.left || ew.left).toBe(false)
        expect(pedestrianAspect(1 - axis, t, x, z).phase).toBe('red')
      }
      for (const side of [-1, 1]) {
        const person = crossingPose(t, x, z, axis, side), previous = crossingPose(t - .001, x, z, axis, side)
        if (person.moving) expect(pedestrian.phase).not.toBe('red')
        if (previous.progress === 0 && person.progress > 0) expect(person.canStart).toBe(true)
      }
    }
  }
})
