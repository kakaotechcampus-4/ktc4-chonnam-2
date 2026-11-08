// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createDrivingScene } from '../components/driving/createDrivingScene.js'
afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
function mount(sessionKey?: string) {
  const root = document.createElement('div')
  root.innerHTML = '<div class="media"></div>'
  document.body.append(root)
  const failed = vi.fn(),
    ready = vi.fn(),
    scene = createDrivingScene(root, failed, ready, sessionKey),
    frame = root.querySelector('iframe')!
  const api = { connect: vi.fn(), setActive: vi.fn(), dispose: vi.fn(), snapshot: vi.fn(), restore: vi.fn() }
  Object.defineProperty(frame.contentWindow, 'drivingGame', {
    value: api,
    configurable: true,
  })
  return { root, scene, frame, api, failed, ready }
}
it('restores the same case after candidate review and starts a new case fresh', () => {
  const first = mount('case-resume')
  first.frame.dispatchEvent(new Event('load'))
  const state = { level: 17, distance: 6800, phase: 'paused' }
  first.api.snapshot.mockReturnValue(state)
  first.scene.dispose()
  expect(first.api.dispose).toHaveBeenCalledOnce()
  const next = mount('case-resume')
  next.frame.dispatchEvent(new Event('load'))
  expect(next.api.restore).toHaveBeenCalledWith(state)
  next.scene.dispose()
  const other = mount('case-new')
  other.frame.dispatchEvent(new Event('load'))
  expect(other.api.restore).not.toHaveBeenCalled()
  other.scene.dispose()
})
it('keeps the game inactive when the user returns before its document loads', () => {
  const m = mount()
  expect(m.ready).not.toHaveBeenCalled()
  m.scene.setActive(false)
  m.frame.dispatchEvent(new Event('load'))
  expect(m.ready).toHaveBeenCalledOnce()
  expect(m.api.setActive).toHaveBeenLastCalledWith(false)
  m.scene.setActive(true)
  expect(m.api.setActive).toHaveBeenLastCalledWith(true)
  m.scene.dispose()
  m.scene.dispose()
  expect(m.api.dispose).toHaveBeenCalledOnce()
  expect(m.frame.isConnected).toBe(false)
})
it('does not initialize a late frame after analysis ends', () => {
  const m = mount()
  m.scene.dispose()
  m.frame.dispatchEvent(new Event('load'))
  expect(m.api.connect).not.toHaveBeenCalled()
  expect(m.ready).not.toHaveBeenCalled()
})
it('isolates loading and WebGL failures from analysis', () => {
  const m = mount()
  m.frame.dispatchEvent(new Event('load'))
  m.api.connect.mock.calls[0][0].onUnavailable()
  expect(m.failed).toHaveBeenCalledOnce()
  expect(m.api.setActive).toHaveBeenLastCalledWith(false)
  m.scene.setActive(true)
  expect(m.api.setActive).toHaveBeenLastCalledWith(false)
  m.scene.dispose()
  const bad = mount()
  Object.defineProperty(bad.frame.contentWindow, 'drivingGame', {
    value: { failed: true },
  })
  bad.frame.dispatchEvent(new Event('load'))
  expect(bad.failed).toHaveBeenCalledOnce()
  expect(bad.ready).not.toHaveBeenCalled()
  bad.scene.dispose()
})
it('suspends an offscreen game and disconnects its observer on removal', () => {
  let observeChange: (entries: { isIntersecting: boolean }[]) => void = () => {}
  const disconnect = vi.fn()
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(cb: typeof observeChange) {
        observeChange = cb
      }
      observe() {}
      disconnect = disconnect
    },
  )
  const m = mount()
  m.frame.dispatchEvent(new Event('load'))
  observeChange([{ isIntersecting: false }])
  expect(m.api.setActive).toHaveBeenLastCalledWith(false)
  observeChange([{ isIntersecting: true }])
  expect(m.api.setActive).toHaveBeenLastCalledWith(true)
  m.scene.dispose()
  expect(disconnect).toHaveBeenCalledOnce()
})
