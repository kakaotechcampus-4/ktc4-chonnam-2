export function tutorialCue(s, plan, touch = false) {
  if (
    s.level !== 1 ||
    s.phase !== 'playing' ||
    !plan.row ||
    plan.gap < 0 ||
    plan.gap > s.speed * 1.7
  )
    return { text: '', now: false }
  const key = touch ? '탭' : '↑',
    type = plan.car?.type,
    kind = plan.row.kind
  if (type === 'wall')
    return {
      text: touch ? '열린 차선으로 밀기' : '← → 열린 차선으로 이동',
      now: false,
    }
  if (kind === 'low' || kind === 'landing')
    return { text: '그대로 통과 · 두 번 눌러 넘기', now: false }
  const high = type === 'truck',
    long = kind === 'queue'
  if (s.airborne) {
    if (high && s.jumpCount === 1 && s.time - s.jumpAt <= 0.3)
      return { text: touch ? '한 번 더 탭' : '↑ 한 번 더', now: true }
    return {
      text: long && s.jumpHeld ? '계속 누르기 · 놓으면 하강' : '',
      now: false,
    }
  }
  const lead = high ? 0.64 : 0.43,
    ttc = plan.gap / s.speed,
    now = ttc <= lead + 0.18 && ttc >= lead - 0.06
  const action = high
    ? `${key} 빠르게 두 번`
    : long
      ? touch
        ? '길게 누르기'
        : '↑ 누르고 있기'
      : `${key} 짧게 한 번`
  return { text: `${now ? '지금' : '준비'} · ${action}`, now }
}
