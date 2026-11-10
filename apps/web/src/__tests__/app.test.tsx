// @vitest-environment jsdom
//
// 진입 주소: 기본은 실제 흐름, 시연은 `?demo`(· `?cases`)로만 연다(#535).
// 주소에 case가 없으면 이 브라우저가 마지막으로 연 case로 이어간다.

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { App } from '../App'

vi.mock('../screens/ApiFlow', () => ({
  ApiFlow: (p: { caseId?: string | null; remembered?: boolean }) => <p>api {p.caseId ?? '-'}{p.remembered ? ' (기억)' : ''}</p>,
}))
vi.mock('../screens/OfficialSampleEntry', () => ({
  OfficialSampleEntry: (p: { caseId?: string | null; remembered?: boolean }) => <p>sample {p.caseId ?? '-'}{p.remembered ? ' (기억)' : ''}</p>,
}))
vi.mock('../screens/DemoFlow', () => ({ DemoFlow: (p: { casePicker?: boolean }) => <p>demo {String(!!p.casePicker)}</p> }))

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })))
})

it.each([
  ['', 'api - (기억)'],
  ['?case=c1', 'api c1'],
  ['?sample', 'api - (기억)'],
  ['?sample&case=c1', 'api c1'],
  ['?api', 'api - (기억)'],
  ['?api&case=c1', 'api c1'],
  ['?demo', 'demo false'],
  ['?demo&cases', 'demo true'],
  ['?cases', 'demo true'],
])('%s → %s', async (search, text) => {
  history.replaceState(null, '', `/${search}`)
  render(<App />)
  expect(await screen.findByText(text)).toBeTruthy()
})

it('주소에 case가 없으면 기억한 case로 이어가고, 주소의 case가 기억보다 앞선다', async () => {
  localStorage.setItem('daesingo.lastCase', 'c9')
  history.replaceState(null, '', '/')
  render(<App />)
  expect(await screen.findByText('api c9 (기억)')).toBeTruthy()
  cleanup()
  history.replaceState(null, '', '/?case=c1')
  render(<App />)
  expect(await screen.findByText('api c1')).toBeTruthy()
})

it('공개 모드에서는 /와 이전 sample 주소가 같은 입구이고 case는 보존한다', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ upload_enabled: true, retention_ttl_sec: 86400 })))
  history.replaceState(null, '', '/?sample&case=c1')
  render(<App />)
  expect(await screen.findByText('sample c1')).toBeTruthy()
  expect(location.search).toBe('?case=c1')
})
