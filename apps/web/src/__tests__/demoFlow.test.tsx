// @vitest-environment jsdom
//
// 시연 흐름: Figma Memo의 키 규칙(d 진행 · a 실패 · w 재시도 · s 뒤로)대로 넘어간다.

import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { DemoFlow } from '../screens/DemoFlow'

afterEach(cleanup)

const press = (key: string) => fireEvent.keyDown(window, { key })

it('업로드 → 진행 → 결과, a는 실패 화면, s는 한 칸 뒤로', () => {
  const { container, getByText } = render(<DemoFlow />)
  const text = () => container.querySelector('main')!.textContent!

  fireEvent.change(container.querySelector('input[type=file]')!, {
    target: { files: [new File([''], 'a.mp4', { type: 'video/mp4' })] },
  })
  expect(text()).toContain('올리는 중')
  press('d')
  expect(text()).toContain('올리기 완료')

  fireEvent.click(getByText('영상에서 찾아보기'))
  expect(text()).toContain('올리면 진행')

  press('a')
  expect(container.querySelector('.tl-failed')).not.toBeNull()
  press('s')
  press('w')
  expect(container.querySelector('.tl-running')).not.toBeNull()
  press('s')

  press('d')
  expect(text()).toContain('신고자료가 준비됐어요')
  fireEvent.click(getByText('어떻게 정했는지 확인 →'))
  expect(text()).toContain('어떻게 정했는지')
  press('s')
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('입력칸에 글을 쓰는 중에는 키로 화면이 넘어가지 않는다', () => {
  const { container } = render(<DemoFlow />)
  fireEvent.change(container.querySelector('input[type=file]')!, {
    target: { files: [new File([''], 'a.mp4', { type: 'video/mp4' })] },
  })
  fireEvent.keyDown(container.querySelector('textarea')!, { key: 'd' })
  expect(container.textContent).toContain('올리는 중')
})
