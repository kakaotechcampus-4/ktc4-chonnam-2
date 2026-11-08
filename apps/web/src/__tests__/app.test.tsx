// @vitest-environment jsdom
//
// 진입 주소: 기본은 실제 흐름, 시연은 `?demo`(· `?cases`)로만 연다(#535).
// 주소에 case가 없으면 이 브라우저가 마지막으로 연 case로 이어간다.

import { cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { App } from '../App'

vi.mock('../screens/ApiFlow', () => ({
  ApiFlow: (p: { caseId?: string | null; remembered?: boolean }) => <p>api {p.caseId ?? '-'}{p.remembered ? ' (기억)' : ''}</p>,
}))
vi.mock('../screens/OfficialSampleEntry', () => ({
  OfficialSampleEntry: (p: { caseId?: string | null; remembered?: boolean }) => <p>sample {p.caseId ?? '-'}{p.remembered ? ' (기억)' : ''}</p>,
}))
vi.mock('../screens/DemoFlow', () => ({ DemoFlow: (p: { casePicker?: boolean }) => <p>demo {String(!!p.casePicker)}</p> }))

afterEach(cleanup)
beforeEach(() => localStorage.clear())

it.each([
  ['', 'api - (기억)'],
  ['?case=c1', 'api c1'],
  ['?sample', 'sample - (기억)'],
  ['?sample&case=c1', 'sample c1'],
  ['?api', 'api - (기억)'],
  ['?api&case=c1', 'api c1'],
  ['?demo', 'demo false'],
  ['?demo&cases', 'demo true'],
  ['?cases', 'demo true'],
])('%s → %s', (search, text) => {
  history.replaceState(null, '', `/${search}`)
  expect(render(<App />).container.textContent).toBe(text)
})

it('주소에 case가 없으면 기억한 case로 이어가고, 주소의 case가 기억보다 앞선다', () => {
  localStorage.setItem('daesingo.lastCase', 'c9')
  history.replaceState(null, '', '/')
  expect(render(<App />).container.textContent).toBe('api c9 (기억)')
  cleanup()
  history.replaceState(null, '', '/?case=c1')
  expect(render(<App />).container.textContent).toBe('api c1')
})
