import type { CSSProperties, JSX } from 'react'
import carSide from '../assets/car/car-side.webp'
import frontBack from '../assets/car/wheel-front-back.webp'
import frontSpin from '../assets/car/wheel-front-spin.webp'
import rearBack from '../assets/car/wheel-rear-back.webp'
import rearSpin from '../assets/car/wheel-rear-spin.webp'
import { Puffs, burst } from './CarFx'

// 결과 화면 머리글 뒤에 서는 자동차(520×260). 진행에서 막 넘어왔을 때(arriving)만 들어오며 브레이크
// 연기·스키드 자국·바닥 파동을 낸다 — 시간과 움직임은 refresh.css(.res-bgcar) 주석에 있다.
// 휠 위치는 원본(1774×887) 비율(%), 연기는 이 상자 기준 px(바퀴 바닥 y = 260 × 0.85 ≈ 221).
const W = 520
const GROUND = 221
const FRONT_X = ((200.5 + 121.5) / 1774) * W
const REAR_X = ((1265 + 121.5) / 1774) * W
const PCT = (v: number, of: number) => `${(v / of) * 100}%`
const WHEEL = (x: number) =>
  ({ left: PCT(x, 1774), top: PCT(509.5, 887), width: PCT(243, 1774), height: PCT(243, 887) }) as CSSProperties
const BRAKE = [
  ...burst(10, { x: FRONT_X, y: GROUND - 4 }, { from: 380, gap: 36, size: [30, 52], dx: [40, 120], dy: [-50, -14], t: 1100, g: 3, seed: 31 }),
  ...burst(10, { x: REAR_X, y: GROUND - 4 }, { from: 400, gap: 36, size: [30, 52], dx: [40, 120], dy: [-50, -14], t: 1100, g: 3, seed: 37 }),
]

export function ArrivingCar(props: { arriving?: boolean }): JSX.Element {
  return (
    <div className={`res-bgcar${props.arriving ? ' is-arriving' : ''}`} aria-hidden>
      {props.arriving &&
        [FRONT_X, REAR_X].map((x) => <span key={x} className="res-skid" style={{ '--x': `${x}px`, '--y': `${GROUND}px` } as CSSProperties} />)}
      <div className="res-car-drive">
        <div className="res-car-body">
          <img src={carSide} alt="" />
          <span className="res-car-wheel" style={WHEEL(200.5)}>
            <img src={frontBack} alt="" />
            <img className="spin" src={frontSpin} alt="" />
          </span>
          <span className="res-car-wheel" style={WHEEL(1265)}>
            <img src={rearBack} alt="" />
            <img className="spin" src={rearSpin} alt="" />
          </span>
        </div>
      </div>
      {props.arriving && (
        <>
          <Puffs items={BRAKE} />
          {[0, 1].map((i) => (
            <span key={i} className="rs-ring res-ground-ring" style={{ '--d': `${550 + i * 160}ms` } as CSSProperties} />
          ))}
        </>
      )}
    </div>
  )
}
