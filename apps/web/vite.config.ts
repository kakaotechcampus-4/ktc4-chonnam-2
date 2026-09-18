import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// data/mock/case/*.json을 저장소 원본 그대로 읽는다. 복사본을 두면 fixture가
// 갱신될 때 화면이 옛 값을 그린다 — 「web은 CaseView를 그대로 소비한다」의 증빙이
// 사본이 되어서는 안 된다. 그래서 루트 밖 읽기를 열어 둔다.
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: ['../..'] } },
})
