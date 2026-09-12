import { createRoot } from 'react-dom/client'
import '../styles/tokens.css'
import '../styles/global.css'
import './sheet.css'
import Sheet from './Sheet'

// StrictMode를 쓰지 않는다 — 이중 마운트가 Freeze의 타이머를 두 번 돌려서
// 「고정 중 n/19」 카운트가 실제보다 높게 올라간다.
createRoot(document.getElementById('sheet-root')!).render(<Sheet />)
