// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LocationMap, MAP_GPS_NOTE, MAP_ME_FAILED, MAP_ME_NOTE, MAP_PLACE_NOTE, placeMatched, placeNotFound, placeQuery } from '../components/LocationMap'
import { loadKakaoMaps, searchPlace } from '../components/kakaoMap'
import { SNAPSHOTS } from '../contracts/fixtures'
import { ResultScreen } from '../screens/ResultScreen'

vi.mock('../components/kakaoMap', () => ({
  kakaoMapKey: vi.fn(() => 'test-key'),
  loadKakaoMaps: vi.fn(),
  searchPlace: vi.fn(),
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
    relayout() {}
    setCenter() {}
  },
  Marker: class {},
  load: (cb: () => void) => cb(),
}

const geo = (impl: (ok: PositionCallback, fail: PositionErrorCallback) => void) =>
  Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition: vi.fn(impl) }, configurable: true })

// jsdom에는 ResizeObserver가 없다
globalThis.ResizeObserver ??= class {
  observe() {}
  disconnect() {}
  unobserve() {}
} as unknown as typeof ResizeObserver

beforeEach(async () => {
  created.length = 0
  const { kakaoMapKey } = await import('../components/kakaoMap')
  vi.mocked(kakaoMapKey).mockReturnValue('test-key')
  vi.mocked(loadKakaoMaps).mockResolvedValue(maps as never)
  vi.mocked(searchPlace).mockReset()
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

  describe('GPS가 없을 때 위치 글을 카카오맵에서 찾는다', () => {
    const found = { lat: 35.152, lon: 126.851, name: '상무역', address: '광주 서구 치평동 1200', matched: '상무역 사거리' }

    it('찾으면 그 자리에 핀을 찍고, 카카오맵에서 확인한 주소와 「맞는지 확인해 주세요」를 적는다', async () => {
      vi.mocked(searchPlace).mockResolvedValue(found)
      const r = render(<LocationMap coord={null} query="상무역 사거리" />)
      await act(async () => {})
      expect(searchPlace).toHaveBeenCalledWith(maps, '상무역 사거리')
      expect(created).toEqual([{ center: [35.152, 126.851] }])
      expect(r.container.textContent).toContain('카카오맵에서 확인한 주소')
      expect(r.container.textContent).toContain('광주 서구 치평동 1200')
      expect(r.container.textContent).toContain(MAP_PLACE_NOTE)
      expect(r.queryByText('지도에서 내 위치 보기')).toBeNull()
      expect(r.container.textContent).not.toContain(placeMatched('상무역 사거리'))
    })

    it('「사거리」를 떼고 찾았으면 대표 지점이라 떨어져 있을 수 있다고 밝힌다', async () => {
      vi.mocked(searchPlace).mockResolvedValue({ ...found, matched: '상무역' })
      const r = render(<LocationMap coord={null} query="상무역 사거리" />)
      await act(async () => {})
      expect(r.container.textContent).toContain(placeMatched('상무역'))
    })

    it('못 찾으면 지도 없이 그렇다고 적고, 내 위치 보기 버튼을 둔다', async () => {
      vi.mocked(searchPlace).mockResolvedValue(null)
      const r = render(<LocationMap coord={null} query="상무역 사거리" />)
      await act(async () => {})
      expect(created).toEqual([])
      expect(r.container.textContent).toContain(placeNotFound('상무역 사거리'))
      expect(r.getByText('지도에서 내 위치 보기')).toBeTruthy()
    })

    it('GPS 좌표가 있으면 찾지 않는다', async () => {
      render(<LocationMap coord={{ lat: 37.5, lon: 127.0 }} query="상무역 사거리" />)
      await act(async () => {})
      expect(searchPlace).not.toHaveBeenCalled()
      expect(created).toEqual([{ center: [37.5, 127.0] }])
    })

    it('검색어 끝의 「부근 · 근처 · 쯤 · 인근」은 떼고 찾는다', () => {
      expect(placeQuery('상무중앙로 사거리 부근')).toBe('상무중앙로 사거리')
      expect(placeQuery('상무역 근처쯤')).toBe('상무역')
      expect(placeQuery('  ')).toBeNull()
      expect(placeQuery(null)).toBeNull()
    })
  })
})

it('결과 화면: 서버 검색어가 있어도 사용자가 위치를 고치면 고친 글로 지도를 찾는다', async () => {
  vi.mocked(searchPlace).mockResolvedValue(null)
  const happy = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.view.stage === 'READY' && s.view.package !== null)!.view
  const ev = happy.evidence!
  const view = { ...happy, evidence: { ...ev, location_display: { ...ev.location_display, coord: null, search_keyword: '광주 상무지구 상무중앙로 사거리' } } }
  const props = { view, onCandidates: vi.fn(), onPlate: vi.fn(), onDetails: vi.fn(), onAction: vi.fn(), canRun: () => true }
  const r = render(<ResultScreen {...props} />)
  await act(async () => {})
  expect(searchPlace).toHaveBeenLastCalledWith(maps, '광주 상무지구 상무중앙로 사거리')
  r.rerender(<ResultScreen {...props} edits={{ location: '운천역 사거리' }} />)
  await act(async () => {})
  expect(searchPlace).toHaveBeenLastCalledWith(maps, '운천역 사거리')
})
