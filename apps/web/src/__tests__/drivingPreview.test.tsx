// @vitest-environment jsdom
import { StrictMode } from 'react'
import { act, cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi, type MockInstance } from 'vitest'
import { DrivingPreview } from '../components/driving/DrivingPreview'
import * as engine from '../components/driving/createDrivingScene.js'

const dispose = vi.fn()
let mount: MockInstance<typeof engine.createDrivingScene>
beforeEach(() => { dispose.mockReset(); mount = vi.spyOn(engine, 'createDrivingScene').mockReturnValue(dispose) })
afterEach(() => { cleanup(); vi.restoreAllMocks() })
it('StrictMode와 부모 상태 갱신에서도 엔진은 한 번 만들고 화면을 나갈 때 해제한다', async () => {
  const r = render(<StrictMode><DrivingPreview /></StrictMode>)
  await waitFor(() => expect(r.container.querySelector('[data-status="ready"]')).not.toBeNull())
  expect(mount).toHaveBeenCalledTimes(1)
  r.rerender(<StrictMode><DrivingPreview /></StrictMode>)
  expect(mount).toHaveBeenCalledTimes(1)
  r.unmount(); expect(dispose).toHaveBeenCalledTimes(1)
})

it('지연 로딩 도중 분석이 끝나면 그래픽 엔진을 만들지 않는다', async () => {
  const r = render(<DrivingPreview />); r.unmount()
  await act(async () => {})
  expect(mount).not.toHaveBeenCalled()
})

it('WebGL 초기화 실패는 미리보기 안내로 처리하고 분석 화면을 깨뜨리지 않는다', async () => {
  mount.mockImplementation(() => { throw new Error('WebGL unavailable') })
  const r = render(<DrivingPreview />)
  await waitFor(() => expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy())
  expect(r.container.querySelector('.drive-controls')?.hasAttribute('hidden')).toBe(true)
})

it('그래픽 컨텍스트가 유실되면 조작을 숨기고 대체 안내를 표시한다', async () => {
  const r = render(<DrivingPreview />)
  await waitFor(() => expect(mount).toHaveBeenCalledTimes(1))
  act(() => mount.mock.calls[0][1]())
  expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy()
  expect(r.container.querySelector('.drive-controls')?.hasAttribute('hidden')).toBe(true)
})
