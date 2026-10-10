// @vitest-environment jsdom
//
// 시연 흐름: 파일 선택·버튼과 작업 상태 변화로만 화면이 넘어간다.

import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { SNAPSHOTS } from '../contracts/fixtures'
import { DemoFlow } from '../screens/DemoFlow'
import { ResultScreen } from '../screens/ResultScreen'

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function start(caseKey: string) {
  const r = render(<DemoFlow />)
  fireEvent.change(r.container.querySelector('select')!, { target: { value: caseKey } })
  fireEvent.change(r.container.querySelector('input[type=file]')!, {
    target: { files: [new File([''], 'a.mp4', { type: 'video/mp4' })] },
  })
  const text = () => r.container.querySelector('main')!.textContent!
  // 다음 타이머는 렌더 뒤 effect가 건다 — 한 번에 한 단계씩 흘린다.
  const wait = () => {
    for (let i = 0; i < 20; i++) act(() => vi.advanceTimersByTime(5_000))
  }
  return { ...r, text, wait }
}

it('정상: 업로드 완료 → 진행 → 결과, 하위 화면은 「<」로 돌아온다', () => {
  const { text, wait, getByText, container } = start('main')
  expect(text()).toContain('업로드 중')
  wait()
  expect(text()).toContain('업로드 완료 · 영상 1개')
  fireEvent.click(getByText('영상에서 찾아보기'))
  expect(text()).toContain('경과 시간')
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
  // 신고 양식 순서. 발생 일시는 일자·시간으로 나눈다. 위치는 지도 없이 값·검색어만 있다
  const labels = [...container.querySelectorAll('.res-item-k')].map((h) => h.textContent)
  expect(labels).toEqual(['유형', '동영상', '위치 선택', '제목', '신고 내용', '차량 번호', '발생 일자', '발생 시간'])
  expect(text()).toContain('2026-08-24')
  expect(text()).toContain('18:05:12')
  expect(text()).not.toContain('T18:05')
  fireEvent.click(getByText('어떻게 정했는지'))
  expect(text()).toContain('어떻게 정했는지')
  fireEvent.click(container.querySelector('.sub-back')!)
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('번호판 판독 실패: 진행은 끝까지 흐르고 결과 화면에서 알리며 제출을 막는다', () => {
  const { wait, getByText, text } = start('plateFailed')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('신고자료를 완성하지 못했어요')
  expect(text()).toContain('번호판 판독에 실패했습니다')
  // package가 없으니 초안·제출 버튼은 없고, notice와 다시 시도만 있다
  expect(text()).not.toContain('안전신문고로 이동')
  // 번호판 다시 읽기 → 번호판부터 다시 진행해 정상 결과로 끝난다
  fireEvent.click(getByText('번호판 다시 읽기'))
  expect(text()).toContain('경과 시간')
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('위반 미관찰: 후보 확인에서 멈추고 번호판 판독은 시작하지 않는다', () => {
  const { wait, getByText, text, container } = start('notObserved')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  const seen = new Set<string>()
  for (let i = 0; i < 20; i++) {
    container.querySelectorAll('.tl-running .tl-label, .tl-done .tl-label').forEach((el) => seen.add(el.textContent!))
    act(() => vi.advanceTimersByTime(5_000))
  }
  expect(seen.has('후보 확인')).toBe(true)
  expect(seen.has('번호판 판독')).toBe(false)
  expect(text()).toContain('위반을 확인하지 못했어요')
})

it('결과 없음: 아래에서 다시 적고 다시 찾으면 새로 진행한다', () => {
  const { wait, getByText, text, container } = start('notFound')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('말씀하신 장면을 찾지 못했어요')
  const box = container.querySelector('textarea')!
  fireEvent.change(box, { target: { value: '' } })
  fireEvent.keyDown(box, { key: 'Tab' })
  expect(box.value).toContain('검은 승용차')
  fireEvent.click(getByText('다시 찾기'))
  expect(text()).toContain('경과 시간')
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('다른 후보: 기준 후보를 같이 놓되 버튼은 다른 후보에만 달고, 고르면 다시 준비한다', () => {
  const { wait, getByText, getAllByText, text, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('다른 후보 영상 2'))
  expect(container.querySelectorAll('.cand')).toHaveLength(3)
  expect(text()).toContain('지금 신고자료 기준')
  expect(container.querySelector('.hint-recall')).not.toBeNull()
  expect(getAllByText('이 장면으로 다시 준비')).toHaveLength(2)
  // 2번 후보를 고르면 다시 준비한 뒤 2번이 기준 후보가 된다
  fireEvent.click(container.querySelector('.cand-col button')!)
  expect(text()).toContain('경과 시간')
  wait()
  fireEvent.click(getByText('다른 후보 영상 2'))
  const cards = [...container.querySelectorAll('.cand')]
  expect(cards.map((c) => c.classList.contains('sel'))).toEqual([false, true, false])
})

it('업로드 실패: 다시 선택하면 다시 올린다', () => {
  const { wait, text } = start('uploadFail')
  wait()
  expect(text()).toContain('업로드 실패')
  expect(text()).toContain('다시 선택')
  expect(text()).toContain('파일을 올리지 못했어요')
})

it('설명이 비어 있으면 Tab이 예시를 채우고, 「새 신고」는 처음 화면으로 돌아간다', () => {
  const { container, getByText, text, wait } = start('main')
  const box = container.querySelector('textarea')!
  fireEvent.keyDown(box, { key: 'Tab' })
  expect(box.value).toContain('흰색 SUV')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
  fireEvent.click(getByText('새 신고'))
  expect(text()).toContain('블랙박스 영상을 올려주세요')
  expect(container.querySelector('textarea')!.value).toBe('')
})

it('상단 로고(대신고)를 누르면 진행 중이어도 첫 화면으로 돌아간다', () => {
  const { container, getByText, getByLabelText, text, wait } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  expect(container.querySelector('.rs.flow')).not.toBeNull()
  fireEvent.click(getByLabelText('대신고 첫 화면으로'))
  expect(container.querySelector('.rs.flow')).toBeNull()
  expect(text()).toContain('블랙박스 영상을 올려주세요')
  expect(container.querySelector('textarea')!.value).toBe('')
})

it('번호판은 자세히 보기에서 읽은 값을 채운 채 고치고, 결과 화면에 「사용자 확인됨」으로 반영된다', () => {
  const { wait, getByText, text, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('자세히 보기'))
  expect(text()).toContain('번호판을 읽은 장면')
  fireEvent.click(getByText('번호 수정'))
  const input = container.querySelector('.plate-input') as HTMLInputElement
  expect(input.value).toBe('12가3456')
  fireEvent.change(input, { target: { value: '12가3458' } })
  fireEvent.click(getByText('저장'))
  expect(text()).toContain('12가3458')
  fireEvent.click(container.querySelector('.sub-back')!)
  expect(text()).toContain('12가3458')
  expect(text()).toContain('사용자 확인됨')
})

it('복사 버튼은 붙여넣을 칸과 위치 검색어에만 있다', () => {
  const { wait, getByText, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  const items = [...container.querySelectorAll('.res-item')]
  const withCopy = items.filter((r) => r.querySelector('button[aria-label$="복사"]')).map((r) => r.querySelector('.res-item-k')!.textContent)
  // 붙여넣을 것(신고 내용·차량 번호)과 위치 검색어만 복사한다. 직접 고를 칸에는 복사 버튼이 없다.
  // 정상 fixture는 검색어가 없다(search_keyword null + evidence.location_search_keyword_missing) — 그러면 위치에도 복사가 없다
  expect(withCopy).toEqual(['신고 내용', '차량 번호'])
})

it('위치 검색어가 있으면 위치 칸에 검색어 복사가 붙는다', () => {
  const happy = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.view.stage === 'READY' && s.view.package !== null)!.view
  const view = { ...happy, evidence: { ...happy.evidence!, location_display: { ...happy.evidence!.location_display, search_keyword: '광주 상무지구 상무중앙로 사거리' } } }
  const { container, getByRole } = render(<ResultScreen view={view} onCandidates={vi.fn()} onPlate={vi.fn()} onDetails={vi.fn()} onAction={vi.fn()} canRun={() => true} />)
  expect(getByRole('button', { name: '검색어 복사' })).toBeTruthy()
  expect(container.querySelector('.res-keyword-v')!.textContent).toBe('광주 상무지구 상무중앙로 사거리')
  expect(container.querySelector('.res-keyword-missing')).toBeNull()
})

it('검색어를 못 만들었다는 안내는 위 목록이 아니라 위치 칸의 검색어 자리에 있다', () => {
  const happy = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.view.stage === 'READY' && s.view.package !== null)!.view
  expect(happy.notices.some((n) => n.code === 'evidence.location_search_keyword_missing')).toBe(true)
  const { container } = render(<ResultScreen view={happy} onCandidates={vi.fn()} onPlate={vi.fn()} onDetails={vi.fn()} onAction={vi.fn()} canRun={() => true} />)
  const head = container.querySelector('.res-notices')?.textContent ?? ''
  expect(head).not.toContain('검색어')
  const row = [...container.querySelectorAll('.res-item')].find((r) => r.querySelector('.res-item-k')!.textContent === '위치 선택')!
  expect(row.querySelector('.res-keyword-missing')!.textContent).toContain('지도에 붙여넣을 검색어를 만들지 못했습니다')
  expect(row.querySelector('.res-keyword')).toBeNull()
})

it('직접 고르는 칸은 칸 이름 아래 「직접 선택」만 달고, 복사는 값과 같은 줄에 둔다', () => {
  const happy = SNAPSHOTS.find((s) => s.scenarioId === 'scenario_happy_001' && s.view.stage === 'READY' && s.view.package !== null)!.view
  const { container } = render(<ResultScreen view={happy} onCandidates={vi.fn()} onPlate={vi.fn()} onDetails={vi.fn()} onAction={vi.fn()} canRun={() => true} />)
  const picked = [...container.querySelectorAll('.res-item')]
    .filter((r) => r.querySelector('.res-item-pick'))
    .map((r) => r.querySelector('.res-item-k')!.textContent)
  expect(picked).toEqual(['유형', '위치 선택', '발생 일자', '발생 시간'])
  expect(container.textContent).not.toContain('안전신문고에서 직접 골라요')
  expect(container.querySelector('.res-val-line [aria-label="신고 내용 복사"]')).not.toBeNull()
  expect(container.querySelector('.res-plate-meta [aria-label="차량 번호 복사"]')).not.toBeNull()
})

it('번호판 못 읽음: 경고만 달고 제출은 막지 않는다', () => {
  const { wait, getByText, text } = start('plateUnread')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
  expect(text()).toContain('번호판을 확정하지 못했습니다')
  expect((getByText('안전신문고로 이동') as HTMLButtonElement).disabled).toBe(false)
})

it('신고용 영상 미생성: 제출을 막고 「신고용 영상 만들기」로 만든다', () => {
  const { wait, getByText, text } = start('videoNotGenerated')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('신고자료를 완성하지 못했어요')
  expect(text()).toContain('신고용 영상이 아직 만들어지지 않았습니다')
  expect((getByText('안전신문고로 이동') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(getByText('신고용 영상 만들기'))
  expect(text()).toContain('신고용 영상을 만들고 있어요')
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('장면 찾기 실패: 실패 화면에서 「다시 찾기」로 이어서 찾는다', () => {
  const { wait, getByText, text } = start('searchFailed')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('영상을 살펴보다가 문제가 생겼어요')
  fireEvent.click(getByText('다시 찾기'))
  expect(text()).toContain('장면을 다시 찾고 있어요')
  wait()
  expect(text()).toContain('신고자료가 준비됐어요')
})

it('업로드 일부 실패: 건너뛴 파일을 알리고 나머지로 계속한다', () => {
  const { wait, getByText, text } = start('uploadPartial')
  wait()
  expect(text()).toContain('FILE_017.mp4')
  expect((getByText('영상에서 찾아보기') as HTMLButtonElement).disabled).toBe(false)
})

it('다른 후보를 고르면 「새 후보 기준으로」 다시 준비한다고 말한다', () => {
  const { wait, getByText, text, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('다른 후보 영상 2'))
  fireEvent.click(container.querySelector('.cand-col button')!)
  expect(text()).toContain('새 후보 기준으로 신고자료를 다시 준비하고 있어요')
})

it('위반 미관찰: 다른 후보를 버튼 없이 바로 펼쳐 둔다', () => {
  const { wait, getByText, getAllByText, container } = start('notObserved')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(container.querySelectorAll('.cand')).toHaveLength(3)
  expect(getAllByText('이 장면으로 다시 준비')).toHaveLength(2)
})

it('번호판 수정: 취소·Esc·뒤로는 고치던 글자만 버리고, 저장한 값은 AI가 읽은 값과 함께 남는다', () => {
  const { wait, getByText, queryByText, text, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('자세히 보기'))
  const input = () => container.querySelector('.plate-input') as HTMLInputElement
  fireEvent.click(getByText('번호 수정'))
  fireEvent.change(input(), { target: { value: '99허9999' } })
  fireEvent.click(getByText('취소'))
  expect(text()).not.toContain('99허9999')
  fireEvent.click(getByText('번호 수정'))
  fireEvent.change(input(), { target: { value: '88하8888' } })
  fireEvent.keyDown(input(), { key: 'Escape' })
  expect(input()).toBeNull()
  expect(text()).not.toContain('88하8888')
  expect(queryByText('AI가 읽은 값')).toBeNull()
  fireEvent.click(getByText('번호 수정'))
  fireEvent.change(input(), { target: { value: '12가3457' } })
  fireEvent.submit(input().form!)
  expect(text()).toContain('AI가 읽은 값 12가3456')
  // 고치는 중에 뒤로 — 저장한 값(12가3457)이 남는다
  fireEvent.click(getByText('번호 수정'))
  fireEvent.change(input(), { target: { value: '77가7777' } })
  fireEvent.click(container.querySelector('.sub-back')!)
  expect(container.querySelector('.res-plate-v')!.textContent).toBe('12가3457')
  expect(text()).not.toContain('77가7777')
})

it('안전신문고로 이동은 준비됐을 때만 새 창으로 열고, 대신고 화면은 그대로 둔다', () => {
  const opened = vi.spyOn(window, 'open').mockReturnValue(null)
  const { wait, getByText, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('안전신문고로 이동'))
  expect(opened).toHaveBeenCalledWith('https://www.safetyreport.go.kr/', '_blank', 'noopener')
  expect(container.querySelector('.rs.result')).not.toBeNull()
})

it('신고용 영상 미생성이면 안전신문고로 이동·전체 복사를 막는다', () => {
  const { wait, getByText } = start('videoNotGenerated')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect((getByText('안전신문고로 이동').closest('button') as HTMLButtonElement).disabled).toBe(true)
  expect((getByText('붙여넣을 내용 전체 복사') as HTMLButtonElement).disabled).toBe(true)
})

it('복사 결과를 한 줄로 알린다 — 실패도 알린다', async () => {
  const writeText = vi.fn().mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error('denied'))
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  const { wait, getByText, getByLabelText, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  await act(async () => fireEvent.click(getByLabelText('차량 번호 복사')))
  expect(writeText).toHaveBeenCalledWith('12가3456')
  expect(container.querySelector('.res-toast')!.textContent).toBe('복사했습니다')
  await act(async () => fireEvent.click(getByText('붙여넣을 내용 전체 복사')))
  expect(container.querySelector('.res-toast')!.textContent).toContain('복사하지 못했어요')
  act(() => vi.advanceTimersByTime(2_000))
  expect(container.querySelector('.res-toast')!.textContent).toBe('')
})

it('위반 미관찰: 1순위 카드는 신고자료 기준이 아니라 「먼저 확인한 장면」이다', () => {
  const { wait, getByText, text } = start('notObserved')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect(text()).toContain('먼저 확인한 장면')
  expect(text()).not.toContain('지금 신고자료 기준')
})

it('후보 A → B: A의 번호판·일시·장소·내용·검색어·영상·수정값이 B의 자료로 남지 않는다', () => {
  const { wait, getByText, getAllByText, container, text } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  // A에서 번호판을 고쳐 둔다
  fireEvent.click(getByText('자세히 보기'))
  fireEvent.click(getByText('번호 수정'))
  fireEvent.change(container.querySelector('.plate-input')!, { target: { value: '12가3457' } })
  fireEvent.click(getByText('저장'))
  fireEvent.click(container.querySelector('.sub-back')!)
  // B(2번)로 바꾼다
  fireEvent.click(getByText('다른 후보 영상 2'))
  fireEvent.click(getAllByText('이 장면으로 다시 준비')[0])
  wait()
  expect(container.querySelector('.rs.result')).not.toBeNull()
  for (const a of ['12가3456', '12가3457', '2026-08-24', '18:05:12', '상무중앙로', '광주 상무지구', '흰색 SUV가 편도', '교통위반', '영상 파일을 내려받는']) {
    expect(text()).not.toContain(a)
  }
  // 값은 모두 알 수 없음, 복사·이동·다운로드는 열리지 않는다
  expect(text()).toContain('신고자료를 완성하지 못했어요')
  expect(text()).toContain('신고용 영상이 아직 없어요')
  expect(container.querySelectorAll('button[aria-label$="복사"]')).toHaveLength(0)
  expect(text()).not.toContain('안전신문고로 이동')
  expect((getByText('신고용 영상 다운로드').closest('button') as HTMLButtonElement).disabled).toBe(true)
  // 사건 전체 값(기억 단서)은 그대로, 기준 후보는 2번
  fireEvent.click(getByText('다른 후보 영상 2'))
  expect(container.querySelector('.hint-recall')!.textContent).toContain('흰색 SUV')
  expect(container.querySelector('.cand.sel .cnum')!.textContent).toBe('2')
})

it('후보를 바꾸는 중에 이전 진행의 남은 타이머가 와도 새 후보 화면을 덮지 않는다', () => {
  const { wait, getByText, getAllByText, container } = start('main')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  act(() => vi.advanceTimersByTime(1_300)) // 진행 중
  fireEvent.click(getByText('새 신고'))
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File([''], 'b.mp4')] } })
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('다른 후보 영상 2'))
  fireEvent.click(getAllByText('이 장면으로 다시 준비')[1]) // 3번
  wait()
  fireEvent.click(getByText('다른 후보 영상 2'))
  expect(container.querySelector('.cand.sel .cnum')!.textContent).toBe('3')
})

it('「번호판 직접 입력」 notice는 번호판 고치는 칸을 바로 열고, 고친 값은 화면에서만 바뀐 것이라 알린다', () => {
  const { wait, getByText, container, text } = start('plateUnread')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  fireEvent.click(getByText('번호판 직접 입력'))
  const input = container.querySelector('.plate-input') as HTMLInputElement
  expect(document.activeElement).toBe(input)
  fireEvent.change(input, { target: { value: '34나5678' } })
  fireEvent.submit(input.form!)
  expect(text()).toContain('서버에는 아직 저장되지 않아요')
  fireEvent.click(container.querySelector('.sub-back')!)
  expect(container.querySelector('.res-plate-v')!.textContent).toBe('34나5678')
  expect(text()).toContain('서버에는 아직 저장되지 않아요')
})

it('실제 데이터의 시각 notice: 연결 안 된 「시각 직접 입력」「시각 확인하기」는 사용 불가와 이유를 보이고, 제출은 막지 않는다', () => {
  const { wait, getByText, getAllByText } = start('timeReview')
  wait()
  fireEvent.click(getByText('영상에서 찾아보기'))
  wait()
  expect((getByText('시각 직접 입력').closest('button') as HTMLButtonElement).disabled).toBe(true)
  expect((getByText('시각 확인하기').closest('button') as HTMLButtonElement).disabled).toBe(true)
  expect(getAllByText('아직 이 화면에서 할 수 없어요')).toHaveLength(2)
  expect((getByText('안전신문고로 이동').closest('button') as HTMLButtonElement).disabled).toBe(false)
})
