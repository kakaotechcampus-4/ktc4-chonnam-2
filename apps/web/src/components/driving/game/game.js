import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css'
import './game.css'
import { createView } from './scene.js'
import {
  createRun,
  move,
  jump,
  setJumpHeld,
  advance,
  jumpPlan,
  COINS_PER_SHIELD,
  MAX_SHIELDS,
} from './rules.mjs'
import { gestureAction } from './gestures.mjs'
import { createSound } from './sound.mjs'
import { tutorialCue } from './guidance.mjs'
const $ = (id) => document.getElementById(id),
  reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
let view
try {
  view = createView($('view'))
} catch (e) {
  window.drivingGame = { failed: true }
  $('description').textContent =
    '3D 화면을 열지 못했어요. Chrome의 하드웨어 가속 설정을 확인해 주세요.'
  $('start').disabled = true
  throw e
}
let audioOn = true
try {
  audioOn = localStorage.getItem('drive-sound-v1') !== 'off'
} catch {}
const audio = createSound()
audio.setEnabled(audioOn)
let previousSeed = 17
function freshSeed() {
  const value = crypto.getRandomValues(new Uint32Array(1))[0]
  previousSeed = value === previousSeed ? (value + 1) >>> 0 : value
  return previousSeed
}
let run = createRun(freshSeed()),
  frame = 0,
  last = 0,
  lastPhase = '',
  lastEvent = '',
  disposed = false,
  helpOpen = false,
  pointer = null,
  pointerTimer = 0,
  signals = {}
let hostActive = window.parent === window,
  onUnavailable = () => {},
  onFullscreen = null
$('game').dataset.embedded = String(window.parent !== window)
const events = new AbortController(),
  listen = (t, e, h) => t.addEventListener(e, h, { signal: events.signal })
const jumpKeys = new Set()
function sound(kind) {
  const options = {
    direction: run.moveDirection,
    coinCharge: run.coinCharge,
  }
  audio.play(kind, options)
}
function syncFeedback() {
  for (const [field, kind] of [
    ['lastMove', 'move'],
    ['jumpAt', 'jump'],
    ['doubleAt', 'double'],
    ['boostAt', 'boost'],
    ['landingAt', 'land'],
    ['coinAt', 'coin'],
    ['shieldAt', 'shield'],
    ['shieldHitAt', 'shield-hit'],
  ]) {
    if (run[field] > (signals[field] ?? -100)) sound(kind)
    signals[field] = run[field]
  }
  if (run.combo > (signals.combo ?? 0) && run.combo % 5 === 0) sound('clear')
  if (run.level > (signals.level ?? 1)) sound('level')
  if (run.phase === 'over' && signals.phase !== 'over') sound('over')
  signals.combo = run.combo
  signals.level = run.level
  signals.phase = run.phase
}
function soundLabel() {
  $('sound').setAttribute('aria-pressed', String(audioOn))
  $('sound').setAttribute('aria-label', audioOn ? '소리 끄기' : '소리 켜기')
  $('sound').classList.toggle('muted', !audioOn)
}
function clearInput() {
  clearTimeout(pointerTimer)
  pointerTimer = 0
  const id = pointer?.id
  pointer = null
  jumpKeys.clear()
  if (id !== undefined && $('view').hasPointerCapture(id))
    $('view').releasePointerCapture(id)
  setJumpHeld(run, false)
  run.jumpBufferUntil = -100
}
function start() {
  if (disposed || !hostActive) return
  clearInput()
  helpOpen = false
  audio.unlock()
  if (run.phase === 'paused') run.phase = 'playing'
  else {
    if (run.phase !== 'ready') run = createRun(freshSeed())
    run.phase = 'playing'
    signals = {}
  }
  last = 0
  sound('start')
  draw()
  $('view').focus({ preventScroll: true })
  schedule()
}
function steer(d) {
  if (!hostActive) return false
  const moved = move(run, d)
  if (moved) draw()
  return moved
}
function lift() {
  if (!hostActive) return false
  const kind = jump(run)
  if (kind) draw()
  return kind
}

function pause() {
  clearInput()
  if (run.phase === 'playing') {
    run.phase = 'paused'
    cancelAnimationFrame(frame)
    frame = 0
    last = 0
    draw()
  } else if (run.phase === 'paused') start()
}
function draw() {
  view.draw(run, reduced, !!pointer && !pointer.launched && !pointer.handled)
  syncFeedback()
  $('game').dataset.phase = run.phase
  $('game').dataset.help = String(helpOpen)
  $('level-number').textContent = run.level
  $('speed').textContent = Math.round(run.speed * 3.6)
  $('distance').textContent = Math.floor(run.distance).toLocaleString()
  if (lastEvent !== run.lastEvent) {
    $('event').textContent = run.lastEvent
    lastEvent = run.lastEvent
  }
  $('event').style.opacity =
    run.phase === 'playing' && run.time < run.eventUntil ? 1 : 0
  const cue = tutorialCue(
    run,
    jumpPlan(run),
    matchMedia('(pointer: coarse)').matches,
  )
  $('warning').style.opacity = cue.text ? 1 : 0
  $('warning').textContent = cue.text
  $('warning').dataset.now = String(cue.now)
  $('hint').style.opacity = run.level === 1 ? 1 : 0
  const levelUp =
    run.phase === 'playing' && run.level > 1 && run.time - run.levelAt < 2.2
  $('game').dataset.levelup = String(levelUp)
  $('level-up').hidden = !levelUp
  const levelText = `LEVEL ${run.level}`
  if ($('new-level').textContent !== levelText)
    $('new-level').textContent = levelText
  const full = run.shields + run.shieldsUsed >= MAX_SHIELDS
  $('coin-count').textContent = full ? '완료' : run.coinCharge
  $('coin-target').hidden = full
  $('shield-count').textContent = run.shields
  $('rewards').dataset.active = String(run.shields > 0)
  $('rewards').setAttribute(
    'aria-label',
    `${full ? '이번 주행 보호막 획득 완료 · 추가 충전 없음' : `보호막까지 동전 ${run.coinCharge}/${COINS_PER_SHIELD}개`}, 보호막 ${run.shields}개 남음`,
  )
  $('coin-symbol').style.transform = reduced
    ? 'none'
    : `scale(${1 + Math.max(0, 1 - (run.time - run.coinAt) / 0.22) * 0.16})`
  $('shield-symbol').style.transform = reduced
    ? 'none'
    : `scale(${1 + Math.max(0, 1 - (run.time - run.shieldAt) / 0.4) * 0.18})`
  $('pause').disabled = run.phase === 'ready' || run.phase === 'over'
  $('pause').setAttribute(
    'aria-label',
    run.phase === 'paused' ? '계속하기' : '일시정지',
  )
  const key = `${run.phase}:${helpOpen}`
  if (lastPhase !== key) {
    if (helpOpen) {
      $('eyebrow').textContent = '드라이브'
      $('heading').textContent = '조작 방법'
      $('description').textContent = '점프 길이는 누르는 시간으로 조절해요.'
      $('start').textContent = run.phase === 'paused' ? '계속하기' : '시작하기'
      $('tip').textContent = '부스트는 최대 1.6초. 놓으면 먼저 내려와요.'
    } else if (run.phase === 'ready') {
      $('eyebrow').textContent = '기다리는 동안 가볍게'
      $('heading').textContent = '드라이브'
      $('description').textContent =
        '동전 10개마다 보호막 · 한 판에서 총 3회만 써요.'
      $('start').textContent = '시작하기'
      $('tip').textContent = '↑ · Space 또는 화면으로 점프해요.'
    } else if (run.phase === 'paused') {
      $('eyebrow').textContent = '드라이브'
      $('heading').textContent = '잠시 멈췄어요'
      $('description').textContent = '준비되면 같은 위치에서 이어서 달려요.'
      $('start').textContent = '계속하기'
      $('tip').textContent =
        run.level === 1 ? '↑ · Space 또는 P를 누르면 계속해요.' : ''
    } else if (run.phase === 'over') {
      $('eyebrow').textContent = '드라이브'
      $('heading').textContent = '이번 주행 기록'
      $('description').textContent = ''
      $('result-distance').textContent = Math.floor(
        run.distance,
      ).toLocaleString()
      $('result-level').textContent = run.level
      $('start').textContent = '다시 도전'
      $('tip').textContent = '충돌 직전에 멈췄어요. 다시 달려볼까요?'
      $('start').focus({ preventScroll: true })
    }
    lastPhase = key
  }
}
function step(seconds) {
  let t = seconds
  while (t > 1e-8) {
    const dt = Math.min(1 / 120, t)
    advance(run, dt)
    t -= dt
  }
}
function schedule() {
  if (
    !disposed &&
    hostActive &&
    !document.hidden &&
    !frame &&
    run.phase === 'playing'
  )
    frame = requestAnimationFrame(animate)
}
function animate(now) {
  frame = 0
  const dt = last ? Math.min(0.05, (now - last) / 1000) : 0
  last = now
  step(dt)
  draw()
  schedule()
}
function resize() {
  const r = $('game').getBoundingClientRect()
  if (!r.width || !r.height) return
  view.resize(r.width, r.height)
  draw()
}
listen($('start'), 'click', start)
listen($('pause'), 'click', pause)
listen($('help'), 'click', () => {
  helpOpen = true
  if (run.phase === 'playing') pause()
  else draw()
  $('start').focus({ preventScroll: true })
})
listen($('view'), 'pointerdown', (e) => {
  if (!hostActive || run.phase !== 'playing' || !e.isPrimary || e.button !== 0)
    return
  pointer = {
    id: e.pointerId,
    x: e.clientX,
    y: e.clientY,
    at: performance.now(),
    handled: false,
    launched: false,
  }
  $('view').setPointerCapture(e.pointerId)
  $('view').focus({ preventScroll: true })
  draw()
  pointerTimer = setTimeout(() => {
    if (pointer && !pointer.handled && run.phase === 'playing') {
      pointer.launched = true
      setJumpHeld(run, true)
      lift()
    }
  }, 65)
})
listen($('view'), 'pointermove', (e) => {
  if (!pointer || pointer.id !== e.pointerId || pointer.handled) return
  const dx = e.clientX - pointer.x,
    dy = e.clientY - pointer.y
  if (!pointer.launched && Math.hypot(dx, dy) > 8) clearTimeout(pointerTimer)
  if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx) * 1.25) {
    clearTimeout(pointerTimer)
    pointer.handled = true
    setJumpHeld(run, false)
    draw()
    return
  }
  const action = gestureAction(dx, dy, performance.now() - pointer.at)
  if (action === 'left' || action === 'right') {
    clearTimeout(pointerTimer)
    pointer.handled = true
    steer(action === 'left' ? -1 : 1)
  }
})
listen($('view'), 'pointerup', (e) => {
  if (!pointer || pointer.id !== e.pointerId) return
  clearTimeout(pointerTimer)
  const tap =
    !pointer.handled &&
    !pointer.launched &&
    gestureAction(
      e.clientX - pointer.x,
      e.clientY - pointer.y,
      performance.now() - pointer.at,
    ) === 'jump'
  pointer = null
  setJumpHeld(run, false)
  $('view').releasePointerCapture(e.pointerId)
  if (tap) lift()
  draw()
})
for (const name of ['pointercancel', 'lostpointercapture'])
  listen($('view'), name, () => {
    if (pointer) {
      clearInput()
      draw()
    }
  })
listen($('view'), 'contextmenu', (e) => e.preventDefault())
listen(window, 'keydown', (e) => {
  if (!hostActive || e.ctrlKey || e.metaKey || e.altKey) return
  if (e.code === 'ArrowUp' || e.code === 'Space') {
    if (e.code === 'Space' && e.target instanceof HTMLButtonElement) return
    e.preventDefault()
    if (e.repeat || jumpKeys.has(e.code)) return
    if (run.phase === 'playing') {
      const alreadyHeld = jumpKeys.size > 0
      jumpKeys.add(e.code)
      setJumpHeld(run, true)
      if (!alreadyHeld) lift()
    } else start()
  } else if (!e.repeat) {
    if (['ArrowLeft', 'KeyA', 'ArrowRight', 'KeyD'].includes(e.code)) {
      e.preventDefault()
      steer(['ArrowLeft', 'KeyA'].includes(e.code) ? -1 : 1)
    } else if (['KeyP', 'Escape'].includes(e.code)) {
      e.preventDefault()
      pause()
    }
  }
})
listen(window, 'keyup', (e) => {
  if (jumpKeys.delete(e.code)) {
    setJumpHeld(run, jumpKeys.size > 0)
    draw()
  }
})
listen($('sound'), 'click', () => {
  audioOn = !audioOn
  audio.setEnabled(audioOn)
  if (audioOn) {
    audio.unlock()
    audio.play('clear')
  }
  soundLabel()
  try {
    localStorage.setItem('drive-sound-v1', audioOn ? 'on' : 'off')
  } catch {}
})
listen($('fullscreen'), 'click', async () => {
  try {
    if (onFullscreen) {
      await onFullscreen()
      return
    }
    if (document.fullscreenElement) await document.exitFullscreen()
    else await $('game').requestFullscreen()
  } catch {}
})
listen(document, 'fullscreenchange', resize)
listen(window, 'resize', resize)
listen(window, 'blur', () => {
  if (run.phase === 'playing') pause()
  else clearInput()
})
listen(document, 'visibilitychange', () => {
  if (document.hidden && run.phase === 'playing') pause()
})
listen($('view'), 'webglcontextlost', (e) => {
  e.preventDefault()
  hostActive = false
  if (run.phase === 'playing') pause()
  onUnavailable()
  $('description').textContent =
    '화면 연결이 끊겼어요. 새로고침 후 다시 시작해 주세요.'
  $('start').disabled = true
})
function dispose() {
  if (disposed) return
  disposed = true
  clearInput()
  cancelAnimationFrame(frame)
  events.abort()
  view.dispose()
  audio.dispose()
}
window.drivingGame = {
  snapshot() {
    const state = structuredClone(run)
    if (state.phase === 'playing') state.phase = 'paused'
    state.jumpHeld = false
    state.boostActive = false
    state.jumpBufferUntil = -100
    return state
  },
  restore(state) {
    run = structuredClone(state)
    previousSeed = run.seed
    // Restoring progress must not replay old coin, shield, or level sounds.
    signals = { ...run }
    last = 0
    draw()
  },
  connect(callbacks) {
    onUnavailable = callbacks.onUnavailable
    onFullscreen = callbacks.onFullscreen
  },
  setActive(value) {
    if (disposed || hostActive === value) return
    hostActive = value
    clearInput()
    audio.setEnabled(value && audioOn)
    cancelAnimationFrame(frame)
    frame = 0
    last = 0
    if (value) {
      resize()
      schedule()
    }
  },
  dispose,
}
listen(window, 'pagehide', dispose)
soundLabel()
resize()
