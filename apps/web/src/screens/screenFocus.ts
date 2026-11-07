import { useEffect, useRef, type RefObject } from 'react'

// 화면 전환 초점(#509 #2). 화면이 바뀌면 누른 버튼이 사라지면서 초점이 body로 떨어져
// 화면 낭독기가 아무것도 알리지 않는다. 그래서
// - 새 화면이 열리면 그 화면 제목(h1)에 초점을 준다.
// - 하위 화면에서 뒤로 오면 그 화면을 연 버튼(같은 글자 · 같은 class)으로 돌려준다.
// 하위 화면(SubPage)과 진행 화면(FlowScreen)은 열릴 때 스스로 초점을 잡으므로, 초점이 이미
// 화면 안에 있으면 건드리지 않는다. 첫 화면은 페이지가 열린 것이라 옮기지 않는다.
// 반환하는 함수는 하위 화면을 열기 직전에 불러 연 버튼을 기억한다.
export function useScreenFocus(main: RefObject<HTMLElement | null>, screenKey: string, depth: number): () => void {
  const openers = useRef<{ text: string; cls: string }[]>([])
  const prev = useRef({ screenKey, depth })
  useEffect(() => {
    const was = prev.current
    prev.current = { screenKey, depth }
    const root = main.current
    if (was.screenKey === screenKey || !root) return
    const opener = depth < was.depth ? openers.current.splice(depth)[0] : undefined
    const active = document.activeElement
    if (active && active !== document.body && root.contains(active)) return
    const visible = (el: Element) => !el.closest('[inert], [aria-hidden="true"]')
    const back = opener && [...root.querySelectorAll('button')].find((b) => visible(b) && b.textContent === opener.text && b.className === opener.cls)
    const target = back ?? [...root.querySelectorAll<HTMLElement>('h1')].find(visible)
    if (!target) return
    if (target.tagName === 'H1' && !target.hasAttribute('tabindex')) target.tabIndex = -1
    target.focus({ preventScroll: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 화면이 바뀔 때만
  }, [screenKey, depth])
  return () => {
    const a = document.activeElement
    openers.current.push(a instanceof HTMLElement ? { text: a.textContent ?? '', cls: a.className } : { text: '', cls: '' })
  }
}
