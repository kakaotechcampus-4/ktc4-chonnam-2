/**
 * 현재 문서를 **자기 완결 HTML 한 장**으로 굳힌다.
 *
 * html.to.design의 「Import from HTML code」는 붙여넣은 문자열만 보고 렌더한다.
 * 그래서 스크립트를 빼고, 같은 출처의 CSS는 전부 인라인하고, 폰트처럼 읽을 수 없는
 * 외부 스타일시트는 `<link>`로 남긴다 (플러그인이 직접 받아간다).
 */

interface CollectedCss {
  inline: string[];
  keepLinks: string[];
}

function collectCss(): CollectedCss {
  const inline: string[] = [];
  const keepLinks: string[] = [];

  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList | null = null;
    try {
      rules = sheet.cssRules;
    } catch {
      rules = null; // cross-origin — 읽을 수 없다
    }

    if (rules) {
      const text = Array.from(rules)
        .map((r) => r.cssText)
        .join('\n');
      if (text.trim()) inline.push(text);
    } else if (sheet.href) {
      keepLinks.push(sheet.href);
    }
  }

  return { inline, keepLinks };
}

/** 시트 자체의 조작 UI는 Figma에 들어갈 필요가 없다 */
const STRIP_SELECTORS = ['script', '.sheet-bar', '.sheet-warn', '.sheet-how'];

export function serializeDocument(): string {
  const { inline, keepLinks } = collectCss();

  const body = document.body.cloneNode(true) as HTMLElement;
  for (const sel of STRIP_SELECTORS) {
    body.querySelectorAll(sel).forEach((n) => n.remove());
  }

  // 스타일 속성으로 살아 있는 값들은 그대로 두되, React가 남긴 주석 노드만 정리
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_COMMENT);
  const comments: Comment[] = [];
  while (walker.nextNode()) comments.push(walker.currentNode as Comment);
  comments.forEach((c) => c.remove());

  const links = keepLinks.map((href) => `<link rel="stylesheet" href="${href}">`).join('\n');

  return [
    '<!doctype html>',
    '<html lang="ko">',
    '<head>',
    '<meta charset="utf-8">',
    '<title>대신고 — 화면 시트</title>',
    links,
    '<style>',
    inline.join('\n'),
    '</style>',
    '</head>',
    '<body>',
    body.innerHTML,
    '</body>',
    '</html>',
  ].join('\n');
}
