import { useEffect, useRef, useState, type JSX } from 'react'
import { LocateFixed } from 'lucide-react'
import { kakaoMapKey, loadKakaoMaps } from './kakaoMap'

// 위치 칸의 지도. 블랙박스 GPS 좌표(location_display.coord)가 있으면 그 자리를 찍는다.
// 좌표가 없으면 사용자가 버튼을 눌렀을 때만 지금 내 위치를 보여 준다 — 화면을 열자마자 권한을 묻지 않는다.
// 내 위치는 사건 장소가 아니다. 그렇다고 적고, 최종 핀은 안전신문고 지도에서 사용자가 놓는다(core-user-flow §14).
// 지도 키가 없거나 지도를 못 불러오면 칸을 그리지 않는다 — 위치 글과 검색어는 그대로 있다.

type Spot = { lat: number; lon: number; kind: 'gps' | 'me' }
type MyState = 'idle' | 'asking' | 'failed'

export const MAP_GPS_NOTE = '블랙박스 GPS가 기록한 위치예요. 안전신문고 지도에서 핀을 확인해 주세요.'
export const MAP_ME_NOTE = '지금 내 위치예요. 사건 장소가 아니니, 안전신문고 지도에서 사건 장소를 골라 주세요.'
export const MAP_ME_FAILED = '내 위치를 가져오지 못했어요. 브라우저의 위치 권한을 확인해 주세요.'

export function LocationMap(props: { coord: { lat: number; lon: number } | null }): JSX.Element | null {
  const key = kakaoMapKey()
  const [me, setMe] = useState<{ lat: number; lon: number } | null>(null)
  const [myState, setMyState] = useState<MyState>('idle')
  const [broken, setBroken] = useState(false)
  const el = useRef<HTMLDivElement>(null)
  const spot: Spot | null = props.coord ? { ...props.coord, kind: 'gps' } : me ? { ...me, kind: 'me' } : null

  useEffect(() => {
    if (!key || !spot || !el.current) return
    let live = true
    let resize: ResizeObserver | undefined
    loadKakaoMaps(key).then(
      (maps) => {
        if (!live || !el.current) return
        const center = new maps.LatLng(spot.lat, spot.lon)
        const map = new maps.Map(el.current, { center, level: 3 })
        new maps.Marker({ position: center, map })
        // 칸 크기가 만든 뒤에 바뀌면(화면이 자리 잡는 중 등) 지도는 옛 크기 기준이라 핀이 가운데서 벗어난다
        resize = new ResizeObserver(() => {
          map.relayout()
          map.setCenter(center)
        })
        resize.observe(el.current)
      },
      () => live && setBroken(true),
    )
    return () => {
      live = false
      resize?.disconnect()
    }
  }, [key, spot?.lat, spot?.lon]) // eslint-disable-line react-hooks/exhaustive-deps -- 좌표가 바뀔 때만

  if (!key || broken) return null

  const locate = () => {
    if (!navigator.geolocation) return setMyState('failed')
    setMyState('asking')
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setMe({ lat: p.coords.latitude, lon: p.coords.longitude })
        setMyState('idle')
      },
      () => setMyState('failed'),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    )
  }

  if (!spot)
    return (
      <div className="res-map-empty">
        <button type="button" className="rs-btn sec sm" disabled={myState === 'asking'} onClick={locate}>
          <LocateFixed size={16} strokeWidth={2} aria-hidden />
          {myState === 'asking' ? '내 위치 찾는 중' : '지도에서 내 위치 보기'}
        </button>
        {myState === 'failed' && (
          <p className="res-map-note" role="status">
            {MAP_ME_FAILED}
          </p>
        )}
      </div>
    )

  return (
    <figure className="res-map">
      <div ref={el} className="res-map-canvas" role="img" aria-label={spot.kind === 'gps' ? '블랙박스 GPS 위치 지도' : '지금 내 위치 지도'} />
      <figcaption className="res-map-note">{spot.kind === 'gps' ? MAP_GPS_NOTE : MAP_ME_NOTE}</figcaption>
    </figure>
  )
}
