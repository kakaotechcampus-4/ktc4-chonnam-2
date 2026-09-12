import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// 입력 경로는 `root`(= 이 폴더) 기준 상대 경로다. `node:path`/`__dirname`을 쓰지 않는 이유는
// 이 워크스페이스에 `@types/node`가 없어서 `tsc -b`가 그 둘을 모른다.
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        // 프로토타입 본체
        index: 'index.html',
        // 모든 화면·상태를 한 페이지에 늘어놓은 Figma 반입용 시트 (src/sheet/)
        sheet: 'sheet.html',
      },
    },
  },
})
