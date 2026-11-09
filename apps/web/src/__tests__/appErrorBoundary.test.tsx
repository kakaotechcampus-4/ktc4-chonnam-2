// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AppErrorBoundary } from '../components/AppErrorBoundary'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

function Broken(): never {
  throw new Error('render failed')
}

it('렌더 오류가 나면 빈 화면 대신 새로고침 안내를 보인다', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  const r = render(<AppErrorBoundary><Broken /></AppErrorBoundary>)
  expect(r.getByRole('alert').textContent).toContain('화면을 표시하지 못했어요')
  expect(r.getByRole('button', { name: '새로고침' })).toBeTruthy()
})

it('오류가 없으면 자식을 그대로 그린다', () => {
  const r = render(<AppErrorBoundary><p>정상 화면</p></AppErrorBoundary>)
  expect(r.getByText('정상 화면')).toBeTruthy()
  expect(r.queryByRole('alert')).toBeNull()
})
