/**
 * 화면 시트를 **자기 완결 HTML 한 장**으로 굽는다.
 *
 *   node scripts/build-sheet.mjs [출력경로]
 *
 * 하는 일
 *   1. `vite build`로 나온 `dist/sheet.html`을 미리보기 서버에 띄운다
 *   2. 설치된 Chrome을 headless로 돌려 `--dump-dom`으로 **JS 실행이 끝난 DOM**을 받는다
 *      (화면 자체 타이머가 다 돌고 Sheet.tsx가 DOM을 얼린 뒤의 상태)
 *   3. 스크립트를 빼고, 같은 출처 CSS·이미지를 전부 인라인하고, 폰트 CDN 링크만 남긴다
 *
 * 결과물은 파일 하나라서 그대로 Figma html.to.design의
 * 「Import from HTML code」에 붙여넣으면 된다. 서버를 띄울 필요가 없다.
 *
 * 이 스크립트는 빌드에 포함되지 않는다. 손으로 돌린다.
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, '..');
const PORT = 4178;

const OUT = process.argv[2]
  ? resolve(process.cwd(), process.argv[2])
  : resolve(APP, 'figma/daesingo-screens-sheet.html');

/** Chrome이 설치돼 있을 만한 자리. 하나라도 있으면 그걸 쓴다 */
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
].filter(Boolean);

function findChrome() {
  const hit = CHROME_CANDIDATES.find((p) => existsSync(p));
  if (!hit) {
    throw new Error(
      `Chrome을 찾지 못했다. CHROME_PATH 환경변수로 실행 파일 경로를 알려달라.\n찾아본 곳:\n  ${CHROME_CANDIDATES.join('\n  ')}`,
    );
  }
  return hit;
}

async function waitForServer(url, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // 아직 안 떴다
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`미리보기 서버가 ${timeoutMs}ms 안에 뜨지 않았다: ${url}`);
}

function dumpDom(chrome, url) {
  const res = spawnSync(
    chrome,
    [
      '--headless=new',
      '--disable-gpu',
      '--no-sandbox',
      '--hide-scrollbars',
      // 1400px보다 좁으면 global.css의 미디어 쿼리가 화면을 1단으로 접는다
      '--window-size=1600,1400',
      // 화면 자체 타이머(UploadScreen 3초 등)와 Sheet.tsx의 고정 타이머를 다 돌린다
      '--virtual-time-budget=20000',
      '--dump-dom',
      url,
    ],
    { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 },
  );
  if (res.status !== 0) {
    throw new Error(`chrome --dump-dom 실패 (exit ${res.status})\n${res.stderr}`);
  }
  return res.stdout;
}

/** `/assets/x.css` 같은 같은-출처 스타일시트를 통째로 인라인한다 */
function inlineLocalCss(html) {
  return html.replace(
    /<link[^>]+rel="stylesheet"[^>]*href="(\/[^"]+\.css)"[^>]*>/g,
    (whole, href) => {
      const file = resolve(APP, 'dist', href.replace(/^\//, ''));
      if (!existsSync(file)) return whole;
      return `<style data-from="${href}">\n${readFileSync(file, 'utf8')}\n</style>`;
    },
  );
}

/** `/meerkat.png` 같은 같은-출처 이미지를 data: URI로 바꾼다 */
function inlineLocalImages(html) {
  const MIME = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', svg: 'image/svg+xml', webp: 'image/webp' };
  return html.replace(/(src|href)="(\/[^"]+\.(png|jpe?g|gif|svg|webp))"/g, (whole, attr, path, ext) => {
    for (const base of [resolve(APP, 'dist'), resolve(APP, 'public')]) {
      const file = resolve(base, path.replace(/^\//, ''));
      if (existsSync(file)) {
        const b64 = readFileSync(file).toString('base64');
        return `${attr}="data:${MIME[ext.toLowerCase()]};base64,${b64}"`;
      }
    }
    return whole;
  });
}

function strip(html) {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '')
    .replace(/<script\b[^>]*\/>/g, '')
    // 스크립트를 뺐으므로 preload/prefetch 힌트는 죽은 참조만 남는다
    .replace(/<link[^>]+rel="(?:modulepreload|preload|prefetch)"[^>]*>/g, '')
    // 시트의 조작 UI는 Figma에 들어갈 필요가 없다
    .replace(/<div class="sheet-bar">[\s\S]*?<\/div>\s*<\/div>/, '')
    .replace(/<p class="sheet-warn">[\s\S]*?<\/p>/, '')
    .replace(/<p class="sheet-how">[\s\S]*?<\/p>/, '')
    .replace(/<!--[\s\S]*?-->/g, '');
}

// ---------------------------------------------------------------- 실행
const chrome = findChrome();

if (!existsSync(resolve(APP, 'dist/sheet.html'))) {
  throw new Error('dist/sheet.html이 없다. 먼저 `npm run build --workspace=daesingo-prototype`을 돌려라.');
}

const server = spawn('npx', ['vite', 'preview', '--port', String(PORT), '--strictPort'], {
  cwd: APP,
  stdio: 'ignore',
  shell: process.platform === 'win32',
});

try {
  const url = `http://localhost:${PORT}/sheet.html`;
  await waitForServer(url);

  let html = dumpDom(chrome, url);
  const boards = (html.match(/data-artboard="/g) ?? []).length;
  const frozen = /전부 고정됨/.test(html);

  html = strip(html);
  html = inlineLocalCss(html);
  html = inlineLocalImages(html);

  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, html, 'utf8');

  console.log(`아트보드 ${boards}장 · 고정 ${frozen ? '완료' : '미완료(확인 필요)'}`);
  console.log(`${Math.round(html.length / 1024)}KB → ${OUT}`);
  if (!frozen) process.exitCode = 1;
} finally {
  server.kill();
}
