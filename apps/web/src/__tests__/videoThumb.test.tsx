// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { VideoThumb } from '../components/VideoThumb'

const videos: HTMLVideoElement[] = []
const createUrl = vi.fn(), revokeUrl = vi.fn()
beforeEach(() => {
  vi.useFakeTimers()
  videos.length = 0
  createUrl.mockReset().mockImplementation(() => `blob:video-${videos.length}`)
  revokeUrl.mockReset()
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createUrl; static revokeObjectURL = revokeUrl })
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {})
  const create = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((...args) => {
    const element = create(...args)
    if (args[0] === 'video') {
      const video = element as HTMLVideoElement
      Object.defineProperties(video, { videoWidth: { value: 1920 }, videoHeight: { value: 1080 }, duration: { value: 30 } })
      videos.push(video)
    }
    return element
  })
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage: vi.fn() } as unknown as CanvasRenderingContext2D)
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/jpeg;base64,preview')
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })
const file = (name = 'a.mp4') => new File(['video'], name, { type: 'video/mp4' })
const fallback = <div data-testid="waiting-drive">주행 화면</div>

it('준비 중과 정상 미리보기에는 주행 화면을 표시하지 않는다', () => {
  const r = render(<VideoThumb file={file()} name="a.mp4" unavailableFallback={fallback} />)
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  fireEvent.loadedMetadata(videos[0]); fireEvent.seeked(videos[0])
  expect(r.container.querySelector('img')?.getAttribute('src')).toBe('data:image/jpeg;base64,preview')
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  act(() => vi.advanceTimersByTime(5000))
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  expect(revokeUrl).toHaveBeenCalledTimes(1)
})

it.each(['error', 'timeout'] as const)('%s로 미리보기 실패가 확인됐을 때만 대체 화면을 표시한다', reason => {
  const r = render(<VideoThumb file={file()} name="a.mp4" unavailableFallback={fallback} />)
  if (reason === 'error') fireEvent.error(videos[0])
  else { act(() => vi.advanceTimersByTime(3999)); expect(r.queryByTestId('waiting-drive')).toBeNull(); act(() => vi.advanceTimersByTime(1)) }
  expect(r.queryByTestId('waiting-drive')).not.toBeNull()
  expect(r.container.querySelector('figcaption')?.textContent).toContain('a.mp4')
  r.unmount(); expect(revokeUrl).toHaveBeenCalledTimes(1)
})

it('원본이 없거나 임시 주소를 만들 수 없으면 대체 화면을 사용한다', () => {
  const r = render(<VideoThumb file={null} name="a.avi" unavailableFallback={fallback} />)
  expect(r.queryByTestId('waiting-drive')).not.toBeNull()
  createUrl.mockImplementation(() => { throw new Error('unavailable') })
  r.rerender(<VideoThumb file={file()} name="b.mp4" unavailableFallback={fallback} />)
  expect(r.queryByTestId('waiting-drive')).not.toBeNull()
})

it('파일 교체 시 이전 실패·늦은 이벤트를 새 파일에 적용하지 않는다', () => {
  const r = render(<VideoThumb file={file()} name="a.mp4" unavailableFallback={fallback} />)
  fireEvent.error(videos[0]); expect(r.queryByTestId('waiting-drive')).not.toBeNull()
  r.rerender(<VideoThumb file={file('b.mp4')} name="b.mp4" unavailableFallback={fallback} />)
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  fireEvent.seeked(videos[0]); fireEvent.error(videos[0])
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  fireEvent.loadedMetadata(videos[1]); fireEvent.seeked(videos[1])
  expect(r.container.querySelector('img')).not.toBeNull()
  r.unmount(); expect(revokeUrl).toHaveBeenCalledTimes(2)
})

it('분석 단계가 바뀌어 대체 화면을 제거하면 기존 미리보기 불가 안내로 돌아간다', () => {
  const r = render(<VideoThumb file={null} name="a.avi" unavailableFallback={fallback} />)
  r.rerender(<VideoThumb file={null} name="a.avi" />)
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy()
})

it('준비 중 화면을 나가면 디코더·주소·실패 타이머를 해제한다', () => {
  const r = render(<VideoThumb file={file()} name="a.mp4" unavailableFallback={fallback} />)
  r.unmount(); act(() => vi.advanceTimersByTime(5000))
  expect(revokeUrl).toHaveBeenCalledTimes(1)
  expect(videos[0].getAttribute('src')).toBeNull()
  expect(vi.getTimerCount()).toBe(0)
})
