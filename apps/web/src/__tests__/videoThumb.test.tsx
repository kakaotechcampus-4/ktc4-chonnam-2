// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { VideoThumb } from '../components/VideoThumb'

vi.mock('../components/driving/DrivingPreview', () => ({
  DrivingPreview: ({ active, onBack }: { active: boolean; onBack: () => void }) => (
    <div data-testid="waiting-drive" hidden={!active}>
      <button onClick={onBack}>미리보기로 돌아가기</button>
    </div>
  ),
}))
const { decodeAviFrame } = vi.hoisted(() => ({ decodeAviFrame: vi.fn() }))
vi.mock('../components/aviFrame', () => ({ decodeAviFrame }))
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
const invitation = /^기다리는 동안 게임을 해보시겠어요\?/

it('정상 미리보기에서도 게임을 선택할 수 있고 돌아오면 썸네일과 주행 상태를 유지한다', () => {
  const r = render(<VideoThumb file={file()} name="a.mp4" canDrive />)
  const entry = r.getByRole('button', { name: invitation })
  expect(entry.textContent).toBe('기다리는 동안 게임을 해보시겠어요?')
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  fireEvent.loadedMetadata(videos[0]); fireEvent.seeked(videos[0])
  const image = r.container.querySelector('img')
  expect(image?.getAttribute('src')).toBe('data:image/jpeg;base64,preview')
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  fireEvent.click(entry)
  const game = r.getByTestId('waiting-drive')
  expect(game.hidden).toBe(false)
  expect(r.queryByRole('button', { name: invitation })).toBeNull()
  fireEvent.click(r.getByRole('button', { name: '미리보기로 돌아가기' }))
  expect(game.hidden).toBe(true)
  expect(r.container.querySelector('img')).toBe(image)
  expect(document.activeElement).toBe(entry)
  expect(r.getByRole('button', { name: '주행 게임' })).toBe(entry)
  fireEvent.click(entry)
  expect(r.getByTestId('waiting-drive')).toBe(game)
  expect(game.hidden).toBe(false)
  expect(createUrl).toHaveBeenCalledOnce()
  expect(revokeUrl).toHaveBeenCalledOnce()
})

it.each(['error', 'timeout'] as const)('%s로 미리보기 실패가 확인돼도 게임을 자동으로 열지 않는다', reason => {
  const r = render(<VideoThumb file={file()} name="a.mp4" canDrive />)
  if (reason === 'error') fireEvent.error(videos[0])
  else {
    act(() => vi.advanceTimersByTime(3999))
    expect(r.queryByText('미리보기를 표시할 수 없어요')).toBeNull()
    act(() => vi.advanceTimersByTime(1))
  }
  expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy()
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  fireEvent.click(r.getByRole('button', { name: invitation }))
  expect(r.getByTestId('waiting-drive').hidden).toBe(false)
  expect(r.container.querySelector('figcaption')?.textContent).toContain('a.mp4')
  r.unmount(); expect(revokeUrl).toHaveBeenCalledOnce()
})

it('원본 없음·주소 생성 실패에서도 선택하기 전에는 미리보기 불가 안내만 표시한다', () => {
  const r = render(<VideoThumb file={null} name="a.avi" canDrive />)
  expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy()
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  createUrl.mockImplementation(() => { throw new Error('unavailable') })
  r.rerender(<VideoThumb file={file()} name="b.mp4" canDrive />)
  expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy()
  expect(r.queryByTestId('waiting-drive')).toBeNull()
})

it('게임 중 미리보기가 완성돼도 화면을 강제로 바꾸지 않는다', () => {
  const r = render(<VideoThumb file={file()} name="a.mp4" canDrive />)
  fireEvent.click(r.getByRole('button', { name: invitation }))
  fireEvent.loadedMetadata(videos[0]); fireEvent.seeked(videos[0])
  expect(r.getByTestId('waiting-drive').hidden).toBe(false)
  fireEvent.click(r.getByRole('button', { name: '미리보기로 돌아가기' }))
  expect(r.container.querySelector('img')).not.toBeNull()
})

it('파일 교체 시 이전 실패·늦은 이벤트를 새 파일에 적용하지 않는다', () => {
  const r = render(<VideoThumb file={file()} name="a.mp4" canDrive />)
  fireEvent.error(videos[0])
  r.rerender(<VideoThumb file={file('b.mp4')} name="b.mp4" canDrive />)
  expect(r.queryByText('미리보기를 표시할 수 없어요')).toBeNull()
  fireEvent.seeked(videos[0]); fireEvent.error(videos[0])
  expect(r.queryByText('미리보기를 표시할 수 없어요')).toBeNull()
  fireEvent.loadedMetadata(videos[1]); fireEvent.seeked(videos[1])
  expect(r.container.querySelector('img')).not.toBeNull()
  r.unmount(); expect(revokeUrl).toHaveBeenCalledTimes(2)
})

it('장면 찾기가 끝나면 게임을 해제하고 다시 시작해도 자동으로 열지 않는다', () => {
  const r = render(<VideoThumb file={null} name="a.avi" canDrive />)
  fireEvent.click(r.getByRole('button', { name: invitation }))
  r.rerender(<VideoThumb file={null} name="a.avi" canDrive={false} />)
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  expect(r.queryByRole('button', { name: '주행 게임' })).toBeNull()
  expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy()
  r.rerender(<VideoThumb file={null} name="a.avi" canDrive />)
  expect(r.queryByTestId('waiting-drive')).toBeNull()
  expect(r.getByRole('button', { name: invitation })).toBeTruthy()
})

it('AVI는 <video> 없이 첫 영상 조각을 디코드해 그리고, 못 꺼내면 대체 화면을 둔다(#595)', async () => {
  const close = vi.fn()
  decodeAviFrame.mockResolvedValueOnce({ image: {}, width: 1920, height: 1080, close })
  const avi = new File(['avi'], 'EVT_1.AVI', { type: '' })
  const r = render(<VideoThumb file={avi} name="EVT_1.AVI" />)
  await act(async () => {})
  expect(decodeAviFrame).toHaveBeenCalledWith(avi)
  expect(r.container.querySelector('img')?.getAttribute('src')).toBe('data:image/jpeg;base64,preview')
  expect(close).toHaveBeenCalledOnce()
  expect(videos).toHaveLength(0)
  decodeAviFrame.mockResolvedValueOnce(null)
  r.rerender(<VideoThumb file={new File(['x'], 'broken.avi')} name="broken.avi" />)
  await act(async () => {})
  expect(r.getByText('미리보기를 표시할 수 없어요')).toBeTruthy()
  expect(videos).toHaveLength(0)
})

it('준비 중 화면을 나가면 디코더·주소·실패 타이머를 해제한다', () => {
  const r = render(<VideoThumb file={file()} name="a.mp4" canDrive />)
  r.unmount(); act(() => vi.advanceTimersByTime(5000))
  expect(revokeUrl).toHaveBeenCalledOnce()
  expect(videos[0].getAttribute('src')).toBeNull()
  expect(vi.getTimerCount()).toBe(0)
})
