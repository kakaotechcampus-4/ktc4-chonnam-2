// 업로드 화면의 영상 시각 안내 — 파일 이름(서버와 같은 두 규칙)과 AVI 머리의 길이로 구간을 만든다.

import { expect, it } from 'vitest'
import { aviSeconds, filenameTime, videoTime, videoTimeText } from '../state/videoTime'

const Y = new Date().getFullYear()
const yy = String(Y).slice(2)

// RIFF·AVI·LIST·hdrl 뒤 avih(프레임 간격 µs, 총 프레임). dmlh를 주면 OpenDML 총 프레임으로 덮는다
function avi(usPerFrame: number, frames: number, dmlhFrames?: number): ArrayBuffer {
  const b = new DataView(new ArrayBuffer(200))
  const put = (at: number, s: string) => [...s].forEach((c, i) => b.setUint8(at + i, c.charCodeAt(0)))
  put(0, 'RIFF')
  put(8, 'AVI ')
  put(12, 'LIST')
  put(20, 'hdrl')
  put(24, 'avih')
  b.setUint32(32, usPerFrame, true)
  b.setUint32(48, frames, true)
  if (dmlhFrames !== undefined) {
    put(100, 'dmlh')
    b.setUint32(108, dmlhFrames, true)
  }
  put(150, 'movi')
  return b.buffer
}

it('서버와 같은 두 파일명 규칙만 읽고, 없는 날짜·다른 이름은 버린다', () => {
  expect(filenameTime('20260824_140312_EVT_1.avi')).toEqual(new Date(2026, 7, 24, 14, 3, 12))
  expect(filenameTime('MDR_260824_140312.AVI')).toEqual(new Date(2026, 7, 24, 14, 3, 12))
  expect(filenameTime('20261324_140312_EVT_1.avi')).toBeNull()
  expect(filenameTime('20260824_250312_EVT_1.avi')).toBeNull()
  expect(filenameTime('20260824_140312.mp4')).toBeNull()
})

it('AVI 머리에서 길이를 읽고, OpenDML이면 dmlh 프레임 수를 쓴다', async () => {
  expect(await aviSeconds(new Blob([avi(40_000, 1500)]))).toBe(60)
  expect(await aviSeconds(new Blob([avi(40_000, 1500, 3000)]))).toBe(120)
  expect(await aviSeconds(new Blob([avi(40_000, 1500, 0)]))).toBe(60) // 비워 둔 dmlh(ffmpeg)
  expect(await aviSeconds(new Blob([avi(40_000, 0)]))).toBeNull()
  expect(await aviSeconds(new Blob(['not an avi file at all']))).toBeNull()
})

it('이어진 녹화는 한 구간으로 묶고, 떨어진 녹화와 못 읽은 파일은 따로 센다', async () => {
  const minute = avi(40_000, 1500)
  const v = await videoTime([
    new File([minute], `MDR_${yy}0824_140500.AVI`),
    new File([minute], `MDR_${yy}0824_140302.AVI`),
    new File([minute], `MDR_${yy}0824_140405.AVI`),
    new File([minute], `${Y}0824_183000_EVT_1.avi`),
    new File([minute], 'FILE_017.mp4'),
  ])
  expect(v.spans).toEqual([
    { start: new Date(Y, 7, 24, 14, 3, 2), end: new Date(Y, 7, 24, 14, 6, 0) },
    { start: new Date(Y, 7, 24, 18, 30, 0), end: new Date(Y, 7, 24, 18, 31, 0) },
  ])
  expect(v.unread).toBe(1)
  expect(videoTimeText(v)).toBe('8월 24일 오후 2:03 ~ 오후 2:06, 8월 24일 오후 6:30 ~ 오후 6:31')
})

it('길이를 못 읽으면 시작 시각만, 올해가 아니면 해를, 날이 바뀌면 끝에도 날짜를 붙인다', () => {
  const at = (...a: [number, number, number, number, number]) => new Date(...a)
  expect(videoTimeText({ spans: [{ start: at(Y, 7, 24, 14, 3), end: at(Y, 7, 24, 14, 3) }], unread: 0 })).toBe(
    '8월 24일 오후 2:03',
  )
  expect(videoTimeText({ spans: [{ start: at(2000, 0, 1, 0, 0), end: at(2000, 0, 1, 0, 0) }], unread: 0 })).toBe(
    '2000년 1월 1일 오전 12:00',
  )
  expect(videoTimeText({ spans: [{ start: at(Y, 7, 24, 23, 59), end: at(Y, 7, 25, 0, 10) }], unread: 0 })).toBe(
    '8월 24일 오후 11:59 ~ 8월 25일 오전 12:10',
  )
  expect(videoTimeText({ spans: [], unread: 2 })).toBeNull()
})
