// Keep only the latest case's run in memory while releasing its graphics on navigation.
let savedSession = null

// Keep game styles and input inside its document; the host owns visibility and cleanup.
export function createDrivingScene(root, onUnavailable, onReady = () => {}, sessionKey) {
  if (sessionKey && savedSession?.key !== sessionKey)
    savedSession = { key: sessionKey, state: null }
  const session = sessionKey ? savedSession : null
  const media = root.querySelector('.media'),
    frame = document.createElement('iframe'),
    events = new AbortController()
  let game = null,
    active = true,
    visible = true,
    disposed = false,
    failed = false
  frame.title = '드라이브 게임'
  frame.name = 'drive-game'
  frame.allow = 'fullscreen'
  frame.className = 'drive-frame'
  const sync = () => game?.setActive(active && visible && !failed)
  const unavailable = () => {
    if (disposed || failed) return
    failed = true
    sync()
    onUnavailable()
  }
  frame.addEventListener(
    'load',
    () => {
      if (disposed) return
      const api = frame.contentWindow?.drivingGame
      if (!api?.connect || api.failed) return unavailable()
      game = api
      game.connect({
        onUnavailable: unavailable,
        onFullscreen: async () => {
          if (disposed || !active) return
          if (document.fullscreenElement) await document.exitFullscreen()
          else await media.requestFullscreen()
        },
      })
      if (session?.state) game.restore(session.state)
      sync()
      onReady()
    },
    { signal: events.signal },
  )
  frame.addEventListener('error', unavailable, { signal: events.signal })
  const observer =
    typeof IntersectionObserver === 'undefined'
      ? null
      : new IntersectionObserver((entries) => {
          visible = entries[0]?.isIntersecting ?? false
          sync()
        })
  frame.src = import.meta.env.BASE_URL + 'driving-game.html'
  media.prepend(frame)
  observer?.observe(root)
  return {
    setActive(value) {
      if (disposed) return
      active = value
      sync()
    },
    dispose() {
      if (disposed) return
      disposed = true
      events.abort()
      observer?.disconnect()
      if (session && game) session.state = game.snapshot()
      game?.dispose()
      game = null
      if (
        document.fullscreenElement &&
        root.contains(document.fullscreenElement)
      )
        document.exitFullscreen().catch(() => {})
      frame.remove()
    },
  }
}
