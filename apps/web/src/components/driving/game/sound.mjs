const noiseBuffers = new WeakMap()
export function scheduleSound(
  ctx,
  out,
  kind,
  { at = ctx.currentTime, direction = 0, coinCharge = 0 } = {},
) {
  const created = []
  const note = (hz, duration, volume, end = hz, delay = 0, type = 'sine') => {
    const o = ctx.createOscillator(),
      g = ctx.createGain()
    o.type = type
    o.frequency.setValueAtTime(hz, at + delay)
    o.frequency.exponentialRampToValueAtTime(
      Math.max(20, end),
      at + delay + duration,
    )
    g.gain.setValueAtTime(0.0001, at + delay)
    g.gain.exponentialRampToValueAtTime(volume, at + delay + 0.006)
    g.gain.exponentialRampToValueAtTime(0.0001, at + delay + duration)
    o.connect(g).connect(out)
    o.onended = () => {
      o.disconnect()
      g.disconnect()
    }
    o.start(at + delay)
    o.stop(at + delay + duration + 0.01)
    created.push(o)
  }
  const noise = (duration, volume, frequency, pan = 0) => {
    let buffer = noiseBuffers.get(ctx)
    if (!buffer) {
      buffer = ctx.createBuffer(1, ctx.sampleRate * 0.4, ctx.sampleRate)
      const data = buffer.getChannelData(0)
      let seed = 12345
      for (let i = 0; i < data.length; i++) {
        seed = (Math.imul(seed, 1664525) + 1013904223) | 0
        data[i] = (seed >>> 0) / 2147483648 - 1
      }
      noiseBuffers.set(ctx, buffer)
    }
    const o = ctx.createBufferSource(),
      f = ctx.createBiquadFilter(),
      g = ctx.createGain(),
      p = ctx.createStereoPanner()
    o.buffer = buffer
    f.type = 'lowpass'
    f.frequency.setValueAtTime(frequency, at)
    f.frequency.exponentialRampToValueAtTime(
      Math.max(80, frequency * 0.3),
      at + duration,
    )
    g.gain.setValueAtTime(0.0001, at)
    g.gain.exponentialRampToValueAtTime(volume, at + 0.006)
    g.gain.exponentialRampToValueAtTime(0.0001, at + duration)
    p.pan.value = pan
    o.connect(f).connect(g).connect(p).connect(out)
    o.onended = () => {
      o.disconnect()
      f.disconnect()
      g.disconnect()
      p.disconnect()
    }
    o.start(at)
    o.stop(at + duration + 0.01)
    created.push(o)
  }
  if (kind === 'move') {
    noise(0.065, 0.08, 1500, direction * 0.55)
    note(180, 0.035, 0.035, 130)
  }
  if (kind === 'jump') {
    note(120, 0.1, 0.12, 200, 0, 'sine')
    noise(0.12, 0.11, 2100)
  }
  if (kind === 'double') {
    note(180, 0.12, 0.1, 300)
    noise(0.16, 0.14, 3300)
  }
  if (kind === 'boost') {
    noise(0.32, 0.16, 2500)
    note(100, 0.25, 0.055, 155)
  }
  if (kind === 'land') {
    note(85, 0.11, 0.18, 43)
    noise(0.08, 0.12, 550)
  }
  if (kind === 'coin') {
    const hz = 660 + coinCharge * 65
    note(hz, 0.105, 0.072, hz * 1.12)
    note(hz * 2, 0.075, 0.022, hz * 2, 0.025)
  }
  if (kind === 'shield') {
    ;[523.25, 659.25, 783.99].forEach((hz, i) =>
      note(hz, 0.24, 0.085, hz, i * 0.055),
    )
  }
  if (kind === 'shield-hit') {
    note(250, 0.18, 0.12, 120)
    note(620, 0.18, 0.06, 310)
    noise(0.16, 0.12, 1800)
  }
  if (kind === 'clear') {
    note(523.25, 0.12, 0.065)
    note(659.25, 0.15, 0.045, 659.25, 0.045)
  }
  if (kind === 'level') {
    ;[392, 523.25, 783.99].forEach((hz, i) =>
      note(hz, 0.32, 0.12, hz, i * 0.09),
    )
  }
  if (kind === 'start') {
    note(330, 0.11, 0.085, 440)
    note(660, 0.15, 0.07, 660, 0.06)
  }
  if (kind === 'over') {
    note(180, 0.22, 0.09, 85)
    noise(0.1, 0.07, 400)
  }
  return created
}
export function createSound() {
  let ctx,
    master,
    enabled = true
  function unlock() {
    try {
      if (!ctx) {
        ctx = new AudioContext()
        master = ctx.createGain()
        master.gain.value = enabled ? 0.65 : 0
        master.connect(ctx.destination)
      }
      if (ctx.state === 'suspended') ctx.resume()
    } catch {}
  }
  return {
    unlock,
    setEnabled(value) {
      enabled = value
      if (master)
        master.gain.setTargetAtTime(enabled ? 0.65 : 0, ctx.currentTime, 0.015)
    },
    play(kind, options) {
      if (enabled && ctx?.state === 'running')
        scheduleSound(ctx, master, kind, options)
    },
    state() {
      return { enabled, state: ctx?.state ?? 'locked' }
    },
    dispose() {
      ctx?.close()
    },
  }
}
