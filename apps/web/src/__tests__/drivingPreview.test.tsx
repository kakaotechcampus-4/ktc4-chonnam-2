// @vitest-environment jsdom
import { StrictMode } from 'react'
import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi, type MockInstance } from 'vitest'
import { DrivingPreview } from '../components/driving/DrivingPreview'
import * as engine from '../components/driving/createDrivingScene.js'

const dispose = vi.fn()
const setActive = vi.fn(), onBack = vi.fn()
let mount: MockInstance<typeof engine.createDrivingScene>
beforeEach(() => { dispose.mockReset(); setActive.mockReset(); onBack.mockReset(); mount = vi.spyOn(engine, 'createDrivingScene').mockReturnValue({ dispose, setActive }) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
it('StrictMode와 부모 상태 갱신에서도 엔진은 한 번 만들고 화면을 나갈 때 해제한다', async () => {
  const r = render(<StrictMode><DrivingPreview active onBack={onBack} /></StrictMode>)
  await waitFor(() => expect(r.container.querySelector('[data-status="ready"]')).not.toBeNull())
  expect(mount).toHaveBeenCalledTimes(1)
  r.rerender(<StrictMode><DrivingPreview active onBack={onBack} /></StrictMode>)
  expect(mount).toHaveBeenCalledTimes(1)
  r.unmount(); expect(dispose).toHaveBeenCalledTimes(1)
})

it('지연 로딩 도중 분석이 끝나면 그래픽 엔진을 만들지 않는다', async () => {
  const r = render(<DrivingPreview active onBack={onBack} />); r.unmount()
  await act(async () => {})
  expect(mount).not.toHaveBeenCalled()
})

it('WebGL 초기화 실패는 미리보기 안내로 처리하고 분석 화면을 깨뜨리지 않는다', async () => {
  mount.mockImplementation(() => { throw new Error('WebGL unavailable') })
  const r = render(<DrivingPreview active onBack={onBack} />)
  await waitFor(() => expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy())
  expect(r.container.querySelector('.drive-controls')?.hasAttribute('hidden')).toBe(true)
  fireEvent.click(r.getByRole('button', { name: '미리보기로 돌아가기' }))
  expect(onBack).toHaveBeenCalledOnce()
})

it('그래픽 컨텍스트가 유실되면 조작을 숨기고 대체 안내를 표시한다', async () => {
  const r = render(<DrivingPreview active onBack={onBack} />)
  await waitFor(() => expect(mount).toHaveBeenCalledTimes(1))
  act(() => mount.mock.calls[0][1]())
  expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy()
  expect(r.container.querySelector('.drive-controls')?.hasAttribute('hidden')).toBe(true)
})

it('미리보기로 전환하면 엔진을 멈추고 다시 열 때 같은 엔진을 재개한다', async () => {
  const r = render(<DrivingPreview active onBack={onBack} />)
  await waitFor(() => expect(setActive).toHaveBeenLastCalledWith(true))
  const canvas = r.container.querySelector('canvas')
  r.rerender(<DrivingPreview active={false} onBack={onBack} />)
  expect(setActive).toHaveBeenLastCalledWith(false)
  expect(r.queryByRole('button', { name: '미리보기로 돌아가기' })).toBeNull()
  expect(dispose).not.toHaveBeenCalled()
  r.rerender(<DrivingPreview active onBack={onBack} />)
  expect(setActive).toHaveBeenLastCalledWith(true)
  expect(mount).toHaveBeenCalledOnce()
  expect(r.container.querySelector('canvas')).toBe(canvas)
  expect(document.activeElement).toBe(r.getByRole('button', { name: '미리보기로 돌아가기' }))
})

it('지연 로딩 중 돌아가도 엔진이 뒤에서 주행을 시작하지 않는다', async () => {
  const r = render(<DrivingPreview active onBack={onBack} />)
  r.rerender(<DrivingPreview active={false} onBack={onBack} />)
  await waitFor(() => expect(mount).toHaveBeenCalledOnce())
  expect(setActive).toHaveBeenLastCalledWith(false)
})

it('크게 보기에서 돌아가면 전체 화면을 먼저 종료한다', async () => {
  const r = render(<DrivingPreview active onBack={onBack} />)
  const exit = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(document, 'fullscreenElement', { configurable: true, get: () => r.container.querySelector('.media') })
  Object.defineProperty(document, 'exitFullscreen', { configurable: true, value: exit })
  try {
    fireEvent.click(r.getByRole('button', { name: '미리보기로 돌아가기' }))
    expect(exit).toHaveBeenCalledOnce()
    expect(onBack).not.toHaveBeenCalled()
    await waitFor(() => expect(onBack).toHaveBeenCalledOnce())
  } finally {
    Reflect.deleteProperty(document, 'fullscreenElement')
    Reflect.deleteProperty(document, 'exitFullscreen')
  }
})
