import { describe, expect, it } from 'vitest'
import { searchPlace, type KakaoMaps } from '../components/kakaoMap'

// 카카오 services를 검색어 → 결과 표로 흉내 낸다. 표에 없으면 ZERO_RESULT
type Row = { place_name?: string; address_name: string; road_address_name?: string; x: string; y: string }
function fakeMaps(address: Record<string, Row[]>, keyword: Record<string, Row[]>) {
  const asked: string[] = []
  const reply = (table: Record<string, Row[]>, kind: string) => (q: string, cb: (d: Row[], s: string) => void) => {
    asked.push(`${kind}:${q}`)
    const d = table[q] ?? []
    cb(d, d.length ? 'OK' : 'ZERO_RESULT')
  }
  const maps = {
    services: {
      Status: { OK: 'OK' },
      Geocoder: class {
        addressSearch = reply(address, 'addr')
      },
      Places: class {
        keywordSearch = reply(keyword, 'kw')
      },
    },
  } as unknown as KakaoMaps
  return { maps, asked }
}

describe('카카오맵 위치 찾기 (searchPlace)', () => {
  it('주소로 먼저 찾는다', async () => {
    const { maps, asked } = fakeMaps({ 상무중앙로: [{ address_name: '광주 서구 상무중앙로', x: '126.85', y: '35.15' }] }, {})
    expect(await searchPlace(maps, '상무중앙로')).toEqual({ lat: 35.15, lon: 126.85, name: '', address: '광주 서구 상무중앙로', matched: '상무중앙로' })
    expect(asked).toEqual(['addr:상무중앙로'])
  })

  it('장소 이름이 검색어 낱말을 담지 않으면 받지 않는다 — 「상무역 사거리」에 「풍금사거리」', async () => {
    const { maps } = fakeMaps({}, { '상무역 사거리': [{ place_name: '풍금사거리', address_name: '광주 서구 금호동', x: '1', y: '2' }] })
    expect(await searchPlace(maps, '상무역 사거리')).toBeNull()
  })

  it('장소 이름이 맞으면 도로명 주소를 쓴다', async () => {
    const { maps } = fakeMaps({}, { 상무역: [{ place_name: '상무역 광주1호선', address_name: '지번', road_address_name: '광주 서구 상무대로 지하 777', x: '126.8', y: '35.1' }] })
    expect(await searchPlace(maps, '상무역')).toMatchObject({ name: '상무역 광주1호선', address: '광주 서구 상무대로 지하 777', matched: '상무역' })
  })

  it('없으면 끝의 「사거리」를 떼고 한 번 더 찾고, 뗀 검색어를 알려 준다', async () => {
    const { maps, asked } = fakeMaps({ 상무중앙로: [{ address_name: '광주 서구 상무중앙로', x: '126.85', y: '35.15' }] }, {})
    expect(await searchPlace(maps, '상무중앙로 사거리')).toMatchObject({ address: '광주 서구 상무중앙로', matched: '상무중앙로' })
    expect(asked).toEqual(['addr:상무중앙로 사거리', 'kw:상무중앙로 사거리', 'addr:상무중앙로'])
  })
})
