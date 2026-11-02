// @vitest-environment jsdom
//
// 업로드 화면: 완료되면 한 줄 요약으로 줄지만, 파일 고르기 버튼은 같은 요소로 남아 포커스를
// 잃지 않고, 요약 안의 펼침은 파일 창을 열지 않는다.

import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DemoFlow } from '../screens/DemoFlow'
import { UploadScreen, type UploadState } from '../screens/UploadScreen'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const file = (name: string) => new File([''], name, { type: 'video/mp4' })

function screen(state: UploadState, files: File[] = [], skipped: string[] = []) {
  return (
    <UploadScreen
      state={state}
      files={files}
      skipped={skipped}
      situation=""
      onFiles={() => {}}
      onSituation={() => {}}
      onSearch={() => {}}
    />
  )
}

it('고르기 → 업로드 중 → 완료 동안 버튼이 같은 요소로 남아 포커스를 잃지 않는다', () => {
  const files = [file('a.mp4')]
  const r = render(screen('idle'))
  const button = r.getByText('파일 선택')
  button.focus()
  r.rerender(screen('uploading', files))
  r.rerender(screen('done', files))
  expect(r.getByText('다시 선택')).toBe(button)
  expect(document.activeElement).toBe(button)
})

it('완료 요약의 「영상 N개」 펼침과 빈 곳 클릭은 파일 창을 열지 않는다 — 「다시 선택」만 연다', () => {
  const click = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {})
  const r = render(screen('done', [file('a.mp4'), file('b.mp4')]))
  fireEvent.click(r.container.querySelector('summary')!)
  fireEvent.click(r.container.querySelector('.rs-drop')!)
  expect(click).not.toHaveBeenCalled()
  fireEvent.click(r.getByText('다시 선택'))
  expect(click).toHaveBeenCalledTimes(1)
})

it('완료 요약은 건너뛴 파일을 뺀 개수를 쓰고, 파일 이름과 건너뜀 안내를 모두 남긴다', () => {
  const r = render(screen('done', [file('a.mp4'), file('FILE_017.mp4')], ['FILE_017.mp4']))
  expect(r.container.querySelector('summary')!.textContent).toContain('업로드 완료 · 영상 1개')
  expect(r.container.querySelectorAll('.rs-files li')).toHaveLength(2)
  expect(r.container.querySelector('.skip-list')!.textContent).toContain('FILE_017.mp4')
})

it('파일이 하나면 펼침 없이 이름을 바로 보인다', () => {
  const r = render(screen('done', [file('REC_2026_09_14_LONG_NAME.mp4')]))
  expect(r.container.querySelector('details')).toBeNull()
  expect(r.container.querySelector('.rs-done-name')!.textContent).toBe('REC_2026_09_14_LONG_NAME.mp4')
})

it('성공 체크는 완료될 때 한 번 생기고, 다시 그려지거나 목록을 펼쳐도 새로 만들어지지 않는다', () => {
  const files = [file('a.mp4'), file('b.mp4')]
  const r = render(screen('done', files))
  const check = r.container.querySelector('.rs-check')
  r.rerender(screen('done', files))
  fireEvent.click(r.container.querySelector('summary')!)
  expect(r.container.querySelector('.rs-check')).toBe(check)
})

it('찾아보기 직후 진행 화면은 바로 열리고, 업로드 겉모습 복사본은 읽히지 않으며 곧 사라진다 — 새 신고면 즉시', () => {
  vi.useFakeTimers()
  try {
    const r = render(<DemoFlow />)
    fireEvent.change(r.container.querySelector('input[type=file]')!, { target: { files: [file('a.mp4')] } })
    act(() => vi.advanceTimersByTime(2000))
    fireEvent.click(r.getByText('영상에서 찾아보기'))
    const ghost = r.container.querySelector('.rs-upload-exit')!
    expect(r.container.querySelector('.rs.flow')).not.toBeNull()
    expect(ghost.getAttribute('aria-hidden')).toBe('true')
    expect(ghost.hasAttribute('inert')).toBe(true)
    // 진행 화면은 오른쪽에서 밀려 들어온다 — 출발 장면(앞·뒤 휠)은 복사본에만 있다
    expect(r.container.querySelector('.rs.flow.rs-push-in')).not.toBeNull()
    expect(ghost.querySelectorAll('.rs-depart .rs-depart-body .rs-wheel')).toHaveLength(2)
    // 「아주 화려하게」 — 연기·속도선·잔상이 함께 나온다
    expect(ghost.querySelectorAll('.rs-depart .rs-puff').length).toBeGreaterThan(10)
    expect(ghost.querySelectorAll('.rs-depart .rs-speed').length).toBeGreaterThan(0)
    expect(ghost.querySelectorAll('.rs-depart .is-ghost')).toHaveLength(3)
    // 출발(약 1초) 동안은 남아 있다가 밀려 나간 뒤 사라진다
    act(() => vi.advanceTimersByTime(900))
    expect(r.container.querySelector('.rs-upload-exit')).not.toBeNull()
    act(() => vi.advanceTimersByTime(600))
    expect(r.container.querySelector('.rs-upload-exit')).toBeNull()

    fireEvent.click(r.getByText('새 신고'))
    fireEvent.change(r.container.querySelector('input[type=file]')!, { target: { files: [file('a.mp4')] } })
    act(() => vi.advanceTimersByTime(2000))
    fireEvent.click(r.getByText('영상에서 찾아보기'))
    fireEvent.click(r.getByText('새 신고'))
    expect(r.container.querySelector('.rs-upload-exit')).toBeNull()
  } finally {
    vi.useRealTimers()
  }
})

it('업로드 연출은 실제 상태를 따른다 — 빠른 완료면 카드·열린 문이 남지 않고, 파일을 바꾸면 처음부터 다시 한다', () => {
  vi.useFakeTimers()
  try {
    const a = [file('a.mp4')]
    const r = render(screen('uploading', a))
    expect(r.container.querySelectorAll('.rs-vcard')).toHaveLength(1)
    expect(r.container.querySelector('.rs-drop.is-open')).not.toBeNull()
    r.rerender(screen('done', a)) // 탑승 연출이 끝나기 전에 완료
    expect(r.container.querySelector('.rs-vcard')).toBeNull()
    expect(r.container.querySelector('.rs-drop.is-open')).toBeNull()

    const b = [file('b.mp4'), file('c.mp4'), file('d.mp4'), file('e.mp4')]
    r.rerender(screen('uploading', b)) // 다시 선택으로 교체 — 카드는 최대 3장, 개수는 문구로
    expect(r.container.querySelectorAll('.rs-vcard')).toHaveLength(3)
    act(() => vi.advanceTimersByTime(600))
    expect(r.container.querySelector('.rs-vcard')).toBeNull()
    expect(r.container.querySelector('.upload.bg-off')).not.toBeNull() // 바퀴로 이동 — 배경 숨김
    expect(r.container.querySelector('.rs-drop.is-spinning')).not.toBeNull() // 업로드 중 휠 회전
    r.rerender(screen('fail', b))
    expect(r.container.querySelector('.upload.bg-off')).not.toBeNull()
    expect(r.container.querySelector('.rs-drop.is-spinning')).toBeNull() // 실패하면 그 각도에서 멈춤
  } finally {
    vi.useRealTimers()
  }
})

it('분석 시작은 한 번만 — 누른 뒤 남는 버튼은 누를 수 없는 출발용 복사본뿐이다', () => {
  vi.useFakeTimers()
  try {
    const r = render(<DemoFlow />)
    fireEvent.change(r.container.querySelector('input[type=file]')!, { target: { files: [file('a.mp4')] } })
    act(() => vi.advanceTimersByTime(2000))
    const go = r.getByText('영상에서 찾아보기')
    fireEvent.click(go)
    fireEvent.click(go) // 연타 — 이미 사라진 버튼
    const left = r.getAllByText('영상에서 찾아보기')
    expect(left).toHaveLength(1)
    expect(left[0].closest('.rs-upload-exit')!.hasAttribute('inert')).toBe(true)
    expect(r.container.querySelector('.rs-upload-exit .upload.is-departing .rs-depart')).not.toBeNull()
    expect(r.container.querySelectorAll('.rs.flow')).toHaveLength(1)
  } finally {
    vi.useRealTimers()
  }
})

it('휠은 바퀴 화면에 도착한 뒤 업로드 중에만 돌고, 완료되면 멈춘다 — 출발 장면은 누를 때까지 없다', () => {
  vi.useFakeTimers()
  try {
    const a = [file('a.mp4')]
    const r = render(screen('uploading', a))
    expect(r.container.querySelector('.rs-drop.is-spinning')).toBeNull() // 탑승·문 닫힘 동안은 아직
    act(() => vi.advanceTimersByTime(500))
    expect(r.container.querySelector('.rs-drop.is-spinning')).not.toBeNull()
    r.rerender(screen('done', a))
    expect(r.container.querySelector('.rs-drop.is-spinning')).toBeNull()
    expect(r.container.querySelector('.rs-depart')).toBeNull()
  } finally {
    vi.useRealTimers()
  }
})

it('업로드가 끝나면 상황 입력칸 위에 고른 원본의 파일 이름으로 찍힌 시각을 알려 주고, 건너뛴 파일과 못 읽은 이름은 따로 말한다', async () => {
  const y = new Date().getFullYear()
  const evt = file(`${y}0824_140312_EVT_1.avi`)
  const files = [evt, file('FILE_017.mp4'), file('REC_a.mp4')]
  const r = render(screen('idle'))
  fireEvent.change(r.container.querySelector('input[type=file]')!, { target: { files } })
  expect(r.container.querySelector('.rs-vtime')).toBeNull() // 끝나기 전엔 말하지 않는다
  r.rerender(screen('done', files, ['FILE_017.mp4']))
  // jsdom은 파일 내용을 못 읽어 길이 없이 시작 시각만 나온다
  const line = await r.findByText(/파일 이름 기준/)
  expect(line.closest('.rs-field')).not.toBeNull()
  expect(line.textContent).toBe(
    '올린 영상은 8월 24일 오후 2:03에 찍혔어요(파일 이름 기준). 시각을 못 읽은 파일 1개는 빠졌어요.',
  )

  fireEvent.change(r.container.querySelector('input[type=file]')!, { target: { files: [file('REC_a.mp4')] } })
  r.rerender(screen('done', [file('REC_a.mp4')]))
  expect((await r.findByText(/읽지 못했어요/)).textContent).toBe('파일 이름에서 찍힌 시각을 읽지 못했어요.')
})

it('업로드 전 「영상에서 찾아보기」는 Tab으로 닿고 못 누르는 이유가 읽히며, 눌러도 시작하지 않는다 (#509 #5)', () => {
  const onSearch = vi.fn()
  const r = render(
    <UploadScreen state="idle" files={[]} skipped={[]} situation="" onFiles={() => {}} onSituation={() => {}} onSearch={onSearch} />,
  )
  const btn = r.getByText('영상에서 찾아보기').closest('button')!
  expect(btn.disabled).toBe(false)
  expect(btn.getAttribute('aria-disabled')).toBe('true')
  expect(document.getElementById(btn.getAttribute('aria-describedby')!)!.textContent).toBe('영상을 먼저 올려 주세요.')
  fireEvent.click(btn)
  expect(onSearch).not.toHaveBeenCalled()
  r.rerender(<UploadScreen state="done" files={[file('a.mp4')]} skipped={[]} situation="" onFiles={() => {}} onSituation={() => {}} onSearch={onSearch} />)
  expect(btn.getAttribute('aria-disabled')).toBe('false')
  expect(btn.hasAttribute('aria-describedby')).toBe(false)
  fireEvent.click(btn)
  expect(onSearch).toHaveBeenCalledTimes(1)
})
