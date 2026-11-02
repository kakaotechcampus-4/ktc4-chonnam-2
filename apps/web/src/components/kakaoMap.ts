// 카카오 지도 JavaScript SDK를 한 번만 불러온다. 키는 build 때 `VITE_KAKAO_MAP_KEY`로 받는다.
// 이 키는 브라우저에 그대로 나가는 공개 키다 — 카카오 개발자 콘솔에 등록한 도메인에서만 동작한다.
// 키가 없으면 지도를 그리지 않는다(LocationMap).

export interface KakaoLatLng {
  getLat(): number
  getLng(): number
}

export interface KakaoMaps {
  LatLng: new (lat: number, lng: number) => KakaoLatLng
  Map: new (el: HTMLElement, options: { center: KakaoLatLng; level: number }) => unknown
  Marker: new (options: { position: KakaoLatLng; map: unknown }) => unknown
  load(callback: () => void): void
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
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key)}&autoload=false`
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
