// A11Y-08 — 접근성 브라우저 E2E. 시연 흐름(`?demo`, mock fixture)을 마우스 없이 지난다.
// 다루는 것: E2E-01(키보드 완주) · 02(focus 표시) · 03(이름 있는 조작 요소) · 05 일부(업로드 상태 aria-live). 04(색 외 구분)는 아직 없다.
// 실제 분석·배포 서버는 쓰지 않는다 — 그 확인은 배포본 수동 완주 기록이 맡는다.
import { expect, test, type Locator, type Page } from '@playwright/test'

/** focus 표시에 쓰이는 값. 투명한 outline은 보이지 않으므로 없는 것으로 친다 */
const ringOf = (el: Element) => {
  const s = getComputedStyle(el)
  const transparent = /rgba\(.*,\s*0\)$/.test(s.outlineColor) || s.outlineColor === 'transparent'
  const outline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 && !transparent ? `${s.outlineStyle} ${s.outlineWidth} ${s.outlineColor}` : ''
  return [outline, s.boxShadow, s.borderColor].join(' | ')
}

/** Tab만 눌러 target에 닿는다(E2E-01). 닿기 전과 비교해 focus 표시가 실제로 바뀌어야 한다(E2E-02) —
 *  평소에도 있는 그림자나 투명 outline만으로는 통과하지 않는다(#623 리뷰). */
async function tabTo(page: Page, target: Locator, max = 80) {
  for (let i = 0; i < max; i++) {
    const before = await target.evaluate(ringOf)
    await page.keyboard.press('Tab')
    if (await target.evaluate((el) => el === document.activeElement)) {
      expect(await target.evaluate(ringOf), 'focus 표시가 보여야 한다').not.toBe(before)
      return
    }
  }
  throw new Error(`Tab ${max}번 안에 닿지 않음: ${target}`)
}

/** 이름 없는 버튼·링크·입력이 없어야 한다(E2E-03). */
async function expectNamedControls(page: Page) {
  const unnamed = await page.evaluate(() =>
    [...document.querySelectorAll('button, a[href], input:not([type=hidden]):not([hidden]), select, textarea, [role=button]')]
      // offsetParent는 position: fixed 요소에서 늘 null이라, 겹쳐 뜨는 화면(모달 등)도 검사하도록 그려진 상자로 본다(#623 리뷰)
      .filter((el) => el.getClientRects().length > 0)
      .filter((el) => {
        const labelledby = el.getAttribute('aria-labelledby')
        const fromIds = labelledby?.split(' ').map((id) => document.getElementById(id)?.textContent ?? '').join('')
        const label = (el as HTMLInputElement).labels?.[0]?.textContent
        const name = el.getAttribute('aria-label') || fromIds || label || el.getAttribute('title') || (el as HTMLElement).innerText || el.querySelector('img[alt]')?.getAttribute('alt')
        return !name?.trim()
      })
      .map((el) => el.outerHTML.slice(0, 120)),
  )
  expect(unnamed).toEqual([])
}

test('키보드로 업로드 → 진행 → 결과 → 안전신문고 이동까지 간다', async ({ page }) => {
  // 외부 사이트의 응답 지연과 키보드 동작을 분리한다. 실제 window.open은 그대로 실행한다.
  await page.context().route('https://www.safetyreport.go.kr/**', route => route.fulfill({
    status: 200, contentType: 'text/html', body: '<!doctype html><title>Offline destination</title>',
  }))
  await page.goto('/?demo')
  await expectNamedControls(page)

  // 파일 고르기: Tab으로 「파일 선택」에 닿아 Enter. 열린 OS 파일 창은 브라우저 밖이라 파일을 직접 넣는다
  const chooser = page.waitForEvent('filechooser')
  await tabTo(page, page.getByRole('button', { name: '파일 선택' }))
  await page.keyboard.press('Enter')
  await (await chooser).setFiles({ name: 'a.mp4', mimeType: 'video/mp4', buffer: Buffer.from('') })

  // 업로드 상태는 aria-live로 읽힌다(E2E-05)
  await expect(page.locator('[aria-live]').filter({ hasText: '업로드 완료' })).toBeVisible()
  await tabTo(page, page.getByRole('button', { name: '영상에서 찾아보기' }))
  await page.keyboard.press('Enter')

  // 진행 화면
  await expect(page.getByText('경과 시간')).toBeVisible()

  // 결과(또는 상황 확인) 화면까지 기다린다
  const answer = page.getByRole('button', { name: '맞아요' })
  const ready = page.getByRole('button', { name: /안전신문고/ })
  await expect(answer.or(ready)).toBeVisible({ timeout: 30_000 })
  if (await answer.isVisible()) {
    await tabTo(page, answer)
    await page.keyboard.press('Enter')
  }
  await expect(ready).toBeVisible({ timeout: 30_000 })
  await expectNamedControls(page)

  // 하위 화면에 들어갔다가 키보드로 돌아온다
  await tabTo(page, page.getByRole('button', { name: '어떻게 정했는지' }))
  await page.keyboard.press('Enter')
  const back = page.locator('.sub-back')
  await expect(back).toBeVisible()
  await expectNamedControls(page)
  await tabTo(page, back)
  await page.keyboard.press('Enter')
  await expect(ready).toBeVisible()

  // 안전신문고 이동은 새 창을 연다
  await expect(ready).toBeEnabled()
  const popup = page.waitForEvent('popup')
  await tabTo(page, ready)
  await expect(ready).toBeFocused()
  await page.keyboard.press('Enter')
  const destination = await popup
  await expect(destination).toHaveURL('https://www.safetyreport.go.kr/')
  expect(await destination.evaluate(() => window.opener)).toBeNull()
  await destination.close()
})

test('파일을 고르기 전 「영상에서 찾아보기」는 못 누르는 이유를 보조기기에 알린다', async ({ page }) => {
  await page.goto('/?demo')
  const search = page.getByRole('button', { name: '영상에서 찾아보기' })
  await expect(search).toHaveAttribute('aria-disabled', 'true')
  await expect(search).toHaveAccessibleDescription(/.+/)
})
