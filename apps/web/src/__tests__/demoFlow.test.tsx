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
    for (let i = 0; i < 20; i++) act(() => vi.advanceTimersByTime(5_000))
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
  // 위치는 아직 구현하지 않아 결과 화면에 없다
  expect(text()).not.toContain('발생 장소')
  fireEvent.click(getByText('어떻게 정했는지 →'))
  expect(text()).toContain('어떻게 정했는지')
  fireEvent.click(container.querySelector('.back')!)
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('번호판 판독 실패: 진행은 끝까지 흐르고 결과 화면에서 알리며 제출을 막는다', () => {
  const { wait, getByText, text } = start('fail')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('신고자료를 완성하지 못했어요')
  expect(text()).toContain('번호판 판독에 실패했습니다')
  expect((getByText('안전신문고로 이동') as HTMLButtonElement).disabled).toBe(true)
  // 번호판 다시 읽기 → 번호판부터 다시 진행해 정상 결과로 끝난다
  fireEvent.click(getByText('번호판 다시 읽기'))
  expect(text()).toContain('올리면 진행')
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('위반 미관찰: 후보 확인에서 멈추고 번호판 판독은 시작하지 않는다', () => {
  const { wait, getByText, text, container } = start('notObserved')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  const seen = new Set<string>()
  for (let i = 0; i < 20; i++) {
    container.querySelectorAll('.tl-running .tl-label, .tl-done .tl-label').forEach((el) => seen.add(el.textContent!))
    act(() => vi.advanceTimersByTime(5_000))
  }
  expect(seen.has('후보 확인')).toBe(true)
  expect(seen.has('번호판 판독')).toBe(false)
  expect(text()).toContain('위반을 확인하지 못했어요')
})

it('결과 없음: 아래에서 다시 적고 다시 찾으면 새로 진행한다', () => {
  const { wait, getByText, text, container } = start('notFound')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('조건에 맞는 장면을 찾지 못했습니다')
  const box = container.querySelector('textarea')!
  fireEvent.change(box, { target: { value: '' } })
  fireEvent.keyDown(box, { key: 'Tab' })
  expect(box.value).toContain('검은 승용차')
  fireEvent.click(getByText('다시 찾기'))
  expect(text()).toContain('올리면 진행')
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('다른 후보: 지금 기준 후보는 빼고 보여 주고, 고르면 다시 준비한다', () => {
  const { wait, getByText, text, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('다른 후보 영상 2 →'))
  expect(container.querySelectorAll('.cand')).toHaveLength(2)
  expect(text()).not.toContain('지금 신고자료 기준')
  fireEvent.click(container.querySelector('.cand-col button')!)
  expect(text()).toContain('올리면 진행')
})

it('업로드 실패: 다시 선택하면 다시 올린다', () => {
  const { wait, text } = start('uploadFail')
  wait()
  expect(text()).toContain('업로드 실패')
  expect(text()).toContain('다시 선택')
})

it('설명이 비어 있으면 Tab이 예시를 채우고, 「새 신고」는 처음 화면으로 돌아간다', () => {
  const { container, getByText, text, wait } = start('main')
  const box = container.querySelector('textarea')!
  fireEvent.keyDown(box, { key: 'Tab' })
  expect(box.value).toContain('흰색 SUV')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
  fireEvent.click(getByText('새 신고'))
  expect(text()).toContain('블랙박스 영상을 올려주세요')
  expect(container.querySelector('textarea')!.value).toBe('')
})

it('번호판 직접 입력은 결과 화면 차량 번호에 「사용자 확인됨」으로 반영된다', () => {
  const { wait, getByText, text, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('자세히 보기'))
  fireEvent.change(container.querySelector('.plate-form input')!, { target: { value: '34나5678' } })
  fireEvent.click(getByText('이 번호로 바꾸기'))
  expect(text()).toContain('신고자료가 준비됐어요')
  expect(text()).toContain('34나5678')
  expect(text()).toContain('사용자 확인됨')
})

it('위반 미관찰: 다른 후보를 버튼 없이 바로 펼쳐 둔다', () => {
  const { wait, getByText, container } = start('notObserved')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(container.querySelectorAll('.cand')).toHaveLength(2)
})
