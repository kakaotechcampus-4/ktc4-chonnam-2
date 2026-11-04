import { useEffect, useState } from 'react'

// 결과 화면 위에 여는 하위 화면 목록(다른 후보 · 번호판 · 시각 · 근거 · 설명 고치기).
// 하위 화면마다 브라우저 기록에 한 칸을 남겨, 브라우저 뒤로가기도 화면 안 「뒤로」처럼 하나씩 닫는다.
// 기록 칸의 깊이(history.state.sub)가 기준이고, 목록은 그 깊이만큼만 남긴다.
const depth = () => (history.state as { sub?: number } | null)?.sub ?? 0

export function useSubStack<S>() {
  const [subs, setSubs] = useState<S[]>([])
  useEffect(() => {
    // 하위 화면을 연 채 새로고침하면 목록은 비는데 깊이는 남는다 — 이 칸을 바닥(0)으로 맞춘다
    if (depth() > 0) history.replaceState({ ...history.state, sub: 0 }, '')
    const onPop = () => setSubs((s) => (s.length > depth() ? s.slice(0, depth()) : s))
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const open = (sub: S) => {
    history.pushState({ ...history.state, sub: subs.length + 1 }, '', location.href)
    setSubs((s) => [...s, sub])
  }
  // 기록 칸이 있을 때만 기록을 되돌린다 — 없는데 되돌리면 대신고 밖으로 나간다
  const back = () => {
    setSubs((s) => s.slice(0, -1))
    if (depth() > 0) history.back()
  }
  const closeAll = () => {
    setSubs([])
    if (depth() > 0) history.go(-depth())
  }
  return { subs, open, back, closeAll }
}
