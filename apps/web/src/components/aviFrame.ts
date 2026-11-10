// 브라우저 <video>는 AVI 컨테이너를 열지 못한다(Chrome · Edge). 블랙박스 AVI는 대부분 안의 영상이
// H.264라서, 파일 앞부분에서 첫 영상 조각(`##dc`)만 꺼내 WebCodecs로 한 장 디코드한다.
// 꺼내지 못하거나 디코드하지 못하면 null — 부르는 쪽이 지금의 대체 화면을 둔다.
const HEAD_BYTES = 8 * 1024 * 1024

export interface DecodedFrame {
  image: CanvasImageSource
  width: number
  height: number
  close: () => void
}

/** RIFF/AVI의 `movi` 목록에서 첫 영상 조각(`##dc`)의 바이트. 앞부분 안에 없으면 null */
export function firstVideoChunk(bytes: Uint8Array<ArrayBuffer>): Uint8Array<ArrayBuffer> | null {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const id = (at: number) => String.fromCharCode(bytes[at], bytes[at + 1], bytes[at + 2], bytes[at + 3])
  if (bytes.length < 12 || id(0) !== 'RIFF' || id(8) !== 'AVI ') return null
  let at = 12
  let moviEnd = -1
  while (at + 8 <= bytes.length) {
    const name = id(at)
    const size = view.getUint32(at + 4, true)
    if (moviEnd < 0) {
      // 최상위: hdrl · JUNK 등을 건너뛰고 movi 목록 안으로 들어간다
      if (name === 'LIST' && at + 12 <= bytes.length && id(at + 8) === 'movi') {
        moviEnd = at + 8 + size
        at += 12
      } else {
        at += 8 + size + (size & 1)
      }
      continue
    }
    if (at >= moviEnd) return null
    if (name === 'LIST') {
      at += 12 // `rec ` 묶음 안으로
    } else if (name.endsWith('dc') && size > 0) {
      return at + 8 + size <= bytes.length ? bytes.subarray(at + 8, at + 8 + size) : null
    } else {
      at += 8 + size + (size & 1)
    }
  }
  return null
}

/** Annex B H.264 조각의 SPS에서 WebCodecs 코덱 문자열(`avc1.PPCCLL`). SPS가 없으면 null */
export function avcCodec(data: Uint8Array): string | null {
  const hex = (b: number) => b.toString(16).padStart(2, '0')
  for (let i = 0; i + 6 < data.length; i++) {
    if (data[i] === 0 && data[i + 1] === 0 && data[i + 2] === 1 && (data[i + 3] & 0x1f) === 7) {
      return `avc1.${hex(data[i + 4])}${hex(data[i + 5])}${hex(data[i + 6])}`
    }
  }
  return null
}

export async function decodeAviFrame(file: Blob): Promise<DecodedFrame | null> {
  const chunk = firstVideoChunk(new Uint8Array(await file.slice(0, HEAD_BYTES).arrayBuffer()))
  if (!chunk) return null
  if (chunk[0] === 0xff && chunk[1] === 0xd8) {
    // MJPEG AVI — 조각 하나가 JPEG 한 장이다
    const bitmap = await createImageBitmap(new Blob([chunk], { type: 'image/jpeg' }))
    return { image: bitmap, width: bitmap.width, height: bitmap.height, close: () => bitmap.close() }
  }
  const codec = avcCodec(chunk)
  if (!codec || typeof VideoDecoder === 'undefined') return null
  let frame: VideoFrame | null = null
  const decoder = new VideoDecoder({
    output: (f) => (frame ? f.close() : (frame = f)),
    error: () => {},
  })
  try {
    // description 없이 configure하면 Annex B 바이트를 그대로 받는다
    decoder.configure({ codec, optimizeForLatency: true })
    decoder.decode(new EncodedVideoChunk({ type: 'key', timestamp: 0, data: chunk }))
    await decoder.flush()
  } catch {
    ;(frame as VideoFrame | null)?.close()
    return null
  } finally {
    if (decoder.state !== 'closed') decoder.close()
  }
  const out = frame as VideoFrame | null
  return out && { image: out, width: out.displayWidth, height: out.displayHeight, close: () => out.close() }
}
