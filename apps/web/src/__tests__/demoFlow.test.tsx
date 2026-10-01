// @vitest-environment jsdom
//
// 시연 흐름: 진행 스냅샷만 자동으로 넘기고, 결과 화면에서 멈춘다.

import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { SNAPSHOTS } from '../contracts/fixtures'
import { CaseScreen } from '../screens/CaseScreen'
import { DemoFlow } from '../screens/DemoFlow'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

it('happy 시나리오는 결과 화면(2번째 스냅샷)에서 멈추고 3번째로 넘어가지 않는다', () => {
  vi.useFakeTimers()
  URL.createObjectURL = () => 'blob:x'
  URL.revokeObjectURL = () => {}
  const happy = SNAPSHOTS.filter((s) => s.scenarioId === 'scenario_happy_001')
  expect(happy).toHaveLength(3)

  const { container, getByText } = render(<DemoFlow />)
  fireEvent.change(container.querySelector('input[type=file]')!, {
    target: { files: [new File([''], 'a.mp4', { type: 'video/mp4' })] },
  })
  fireEvent.change(container.querySelector('textarea')!, { target: { value: '신호위반' } })
  fireEvent.click(getByText('분석 시작'))
  expect(container.textContent).toContain('진행 상태')

  act(() => vi.advanceTimersByTime(60_000))
  expect(container.textContent).not.toContain('준비하고 있어요')
  const at = (i: number) => render(<CaseScreen view={happy[i].view} />).container.textContent
  expect(at(1)).not.toBe(at(2))
  expect(container.querySelector('main')!.textContent).toBe('처음으로' + at(1))
})
