import { expect, it } from 'vitest'
import { avcCodec, firstVideoChunk } from '../components/aviFrame'

const ascii = (s: string) => [...s].map((c) => c.charCodeAt(0))
const u32 = (n: number) => [n & 0xff, (n >> 8) & 0xff, (n >> 16) & 0xff, (n >>> 24) & 0xff]
const chunk = (id: string, data: number[]) => [...ascii(id), ...u32(data.length), ...data, ...(data.length & 1 ? [0] : [])]
const list = (kind: string, body: number[]) => [...ascii('LIST'), ...u32(body.length + 4), ...ascii(kind), ...body]
const avi = (...body: number[][]) => {
  const inner = [...ascii('AVI '), ...body.flat()]
  return new Uint8Array([...ascii('RIFF'), ...u32(inner.length), ...inner])
}
// 실제 블랙박스 첫 조각처럼 SPS(High · level 5.0)로 시작하는 Annex B
const keyframe = [0, 0, 0, 1, 0x67, 0x64, 0x00, 0x32, 0xac, 0, 0, 0, 1, 0x68, 0xee]

it('hdrl · JUNK를 건너뛰고 movi의 첫 영상 조각을 꺼낸다(오디오 · 홀수 크기 padding 포함)', () => {
  const bytes = avi(list('hdrl', chunk('avih', [1, 2, 3])), chunk('JUNK', [0, 0, 0]),
    list('movi', [...chunk('01wb', [9, 9, 9]), ...chunk('00dc', keyframe)]))
  expect([...firstVideoChunk(bytes)!]).toEqual(keyframe)
  expect(avcCodec(firstVideoChunk(bytes)!)).toBe('avc1.640032')
})

it('movi 안의 `rec ` 묶음 안으로 들어간다 · 빈 영상 조각은 건너뛴다', () => {
  const bytes = avi(list('movi', [...chunk('00dc', []), ...list('rec ', chunk('00dc', keyframe))]))
  expect([...firstVideoChunk(bytes)!]).toEqual(keyframe)
})

it('AVI가 아니거나 · movi가 없거나 · 조각이 앞부분 밖으로 잘리면 null', () => {
  expect(firstVideoChunk(new Uint8Array([0, 0, 0, 0x18, ...ascii('ftypisom')]))).toBeNull()
  expect(firstVideoChunk(avi(list('hdrl', chunk('avih', [1]))))).toBeNull()
  const cut = avi(list('movi', chunk('00dc', keyframe)))
  expect(firstVideoChunk(cut.subarray(0, cut.length - 4))).toBeNull()
})

it('SPS가 없으면 코덱 문자열을 만들지 않는다', () => {
  expect(avcCodec(new Uint8Array([0, 0, 0, 1, 0x65, 1, 2, 3]))).toBeNull()
})
