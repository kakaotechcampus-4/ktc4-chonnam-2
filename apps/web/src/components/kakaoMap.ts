// 카카오 지도 JavaScript SDK를 한 번만 불러온다. 키는 build 때 `VITE_KAKAO_MAP_KEY`로 받는다.
// 이 키는 브라우저에 그대로 나가는 공개 키다 — 카카오 개발자 콘솔에 등록한 도메인에서만 동작한다.
// 키가 없으면 지도를 그리지 않는다(LocationMap).
// 카카오 개발자 콘솔에서 세 가지가 모두 돼 있어야 SDK가 열린다(아니면 401/403, 지도 칸이 숨는다):
//   1. 앱 키 중 **JavaScript 키**를 쓴다 — REST API 키는 「appKeyType is REST_API_KEY」로 거부된다
//   2. JavaScript SDK 도메인(옛 콘솔: 플랫폼 → Web 사이트 도메인)에 `http://localhost:5173`과 배포 도메인을 등록한다
//   3. 제품 설정에서 카카오맵을 켠다 — 꺼져 있으면 「disabled OPEN_MAP_AND_LOCAL service」

export interface KakaoLatLng {
  getLat(): number
  getLng(): number
}

export interface KakaoMap {
  relayout(): void
  setCenter(latlng: KakaoLatLng): void
}

export interface KakaoMarker {
  setPosition(latlng: KakaoLatLng): void
  getPosition(): KakaoLatLng
}

// 장소 검색(services 라이브러리)에서 쓰는 만큼만. x = 경도, y = 위도(문자열)
interface KakaoPlace {
  place_name: string
  address_name: string
  road_address_name: string
  x: string
  y: string
}

export interface KakaoMaps {
  LatLng: new (lat: number, lng: number) => KakaoLatLng
  Map: new (el: HTMLElement, options: { center: KakaoLatLng; level: number }) => KakaoMap
  Marker: new (options: { position: KakaoLatLng; map: unknown; draggable?: boolean }) => KakaoMarker
  load(callback: () => void): void
  event: { addListener(target: unknown, type: string, handler: (e?: { latLng: KakaoLatLng }) => void): void }
  services: {
    Places: new () => { keywordSearch(query: string, callback: (data: KakaoPlace[], status: string) => void): void }
    Geocoder: new () => {
      addressSearch(query: string, callback: (data: KakaoAddress[], status: string) => void): void
      coord2Address(lng: number, lat: number, callback: (data: KakaoCoordAddress[], status: string) => void): void
    }
    Status: { OK: string }
  }
}

interface KakaoAddress {
  address_name: string
  x: string
  y: string
}

interface KakaoCoordAddress {
  address: { address_name: string } | null
  road_address: { address_name: string } | null
}

// matched: 실제로 찾은 검색어. 「사거리」 등을 떼고 찾았으면 원래 글과 다르다 — 화면이 그대로 밝힌다
export type FoundPlace = { lat: number; lon: number; name: string; address: string; matched: string }

const CROSSING = /\s*(사거리|삼거리|오거리|교차로)$/
const squash = (s: string) => s.replace(/\s+/g, '')

// 장소 이름이 검색어의 낱말을 담고 있을 때만 받는다 — 「상무역 사거리」에 「풍금사거리」가 첫 결과로 오는 일이 있다
function relevant(query: string, placeName: string): boolean {
  const name = squash(placeName)
  if (squash(query).includes(name)) return true
  return query
    .split(/\s+/)
    .filter((w) => w.length >= 2 && !CROSSING.test(w))
    .some((w) => name.includes(w))
}

function byAddress(maps: KakaoMaps, q: string): Promise<FoundPlace | null> {
  return new Promise((resolve) =>
    new maps.services.Geocoder().addressSearch(q, (data, status) => {
      const a = status === maps.services.Status.OK ? data[0] : undefined
      resolve(a ? { lat: Number(a.y), lon: Number(a.x), name: '', address: a.address_name, matched: q } : null)
    }),
  )
}

function byKeyword(maps: KakaoMaps, q: string): Promise<FoundPlace | null> {
  return new Promise((resolve) =>
    new maps.services.Places().keywordSearch(q, (data, status) => {
      const p = status === maps.services.Status.OK ? data.find((d) => relevant(q, d.place_name)) : undefined
      resolve(p ? { lat: Number(p.y), lon: Number(p.x), name: p.place_name, address: p.road_address_name || p.address_name, matched: q } : null)
    }),
  )
}

// 주소(도로명 · 지번) → 장소 이름 순으로 찾고, 없으면 끝의 「사거리 · 삼거리 · 교차로」를 떼고 한 번 더 찾는다.
// 못 찾으면 null
export async function searchPlace(maps: KakaoMaps, query: string): Promise<FoundPlace | null> {
  const shorter = query.replace(CROSSING, '').trim()
  for (const q of shorter && shorter !== query ? [query, shorter] : [query]) {
    const found = (await byAddress(maps, q)) ?? (await byKeyword(maps, q))
    if (found) return found
  }
  return null
}

// 좌표 → 주소(도로명이 있으면 도로명, 없으면 지번). 못 찾으면 null
export function reverseAddress(maps: KakaoMaps, lat: number, lon: number): Promise<string | null> {
  return new Promise((resolve) =>
    new maps.services.Geocoder().coord2Address(lon, lat, (data, status) => {
      const a = status === maps.services.Status.OK ? data[0] : undefined
      resolve(a?.road_address?.address_name || a?.address?.address_name || null)
    }),
  )
}

declare global {
  interface Window {
    kakao?: { maps: KakaoMaps }
  }
}

export function kakaoMapKey(): string | null {
  return import.meta.env.VITE_KAKAO_MAP_KEY || null
}

let loading: Promise<KakaoMaps> | null = null

export function loadKakaoMaps(key: string): Promise<KakaoMaps> {
  if (loading) return loading
  loading = new Promise<KakaoMaps>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key)}&autoload=false&libraries=services`
    script.async = true
    script.onload = () => {
      const maps = window.kakao?.maps
      if (!maps) return reject(new Error('kakao maps missing'))
      maps.load(() => resolve(maps))
    }
    script.onerror = () => reject(new Error('kakao maps load failed'))
    document.head.appendChild(script)
  })
  // 실패하면 다음에 다시 시도할 수 있게 비운다
  loading.catch(() => (loading = null))
  return loading
}
