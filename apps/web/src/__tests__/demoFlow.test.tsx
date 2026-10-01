// @vitest-environment jsdom
//
// 시연 흐름: 파일 선택·버튼과 작업 상태 변화로만 화면이 넘어간다.

import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DemoFlow } from '../screens/DemoFlow'

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function start(caseKey: string) {
  const r = render(<DemoFlow />)
  fireEvent.change(r.container.querySelector('select')!, { target: { value: caseKey } })
  fireEvent.change(r.container.querySelector('input[type=file]')!, {
    target: { files: [new File([''], 'a.mp4', { type: 'video/mp4' })] },
  })
  const text = () => r.container.querySelector('main')!.textContent!
  // 다음 타이머는 렌더 뒤 effect가 건다 — 한 번에 한 단계씩 흘린다.
  const wait = () => {
    for (let i = 0; i < 5; i++) act(() => vi.advanceTimersByTime(5_000))
  }
  return { ...r, text, wait }
}

it('정상: 업로드 완료 → 진행 → 결과, 하위 화면은 「<」로 돌아온다', () => {
  const { text, wait, getByText, container } = start('main')
  expect(text()).toContain('올리는 중')
  wait()
  expect(text()).toContain('올리기 완료')
  fireEvent.click(getByText('영상에서 찾아보기'))
  expect(text()).toContain('올리면 진행')
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
  fireEvent.click(getByText('어떻게 정했는지 확인 →'))
  expect(text()).toContain('어떻게 정했는지')
  fireEvent.click(container.querySelector('.back')!)
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('번호판 판독 실패: 진행 화면에서 실패 단계로 멈춘다', () => {
  const { wait, getByText, container, text } = start('fail')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('올리면 진행')
  expect(container.querySelector('.tl-failed')).not.toBeNull()
})

it('업로드 실패: 다시 선택하면 다시 올린다', () => {
  const { wait, text } = start('uploadFail')
  wait()
  expect(text()).toContain('업로드 실패')
  expect(text()).toContain('다시 선택')
})
