// @vitest-environment jsdom
//
// 업로드 화면: 완료되면 한 줄 요약으로 줄지만, 파일 고르기 버튼은 같은 요소로 남아 포커스를
// 잃지 않고, 요약 안의 펼침은 파일 창을 열지 않는다.

import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
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
