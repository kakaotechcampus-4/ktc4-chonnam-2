import type { CSSProperties, JSX } from 'react'
import carSide from '../assets/car/car-side.webp'
import frontBack from '../assets/car/wheel-front-back.webp'
import frontSpin from '../assets/car/wheel-front-spin.webp'
import rearBack from '../assets/car/wheel-rear-back.webp'
import rearSpin from '../assets/car/wheel-rear-spin.webp'
import { Puffs, burst } from './CarFx'

// 진행 화면 대표 영상 박스 안 — 「장면 찾기」가 도는 동안만(사용자 결정 「아주 화려하게」 10/23).
// 영상 위를 옅게 덮고, 점선 도로가 흐르는 위를 첫 화면의 같은 차가 바퀴를 굴리며 제자리에서 달린다.
// 차 뒤로 연기가 계속 피어나고 레이더 파동이 퍼진다. 진행률이나 남은 시간을 뜻하지 않는다.
// 차·휠 위치는 원본(1774×887) 비율(%)로 잡아 박스 크기가 바뀌어도 그대로 맞는다.
const PCT = (v: number, of: number) => `${(v / of) * 100}%`
const WHEEL = (x: number) =>
  ({ left: PCT(x, 1774), top: PCT(509.5, 887), width: PCT(243, 1774), height: PCT(243, 887) }) as CSSProperties
const EXHAUST = burst(9, { x: 0, y: 0 }, { from: 0, gap: 130, size: [18, 30], dx: [30, 70], dy: [-26, -8], t: 1200, g: 3, seed: 23 })
const DUST = burst(8, { x: 0, y: 0 }, { from: 60, gap: 150, size: [26, 40], dx: [40, 90], dy: [-24, -6], t: 1200, g: 2.8, seed: 29 })

export function SearchFx(): JSX.Element {
  return (
    <div className="flow-search-fx" aria-hidden>
      <span className="flow-search-road" />
      {[0, 1, 2].map((i) => (
        <span key={i} className="rs-ring flow-search-ring" style={{ '--d': `${i * 800}ms` } as CSSProperties} />
      ))}
      <div className="flow-search-car">
        <div className="flow-search-body">
          <img src={carSide} alt="" />
          <span className="flow-search-wheel" style={WHEEL(200.5)}>
            <img src={frontBack} alt="" />
            <img className="spin" src={frontSpin} alt="" />
          </span>
          <span className="flow-search-wheel" style={WHEEL(1265)}>
            <img src={rearBack} alt="" />
            <img className="spin" src={rearSpin} alt="" />
          </span>
        </div>
        {/* 배기(뒤범퍼 아래)와 뒷바퀴 흙먼지 — 차를 따라 같은 자리에서 계속 피어난다 */}
        <span className="flow-search-at" style={{ left: PCT(1700, 1774), top: PCT(690, 887) }}>
          <Puffs items={EXHAUST} loop />
        </span>
        <span className="flow-search-at" style={{ left: PCT(1386, 1774), top: PCT(750, 887) }}>
          <Puffs items={DUST} loop />
        </span>
      </div>
    </div>
  )
}
