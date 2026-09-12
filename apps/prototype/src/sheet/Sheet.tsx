import { useEffect, useRef, useState } from 'react';
import type { JSX, ReactNode } from 'react';
import type { Action, AppState } from '../types';
import { AppBar } from '../components/AppBar';
import { UploadScreen } from '../screens/UploadScreen';
import { DescribeScreen } from '../screens/DescribeScreen';
import { ScopeScreen } from '../screens/ScopeScreen';
import { SearchingScreen } from '../screens/SearchingScreen';
import { CandidatesScreen } from '../screens/CandidatesScreen';
import { NoResultScreen } from '../screens/NoResultScreen';
import { FailedScreen } from '../screens/FailedScreen';
import { PrepareScreen } from '../screens/PrepareScreen';
import { ReviewScreen } from '../screens/ReviewScreen';
import { HandoffScreen } from '../screens/HandoffScreen';
import { ARTBOARDS, LANE_LABEL, LANE_ORDER } from './artboards';
import type { Artboard } from './artboards';
import { serializeDocument } from './serialize';

/**
 * 「대신고 화면 시트」 — 프로토타입의 모든 화면·상태를 한 페이지에 늘어놓는다.
 * 목적은 딱 하나: html.to.design으로 **한 번에** Figma에 반입하는 것.
 *
 * 프로토타입 본체(`App.tsx`)는 건드리지 않는다. 같은 화면 컴포넌트를 읽기만 한다.
 */

/** 아트보드 폭. global.css의 `.grid2`가 2단을 유지하는 최소 폭(1380px)보다 넓게 잡는다 */
const FRAME_W = 1440;
/** 이 폭보다 창이 좁으면 화면 자체가 1단으로 접혀서, 반입 결과가 실제 화면과 달라진다 */
const MIN_WINDOW_W = 1400;

/** 시트 안에서는 아무 것도 진행되면 안 된다. 상태는 artboards.ts가 정한 그대로 고정 */
const noop: (a: Action) => void = () => {};

function renderScreen(state: AppState): ReactNode {
  const p = { state, dispatch: noop };
  switch (state.step) {
    case 'upload': return <UploadScreen {...p} />;
    case 'describe': return <DescribeScreen {...p} />;
    case 'scope': return <ScopeScreen {...p} />;
    case 'searching': return <SearchingScreen {...p} />;
    case 'candidates': return <CandidatesScreen {...p} />;
    case 'no-result': return <NoResultScreen {...p} />;
    case 'failed': return <FailedScreen {...p} />;
    case 'prepare': return <PrepareScreen {...p} />;
    case 'review': return <ReviewScreen {...p} />;
    case 'handoff': return <HandoffScreen {...p} />;
  }
}

/**
 * 화면을 잠깐 살려 뒀다가 DOM을 그대로 굳힌다.
 *
 * 왜 필요한가: UploadScreen은 3초 뒤에야 「완료」가 되고, SearchingScreen은 1초마다
 * 경과 시간을 올린다. 살아 있는 채로 반입하면 아트보드마다 다른 순간이 잡힌다.
 * 얼린 뒤에는 타이머가 전부 사라져서, 몇 시간 뒤에 반입해도 같은 그림이 나온다.
 */
function Freeze(props: { delay: number; onFrozen: () => void; children: ReactNode }): JSX.Element {
  const { delay, onFrozen, children } = props;
  const ref = useRef<HTMLDivElement>(null);
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    if (html !== null) return;
    const t = window.setTimeout(() => {
      const node = ref.current;
      if (!node) return;
      setHtml(node.innerHTML);
      onFrozen();
    }, delay);
    return () => window.clearTimeout(t);
    // onFrozen은 부모에서 안정적으로 유지된다 (useState setter 기반)
  }, [delay, html, onFrozen]);

  if (html !== null) {
    return <div className="ab-live" ref={ref} dangerouslySetInnerHTML={{ __html: html }} />;
  }
  return <div className="ab-live" ref={ref}>{children}</div>;
}

function Board(props: { ab: Artboard; index: number; onFrozen: () => void }): JSX.Element {
  const { ab, index, onFrozen } = props;
  return (
    <section className="ab" style={{ width: FRAME_W }} data-artboard={ab.id}>
      <header className="ab-head">
        <span className="ab-num">{String(index + 1).padStart(2, '0')}</span>
        <span className="ab-title">{ab.title}</span>
        <span className="ab-step">{ab.state.step}</span>
      </header>

      <div className="ab-frame" style={{ width: FRAME_W }}>
        <Freeze delay={ab.freezeMs ?? 0} onFrozen={onFrozen}>
          <div className="app-shell">
            <AppBar step={ab.state.step} />
            {renderScreen(ab.state)}
          </div>
        </Freeze>
      </div>

      <div className="ab-notes" style={{ width: FRAME_W }}>
        <p className="ab-note">{ab.note}</p>
        <ul className="ab-q">
          {ab.questions.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default function Sheet(): JSX.Element {
  const [frozen, setFrozen] = useState(0);
  const [narrow, setNarrow] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  // 부모 재렌더로 Freeze의 effect가 다시 돌지 않도록, setter만 넘긴다
  const bump = useRef(() => setFrozen((n) => n + 1)).current;

  useEffect(() => {
    const check = () => setNarrow(window.innerWidth < MIN_WINDOW_W);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  const total = ARTBOARDS.length;
  const done = frozen >= total;

  function handleExport() {
    const html = serializeDocument();
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'daesingo-screens-sheet.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setSaved(`${Math.round(html.length / 1024)}KB`);
  }

  return (
    <div className="sheet">
      <div className="sheet-bar">
        <div className="sheet-bar-l">
          <strong>대신고 — 화면 시트</strong>
          <span className="sheet-sub">
            화면 {total}장 · html.to.design 반입용 · 프로토타입 <code>machine.ts</code>에서 직접 조립
          </span>
        </div>
        <div className="sheet-bar-r">
          <span className={done ? 'pill ok' : 'pill wait'}>
            {done ? `전부 고정됨 (${total}/${total})` : `고정 중 ${frozen}/${total}`}
          </span>
          <button type="button" className="sheet-btn" onClick={handleExport} disabled={!done}>
            단일 HTML로 내보내기
          </button>
          {saved && <span className="pill ok">{saved} 저장됨</span>}
        </div>
      </div>

      {narrow && (
        <p className="sheet-warn">
          창이 {MIN_WINDOW_W}px보다 좁습니다. 이 상태로 반입하면 화면이 1단으로 접힌 채 Figma에 들어가
          실제 화면과 달라집니다. 창을 최대화한 뒤 새로고침하세요.
        </p>
      )}

      <p className="sheet-how">
        <strong>반입 방법</strong> — ① 「전부 고정됨」이 뜰 때까지 기다린다 ② Figma에서 html.to.design
        플러그인을 연다 ③ <em>Import from HTML code</em>에 내보낸 파일 내용을 붙여넣거나, 이 페이지 URL을
        그대로 넣는다. 아트보드 이름은 각 화면의 <code>data-artboard</code> 값이다.
      </p>

      {LANE_ORDER.map((lane) => {
        const boards = ARTBOARDS.filter((a) => a.lane === lane);
        if (boards.length === 0) return null;
        return (
          <section className="lane" key={lane}>
            <h2 className="lane-t">{LANE_LABEL[lane]}</h2>
            <div className="lane-row">
              {boards.map((ab) => (
                <Board key={ab.id} ab={ab} index={ARTBOARDS.indexOf(ab)} onFrozen={bump} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
