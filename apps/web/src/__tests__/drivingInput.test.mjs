// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import html from '../../driving-game.html?raw'

const { view, audio } = vi.hoisted(() => ({
  view: { draw: vi.fn(), resize: vi.fn(), dispose: vi.fn() },
  audio: {
    unlock: vi.fn(),
    setEnabled: vi.fn(),
    play: vi.fn(),
    dispose: vi.fn(),
  },
}))
vi.mock('../components/driving/game/scene.js', () => ({
  createView: () => view,
}))
vi.mock('../components/driving/game/sound.mjs', () => ({
  createSound: () => audio,
}))

beforeEach(async () => {
  vi.resetModules()
  vi.clearAllMocks()
  document.body.innerHTML = html.slice(
    html.indexOf('<body>') + 6,
    html.indexOf('</body>'),
  )
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
  vi.stubGlobal(
    'requestAnimationFrame',
    vi.fn(() => 1),
  )
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
  await import('../components/driving/game/game.js')
})
afterEach(() => {
  window.drivingGame.dispose()
  delete window.drivingGame
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})
const key = (type, code) =>
  window.dispatchEvent(new KeyboardEvent(type, { code }))
const state = () => view.draw.mock.calls.at(-1)[0]

it('ignores jump and steering while the host hides the game', () => {
  window.drivingGame.setActive(false)
  key('keydown', 'ArrowUp')
  expect(document.getElementById('game').dataset.phase).toBe('ready')
  window.drivingGame.setActive(true)
  document.getElementById('start').click()
  key('keydown', 'ArrowUp')
  expect(state().jumpHeld).toBe(true)
  const lane = state().lane
  window.drivingGame.setActive(false)
  key('keyup', 'ArrowUp')
  key('keydown', 'ArrowUp')
  key('keydown', 'ArrowLeft')
  expect(state().jumpHeld).toBe(false)
  expect(state().jumpCount).toBe(1)
  expect(state().lane).toBe(lane)
})

it('keeps a held jump when the host repeats an active notification', () => {
  document.getElementById('start').click()
  key('keydown', 'ArrowUp')
  window.drivingGame.setActive(true)
  expect(state().jumpHeld).toBe(true)
  key('keyup', 'ArrowUp')
  expect(state().jumpHeld).toBe(false)
})

it('releases input, audio and graphics once when the game is removed', () => {
  document.getElementById('start').click()
  window.drivingGame.dispose()
  window.drivingGame.dispose()
  view.draw.mockClear()
  key('keydown', 'ArrowUp')
  document.getElementById('start').click()
  expect(view.draw).not.toHaveBeenCalled()
  expect(view.dispose).toHaveBeenCalledOnce()
  expect(audio.dispose).toHaveBeenCalledOnce()
  expect(window.hopGame).toBeUndefined()
})
