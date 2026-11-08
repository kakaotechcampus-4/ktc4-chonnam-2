import { defineConfig, devices } from '@playwright/test'

// 접근성 브라우저 E2E(A11Y-08). 서버 없이 `?demo` 시연 흐름(mock fixture)을 실제 브라우저에서 키보드로 지난다.
export default defineConfig({
  testDir: 'e2e',
  // vitest가 *.spec.ts를 집어 가지 않게 이름을 따로 둔다
  testMatch: '*.e2e.ts',
  timeout: 60_000,
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL: 'http://localhost:5199', locale: 'ko-KR', trace: 'retain-on-failure' },
  // PW_CHANNEL=chrome이면 설치된 Chrome을 쓴다(로컬). CI는 비워 두어 Playwright Chromium을 쓴다
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], channel: process.env.PW_CHANNEL } }],
  webServer: { command: 'npx vite --port 5199 --strictPort', url: 'http://localhost:5199', reuseExistingServer: !process.env.CI },
})
