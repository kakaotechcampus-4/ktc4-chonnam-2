import { useState } from 'react';
import type { JSX } from 'react';
import type { Action, AppState, Hints } from '../types';
import { Panel } from '../components/Panel';
import { Button } from '../components/Button';
import { SearchAxis } from '../components/SearchAxis';
import { TOTAL_FILES, DRIVE_START, DRIVE_END } from '../mock/files';

/**
 * DESIGN-stage1-mockups.html 1270–1371 (화면 3 · 이해한 내용과 찾을 범위 확인).
 *
 * Hint chips read straight from `state.case.hints` (§5.3). A field the SUBMIT_MEMORY regexes
 * failed to match comes back as `''` (empty string), not `null` — this is a deliberate,
 * controller-approved deviation from the spec's literal wording (Task 3 review), so the
 * "못 알아들었어요" fallback below checks falsiness, not `=== null`.
 *
 * Origin-quote extraction: each `hints[key]` value (when matched) already *is* the exact
 * substring of `hints.raw` the regex matched — `SUBMIT_MEMORY` sets e.g. `hints.time =
 * timeMatch[0]`, and `[0]` is the whole-match text pulled verbatim out of `raw`. So the
 * "출처" quote for a chip doesn't need to re-run the regex or search `raw` — the value itself
 * is the quote. This is option (b) from the brief, chosen because it's simpler than
 * re-exporting/re-running machine.ts's regex constants and is exactly as correct: the
 * substring shown is not a guess, it's the literal text `SUBMIT_MEMORY` already matched.
 */
const HINT_META: { key: keyof Omit<Hints, 'raw'>; label: string }[] = [
  { key: 'time', label: '시간' },
  { key: 'vehicle', label: '차량' },
  { key: 'event', label: '상황' },
  { key: 'location', label: '위치' },
];

const DAY_MINUTES = 24 * 60;

function toMinutes(hhmm: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(hhmm.trim());
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function toHHMM(minutes: number): string {
  const wrapped = ((minutes % DAY_MINUTES) + DAY_MINUTES) % DAY_MINUTES;
  const h = Math.floor(wrapped / 60);
  const m = wrapped % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

export function ScopeScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const { hints, scope } = state.case;
  const [editingKey, setEditingKey] = useState<keyof Omit<Hints, 'raw'> | null>(null);

  const remaining = TOTAL_FILES - scope.files;

  /**
   * ±15분 조정 — spec explicitly allows this simpler alternative to drag-handles
   * ("구현이 부담되면 ±15분 버튼 4개로 대체해도 된다"). Each button nudges one edge of the
   * scope window by 15 minutes; `fromPct`/`toPct` are left untouched (cosmetic —
   * SearchAxis's brackets won't visually move, only the text/aruler labels change).
   */
  function adjustScope(edge: 'from' | 'to', deltaMinutes: number) {
    const current = toMinutes(scope[edge]);
    if (current === null) return;
    const next = toHHMM(current + deltaMinutes);
    dispatch(edge === 'from' ? { type: 'EDIT_SCOPE', from: next } : { type: 'EDIT_SCOPE', to: next });
  }

  return (
    <div className="pbody">
      <div className="ptop">
        <div>
          <h2 className="ptitle">이렇게 이해했어요</h2>
          <p className="psub">틀린 부분이 있으면 지금 고쳐주세요. 잘못된 조건으로 오래 찾으면 시간이 낭비됩니다.</p>
        </div>
      </div>

      <div className="und" style={{ marginBottom: 18 }}>
        {HINT_META.map(({ key, label }) => {
          const value = hints[key];
          const isEditing = editingKey === key;
          return (
            <div className="undc" key={key}>
              <span className="und-k">{label}</span>
              {isEditing ? (
                <input
                  autoFocus
                  value={value}
                  onChange={(e) => dispatch({ type: 'EDIT_HINT', key, value: e.target.value })}
                  onBlur={() => setEditingKey(null)}
                  style={{
                    font: 'inherit',
                    fontSize: 'calc(19px * var(--font-scale))',
                    fontWeight: 750,
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    padding: '2px 6px',
                    width: '100%',
                  }}
                />
              ) : (
                <span className="und-v" style={value ? undefined : { color: 'var(--orange-ink)' }}>
                  {value || '못 알아들었어요'}
                </span>
              )}
              {value && <span className="und-q">&quot;{value}&quot;에서</span>}
              <button
                type="button"
                className="btn sm"
                style={{ marginTop: 4, alignSelf: 'flex-start' }}
                onClick={() => setEditingKey(isEditing ? null : key)}
              >
                {isEditing ? '완료' : '수정'}
              </button>
            </div>
          );
        })}
      </div>

      <Panel className="axis-p">
        <div className="axis-hd">
          <span className="axis-t">먼저 찾아볼 구간</span>
          <span className="axis-s">
            <b>{scope.from} – {scope.to}</b> · 영상 <span className="mono">{scope.files}</span>개 · 나머지{' '}
            <span className="mono">{remaining}</span>개는 그대로 남습니다
          </span>
        </div>
        <SearchAxis
          from={DRIVE_START}
          to={DRIVE_END}
          scope={{ fromPct: scope.fromPct, toPct: scope.toPct }}
          scannedPct={0}
          markers={[]}
        />
        <div className="alegend">
          <span className="alg"><i className="scope" />먼저 찾을 구간 {scope.files}개</span>
          <span className="alg"><i style={{ background: '#dfe6ee' }} />남겨둔 구간 {remaining}개</span>
        </div>
      </Panel>

      <div style={{ marginTop: 18 }}>
        <Panel>
          <div className="axis-t" style={{ marginBottom: 10 }}>구간 직접 조정</div>
          <div className="btnrow">
            <Button onClick={() => adjustScope('from', -15)}>시작 15분 앞당기기</Button>
            <Button onClick={() => adjustScope('from', 15)}>시작 15분 늦추기</Button>
            <Button onClick={() => adjustScope('to', 15)}>끝 15분 늦추기</Button>
            <Button onClick={() => adjustScope('to', -15)}>끝 15분 앞당기기</Button>
          </div>
        </Panel>
      </div>

      <div className="btnrow" style={{ marginTop: 18 }}>
        <Button variant="primary" size="large" onClick={() => dispatch({ type: 'START_SEARCH' })}>
          맞아요, 찾아주세요
        </Button>
      </div>
    </div>
  );
}
