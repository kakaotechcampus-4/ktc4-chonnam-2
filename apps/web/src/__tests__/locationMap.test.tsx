// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LocationMap, MAP_GPS_NOTE, MAP_ME_FAILED, MAP_ME_NOTE } from '../components/LocationMap'
import { loadKakaoMaps } from '../components/kakaoMap'

vi.mock('../components/kakaoMap', () => ({
  kakaoMapKey: vi.fn(() => 'test-key'),
  loadKakaoMaps: vi.fn(),
}))

const created: { center: number[] }[] = []
class LatLng {
  constructor(
    public lat: number,
    public lng: number,
  ) {}
  getLat() {
    return this.lat
  }
  getLng() {
    return this.lng
  }
}
const maps = {
  LatLng,
  Map: class {
    constructor(_el: HTMLElement, o: { center: LatLng }) {
      created.push({ center: [o.center.lat, o.center.lng] })
    }
  },
  Marker: class {},
  load: (cb: () => void) => cb(),
}

const geo = (impl: (ok: PositionCallback, fail: PositionErrorCallback) => void) =>
  Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition: vi.fn(impl) }, configurable: true })

beforeEach(async () => {
  created.length = 0
  const { kakaoMapKey } = await import('../components/kakaoMap')
  vi.mocked(kakaoMapKey).mockReturnValue('test-key')
  vi.mocked(loadKakaoMaps).mockResolvedValue(maps as never)
})
afterEach(cleanup)

describe('위치 지도 (LocationMap)', () => {
  it('GPS 좌표가 있으면 그 자리에 지도를 그리고 GPS 위치라고 적는다', async () => {
    const r = render(<LocationMap coord={{ lat: 37.5, lon: 127.0 }} />)
    await act(async () => {})
    expect(created).toEqual([{ center: [37.5, 127.0] }])
    expect(r.container.textContent).toContain(MAP_GPS_NOTE)
  })

  it('좌표가 없으면 바로 권한을 묻지 않고, 버튼을 누르면 내 위치를 사건 장소가 아니라고 적어 보여 준다', async () => {
    geo((ok) => ok({ coords: { latitude: 35.1, longitude: 126.9 } } as GeolocationPosition))
    const r = render(<LocationMap coord={null} />)
    expect(navigator.geolocation.getCurrentPosition).not.toHaveBeenCalled()
    expect(created).toEqual([])
    await act(async () => fireEvent.click(r.getByText('지도에서 내 위치 보기')))
    expect(created).toEqual([{ center: [35.1, 126.9] }])
    expect(r.container.textContent).toContain(MAP_ME_NOTE)
  })

  it('내 위치를 못 가져오면 지도 없이 이유를 알린다', async () => {
    geo((_ok, fail) => fail!({ code: 1 } as GeolocationPositionError))
    const r = render(<LocationMap coord={null} />)
    await act(async () => fireEvent.click(r.getByText('지도에서 내 위치 보기')))
    expect(r.container.textContent).toContain(MAP_ME_FAILED)
    expect(created).toEqual([])
  })

  it('지도 키가 없으면 아무것도 그리지 않는다', async () => {
    const { kakaoMapKey } = await import('../components/kakaoMap')
    vi.mocked(kakaoMapKey).mockReturnValue(null)
    const r = render(<LocationMap coord={{ lat: 37.5, lon: 127.0 }} />)
    expect(r.container.innerHTML).toBe('')
  })

  it('지도를 못 불러오면 칸을 지운다', async () => {
    vi.mocked(loadKakaoMaps).mockRejectedValue(new Error('blocked'))
    const r = render(<LocationMap coord={{ lat: 37.5, lon: 127.0 }} />)
    await act(async () => {})
    expect(r.container.innerHTML).toBe('')
  })
})
