// @vitest-environment jsdom
//
// 진입 주소: 기본은 실제 흐름, 시연은 `?demo`(· `?cases`)로만 연다(#535).

import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { App } from '../App'

vi.mock('../screens/ApiFlow', () => ({ ApiFlow: (p: { caseId?: string | null }) => <p>api {p.caseId ?? '-'}</p> }))
vi.mock('../screens/DemoFlow', () => ({ DemoFlow: (p: { casePicker?: boolean }) => <p>demo {String(!!p.casePicker)}</p> }))

afterEach(cleanup)

it.each([
  ['', 'api -'],
  ['?case=c1', 'api c1'],
  ['?api', 'api -'],
  ['?api&case=c1', 'api c1'],
  ['?demo', 'demo false'],
  ['?demo&cases', 'demo true'],
  ['?cases', 'demo true'],
])('%s → %s', (search, text) => {
  history.replaceState(null, '', `/${search}`)
  expect(render(<App />).container.textContent).toBe(text)
})
