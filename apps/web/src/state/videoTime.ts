// 고른 영상이 언제 찍혔는지 — 업로드 화면에서 「어제 오후 1시」 대신 실제 시각을 보고 상황을 적게
// 돕는 안내다. 서버의 시각 판정(recording)과 별개이고 서버로 보내지 않는다. 블랙박스 시계가 틀릴 수
// 있어 화면에는 「파일 이름 기준」으로만 보인다.

// 파일명 규칙은 서버(src/daesingo/recording/time_sources.py)가 읽는 두 가지와 같다.
// 시간대는 바꾸지 않는다 — 파일 이름에 적힌 숫자를 그대로 보인다.
const EVT = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_EVT_\d+\.avi$/i
const MDR = /^MDR_(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.avi$/i

// 블랙박스는 1분 남짓씩 끊어 저장하고 파일 사이가 몇 초 빈다 — 이만큼은 이어진 녹화로 본다.
const JOIN_GAP_MS = 10_000
const MAX_SHOWN = 3

export function filenameTime(name: string): Date | null {
  const m = EVT.exec(name) ?? MDR.exec(name)
  if (!m) return null
  const [y, mo, d, h, mi, s] = m.slice(1).map(Number)
  // MDR 두 자리 연도는 20xx로 본다. 서버는 세기를 설정으로 받는다(mdr_century)
  const t = new Date(m[1].length === 2 ? 2000 + y : y, mo - 1, d, h, mi, s)
  // 13월·25시처럼 넘친 값은 Date가 다음 칸으로 굴리므로, 되돌려 비교해 버린다
  const same = t.getMonth() === mo - 1 && t.getDate() === d && t.getHours() === h && t.getMinutes() === mi && t.getSeconds() === s
  return same ? t : null
}

/** AVI 머리(avih, 1GB 넘는 OpenDML이면 dmlh)의 프레임 수 × 프레임 간격. 못 읽으면 null */
export async function aviSeconds(file: Blob): Promise<number | null> {
  try {
    const b = new DataView(await file.slice(0, 64 * 1024).arrayBuffer())
    const tag = (at: number) => String.fromCharCode(b.getUint8(at), b.getUint8(at + 1), b.getUint8(at + 2), b.getUint8(at + 3))
    if (b.byteLength < 12 || tag(0) !== 'RIFF' || tag(8) !== 'AVI ') return null
    let usPerFrame = 0
    let frames = 0
    // 머리 목록(hdrl)만 본다 — 영상 데이터(movi)에 우연히 같은 글자가 있을 수 있다
    for (let i = 12; i + 28 <= b.byteLength; i++) {
      const t = tag(i)
      if (t === 'movi') break
      if (t === 'avih') {
        usPerFrame = b.getUint32(i + 8, true)
        frames = b.getUint32(i + 24, true)
      } else if (t === 'dmlh') {
        // 1GB를 넘지 않으면 0으로 비워 두는 기록기가 있다(ffmpeg) — 그때는 avih 값을 쓴다
        frames = b.getUint32(i + 8, true) || frames
      }
    }
    return usPerFrame && frames ? (usPerFrame * frames) / 1e6 : null
  } catch {
    return null
  }
}

export type Span = { start: Date; end: Date }
export type VideoTime = { spans: Span[]; unread: number }

/** 이어진 녹화끼리 묶은 구간. 길이를 못 읽은 파일은 시작 시각 한 점이다 */
export async function videoTime(files: File[]): Promise<VideoTime> {
  const read = await Promise.all(
    files.map(async (f) => {
      const start = filenameTime(f.name)
      if (!start) return null
      const sec = await aviSeconds(f)
      return { start, end: new Date(start.getTime() + (sec ?? 0) * 1000) }
    }),
  )
  const spans: Span[] = []
  for (const s of read.filter((r) => r !== null).sort((a, b) => a.start.getTime() - b.start.getTime())) {
    const last = spans[spans.length - 1]
    if (last && s.start.getTime() - last.end.getTime() <= JOIN_GAP_MS) {
      if (s.end > last.end) last.end = s.end
    } else spans.push(s)
  }
  return { spans, unread: read.filter((r) => r === null).length }
}

function when(d: Date, withDate: boolean): string {
  return d.toLocaleString('ko-KR', {
    // 블랙박스 시계가 초기화되면 2000년 같은 해가 나온다 — 올해가 아니면 해를 보여 알아채게 한다
    ...(withDate && d.getFullYear() !== new Date().getFullYear() ? { year: 'numeric' } : {}),
    ...(withDate ? { month: 'long', day: 'numeric' } : {}),
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** 「8월 24일 오후 2:03 ~ 오후 2:15」 — 날이 바뀌면 끝에도 날짜를 붙인다 */
export function videoTimeText(v: VideoTime): string | null {
  if (!v.spans.length) return null
  const parts = v.spans.slice(0, MAX_SHOWN).map(({ start, end }) =>
    end.getTime() - start.getTime() < 60_000
      ? when(start, true)
      : `${when(start, true)} ~ ${when(end, start.toDateString() !== end.toDateString())}`,
  )
  const more = v.spans.length - MAX_SHOWN
  return parts.join(', ') + (more > 0 ? ` 외 ${more}구간` : '')
}
