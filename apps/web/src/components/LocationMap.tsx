import { useEffect, useRef, useState, type JSX } from 'react'
import { LocateFixed } from 'lucide-react'
import { kakaoMapKey, loadKakaoMaps, reverseAddress, searchPlace, type FoundPlace, type KakaoLatLng } from './kakaoMap'

// 위치 칸의 지도. 블랙박스 GPS 좌표(location_display.coord)가 있으면 그 자리를 찍는다.
// GPS가 없으면 위치 글(검색어 또는 대신고가 정리한 위치)을 카카오맵에서 찾아 「이렇게 이해했다」를 보여 준다 —
// 확정이 아니라 사용자가 확인할 자리다. 못 찾으면 사용자가 버튼을 눌렀을 때만 지금 내 위치를 보여 준다
// (화면을 열자마자 권한을 묻지 않는다). 내 위치는 사건 장소가 아니다.
// 최종 핀은 어느 경우든 안전신문고 지도에서 사용자가 놓는다(core-user-flow §14).
// 지도 키가 없거나 지도를 못 불러오면 칸을 그리지 않는다 — 위치 글과 검색어는 그대로 있다.
// 찾은 자리는 출발점이다. 핀을 끌거나 지도를 눌러 옮기며 주변을 살펴볼 수 있고, 옮긴 자리의 주소를 적는다.
// 옮긴 자리는 이 화면 안의 확인용이고 신고 위치가 되지 않는다.

type Spot = { lat: number; lon: number; kind: 'gps' | 'place' | 'me' }
type MyState = 'idle' | 'asking' | 'failed'
type PlaceState = { query: string; found: FoundPlace | null }
// 옮긴 자리. address는 찾는 중 undefined, 못 찾으면 null. from은 어느 출발점에서 옮겼는가 — 출발점이 바뀌면 버린다
type Moved = { from: string; lat: number; lon: number; address?: string | null }

export const MAP_GPS_NOTE = '블랙박스 GPS가 기록한 위치예요. 안전신문고 지도에서 핀을 확인해 주세요.'
export const MAP_PLACE_NOTE = '대신고가 이해한 위치를 카카오맵에서 찾은 곳이에요. 맞는지 확인해 주세요.'
export const MAP_ME_NOTE = '지금 내 위치예요. 사건 장소가 아니니, 안전신문고 지도에서 사건 장소를 골라 주세요.'
export const MAP_ME_FAILED = '내 위치를 가져오지 못했어요. 브라우저의 위치 권한을 확인해 주세요.'
export const MAP_MOVED_NOTE = '직접 옮긴 위치예요. 최종 위치는 안전신문고 지도에서 골라 주세요.'
export const MAP_MOVE_HINT = '핀을 끌거나 지도를 눌러 주변을 살펴볼 수 있어요.'
export const placeNotFound = (q: string) => `카카오맵에서 「${q}」을(를) 찾지 못했어요.`
// 「사거리」 등을 떼고 찾았을 때 — 정확한 지점이 아니라 그 길 · 동네의 대표 지점이다
export const placeMatched = (q: string) => `「${q}」(으)로 찾은 대표 지점이라 실제 장소와 떨어져 있을 수 있어요.`

// 「○○ 부근」처럼 끝에 붙은 말은 장소 검색을 빗나가게 해서 뗀다
export function placeQuery(text: string | null | undefined): string | null {
  const q = (text ?? '').trim().replace(/(\s*(부근|근처|인근|쯤))+$/, '').trim()
  return q || null
}

const LABEL = { gps: '블랙박스 GPS 위치 지도', place: '카카오맵에서 찾은 위치 지도', me: '지금 내 위치 지도' }

export function LocationMap(props: { coord: { lat: number; lon: number } | null; query?: string | null }): JSX.Element | null {
  const key = kakaoMapKey()
  const query = props.coord ? null : placeQuery(props.query)
  const [place, setPlace] = useState<PlaceState | null>(null)
  const [me, setMe] = useState<{ lat: number; lon: number } | null>(null)
  const [myState, setMyState] = useState<MyState>('idle')
  const [broken, setBroken] = useState(false)
  const [moved, setMoved] = useState<Moved | null>(null)
  const el = useRef<HTMLDivElement>(null)
  const resetPin = useRef<(() => void) | null>(null)
  // 「처음 위치로 돌아가기」를 누르면 그 버튼이 사라진다 — 초점이 body로 빠지지 않게 안내 칸으로 옮긴다
  const caption = useRef<HTMLElement>(null)
  const returning = useRef(false)
  // 지금 검색어에 대한 결과만 쓴다 — 위치를 고치면 옛 결과는 버린다
  const placeNow = place && place.query === query ? place : null
  const found = placeNow?.found ?? null
  const spot: Spot | null = props.coord
    ? { ...props.coord, kind: 'gps' }
    : found
      ? { lat: found.lat, lon: found.lon, kind: 'place' }
      : me
        ? { ...me, kind: 'me' }
        : null
  const from = spot ? `${spot.lat},${spot.lon}` : ''
  const movedNow = moved && moved.from === from ? moved : null

  useEffect(() => {
    if (!key || !query) return
    let live = true
    loadKakaoMaps(key)
      .then((maps) => searchPlace(maps, query))
      .then(
        (f) => live && setPlace({ query, found: f }),
        () => live && setBroken(true),
      )
    return () => {
      live = false
    }
  }, [key, query])

  useEffect(() => {
    if (!key || !spot || !el.current) return
    let live = true
    let resize: ResizeObserver | undefined
    loadKakaoMaps(key).then(
      (maps) => {
        if (!live || !el.current) return
        const center = new maps.LatLng(spot.lat, spot.lon)
        const map = new maps.Map(el.current, { center, level: 3 })
        const marker = new maps.Marker({ position: center, map, draggable: true })
        const moveTo = (at: KakaoLatLng) => {
          marker.setPosition(at)
          const lat = at.getLat()
          const lon = at.getLng()
          setMoved({ from, lat, lon })
          reverseAddress(maps, lat, lon).then(
            (address) => live && setMoved((m) => (m && m.lat === lat && m.lon === lon ? { ...m, address } : m)),
            () => live && setMoved((m) => (m && m.lat === lat && m.lon === lon ? { ...m, address: null } : m)),
          )
        }
        maps.event.addListener(map, 'click', (e) => e && moveTo(e.latLng))
        maps.event.addListener(marker, 'dragend', () => moveTo(marker.getPosition()))
        resetPin.current = () => {
          marker.setPosition(center)
          map.setCenter(center)
        }
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
      resetPin.current = null
    }
  }, [key, spot?.lat, spot?.lon]) // 의존성은 일부러 좌표 값만 둔다: spot 객체가 새로 와도 좌표가 같으면 지도를 다시 만들지 않는다

  useEffect(() => {
    if (!returning.current || movedNow) return
    returning.current = false
    caption.current?.focus()
  })

  if (!key || broken) return null
  // 찾는 중에는 버튼을 먼저 띄웠다 지우지 않게 비워 둔다
  if (!spot && query && !placeNow) return null

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
        {query && <p className="res-map-note">{placeNotFound(query)}</p>}
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

  const backToStart = () => {
    resetPin.current?.()
    returning.current = true
    setMoved(null)
  }

  return (
    <figure className="res-map">
      <div ref={el} className="res-map-canvas" role="img" aria-label={LABEL[spot.kind]} />
      {movedNow ? (
        <figcaption className="res-map-note">
          <span className="res-map-addr" role="status">
            직접 옮긴 위치 ·{' '}
            {movedNow.address === undefined ? '주소 찾는 중' : (movedNow.address ?? '주소를 찾지 못했어요')}
          </span>
          {MAP_MOVED_NOTE}
          <button type="button" className="res-link res-map-reset" onClick={backToStart}>
            처음 위치로 돌아가기
          </button>
        </figcaption>
      ) : (
        <figcaption ref={caption} tabIndex={-1} className="res-map-note">
          {spot.kind === 'place' && found && (
            <span className="res-map-addr">
              카카오맵에서 확인한 주소 · {found.address}
              {found.name && ` (${found.name})`}
            </span>
          )}
          {spot.kind === 'place' && found && found.matched !== query && (
            <span className="res-map-addr">{placeMatched(found.matched)}</span>
          )}
          {spot.kind === 'gps' ? MAP_GPS_NOTE : spot.kind === 'place' ? MAP_PLACE_NOTE : MAP_ME_NOTE}
          <span className="res-map-hint">{MAP_MOVE_HINT}</span>
        </figcaption>
      )}
    </figure>
  )
}
