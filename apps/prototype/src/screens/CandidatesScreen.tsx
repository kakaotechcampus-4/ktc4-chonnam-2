import { Check, Minus } from 'lucide-react';
import type { JSX, KeyboardEvent } from 'react';
import type { Action, AppState, Candidate } from '../types';
import { Panel } from '../components/Panel';
import { SecLabel } from '../components/SecLabel';
import { Button } from '../components/Button';
import { EvidenceFrame } from '../components/EvidenceFrame';
import {
  defaultCandidates,
  candidatesShiftedBefore,
  candidatesShiftedAfter,
  similarCandidates,
} from '../mock/candidates';

/**
 * DESIGN-stage1-mockups.html 1503–1695 (화면 5 · 이 사건이 맞나요?) + PROTOTYPE-SPEC.md §5.6.
 *
 * Marker number = 1-based index within whichever family list a candidate id belongs to
 * (mock/candidates.ts: "배열 순서 = 마커 번호 순서"). This mirrors SearchingScreen.tsx's own
 * local `MARKER_NUMBER` map (task-11-report.md flagged this as the same convention a second
 * consumer would need) — duplicated here rather than hoisted into mock/candidates.ts because
 * this task's brief explicitly says not to touch SearchingScreen.tsx, and a shared helper only
 * pays for itself once both call sites can be updated together. If the three candidate arrays'
 * ordering ever changes, this map and SearchingScreen's must be updated together.
 *
 * `similarCandidates` (s1/s2) is added here — task-13's SHOW_SIMILAR is this screen's first
 * real caller with `similar` candidates in `case.candidates`, and without this entry both s1/s2
 * fell back to marker "0" (SearchingScreen.tsx never renders similarCandidates, so it never
 * needed this entry).
 *
 * Final review fix wave finding #2 — spec §5.7 "유사 후보는 「말씀하신 조건과 일부만 맞습니다」로
 * 명시. 후보와 같은 위계로 두지 않는다." Previously SHOW_SIMILAR dumped `similar` straight into
 * `case.candidates` with no trace of that caveat once here — this screen rendered s1/s2 as
 * indistinguishable full peers of a real search result. `case.viewingSimilar` (set by
 * SHOW_SIMILAR, cleared by whatever repopulates real candidates) now lets this screen restate
 * the caveat and stop miscounting the reject button's label.
 */
const MARKER_NUMBER = new Map<string, number>([
  ...defaultCandidates.map((c, i): [string, number] => [c.id, i + 1]),
  ...candidatesShiftedBefore.map((c, i): [string, number] => [c.id, i + 1]),
  ...candidatesShiftedAfter.map((c, i): [string, number] => [c.id, i + 1]),
  ...similarCandidates.map((c, i): [string, number] => [c.id, i + 1]),
]);

// §5.6's fixed candidate-family size — the partial-results banner's "3개 중 N개" always
// compares against this constant, not against whatever the current candidate list's length
// happens to be (that *is* the N).
const INTENDED_TOTAL = 3;

// finding #10 — "세 개 다 아니에요" hardcoded a count of exactly 3, wrong once `viewingSimilar`
// mode shows only 2 candidates (or a partial run ever left some other count). Native-Korean
// counter-attached numerals (한/두/세/네 + 개) for the small counts this app ever actually shows;
// anything else falls back to a digit + 개, a fine (if slightly less idiomatic) plural in Korean.
const NATIVE_COUNTER_NUMERAL: Record<number, string> = { 1: '한', 2: '두', 3: '세', 4: '네' };
function rejectAllLabel(count: number): string {
  // Re-review nit: a STOP fired before any candidate has been revealed yet (count 0) has
  // nothing to count — "0개 다 아니에요" reads as a bug, so fall back to a plain "다 아니에요".
  if (count === 0) return '다 아니에요';
  const numeral = NATIVE_COUNTER_NUMERAL[count];
  return `${numeral ?? count} 개 다 아니에요`;
}

function MatchIcon(props: { ok: boolean; size: number; strokeWidth: number }): JSX.Element {
  const color = props.ok ? 'var(--green)' : 'var(--slate)';
  return props.ok ? (
    <Check size={props.size} color={color} strokeWidth={props.strokeWidth} />
  ) : (
    <Minus size={props.size} color={color} strokeWidth={props.strokeWidth} />
  );
}

export function CandidatesScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const { case: caseState } = state;
  const candidates = caseState.candidates;
  const viewingSimilar = caseState.viewingSimilar;

  // Brief's exact lookup: selectedId's candidate, falling back to the first in the list.
  const selected: Candidate | undefined =
    candidates.find((c) => c.id === caseState.selectedId) ?? candidates[0];

  const sortedCandidates = [...candidates].sort(
    (a, b) => (MARKER_NUMBER.get(a.id) ?? 0) - (MARKER_NUMBER.get(b.id) ?? 0),
  );

  // Reached via STOP mid-search (§5.5) — scannedPct never made it to 100. Also requires
  // candidates.length < INTENDED_TOTAL (review fix): a STOP mid a 'shift' re-search can leave
  // scannedPct < 100 even though SHIFT already populated all 3 candidates wholesale up front
  // (SearchingScreen.tsx never reveals them incrementally for 'shift' mode) — without this
  // second condition the banner would nonsensically read "3개 중 3개 구간만 확인했습니다". Also
  // excludes `viewingSimilar` (finding #2 fix) — a "부분 결과, 이어서 찾기" banner makes no sense
  // while looking at 「비슷하지만 다른 장면」, which was never a real in-progress search.
  const isPartial = caseState.scannedPct < 100 && candidates.length < INTENDED_TOTAL && !viewingSimilar;

  function handleCardKeyDown(e: KeyboardEvent<HTMLDivElement>, id: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      dispatch({ type: 'SELECT', id });
    }
  }

  return (
    <div className="pbody">
      <div className="ptop">
        <div>
          <h2 className="ptitle">이 사건이 맞나요?</h2>
          <p className="psub">
            영상을 보고 직접 확인해주세요. 아래 {viewingSimilar ? candidates.length : INTENDED_TOTAL}개는 언제든 비교할 수 있습니다.
          </p>
        </div>
      </div>

      {viewingSimilar && (
        <div style={{ marginBottom: 18 }}>
          <Panel>
            <span style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span className="chip gray">비슷한 후보</span>
              <span style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--ink-2)', fontWeight: 700 }}>
                말씀하신 조건과 일부만 맞습니다. 같은 사건인지 다시 한번 확인해주세요.
              </span>
            </span>
          </Panel>
        </div>
      )}

      {isPartial && (
        <div style={{ marginBottom: 18 }}>
          <Panel>
            <div
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span className="chip gray">부분 결과</span>
                <span style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--ink-2)', fontWeight: 700 }}>
                  {INTENDED_TOTAL}개 중 {candidates.length}개 구간만 확인했습니다
                </span>
              </span>
              {/* RESUME_SEARCH (controller ruling, task-12 fix round): re-enters SearchingScreen
                  with searchMode 'full', resuming from the existing scannedPct/candidates
                  (STOP's partial results are kept, not discarded) — distinct from RETRY, which
                  is specifically the failure-recovery path. */}
              <Button onClick={() => dispatch({ type: 'RESUME_SEARCH' })}>이어서 찾기</Button>
            </div>
          </Panel>
        </div>
      )}

      {selected && (
        <div className="grid2 wide" style={{ marginBottom: 18 }}>
          <div className="panel" style={{ overflow: 'hidden' }}>
            <EvidenceFrame
              size="large"
              scene={selected.scene}
              time={selected.time}
              file={selected.file}
              annotations={selected.matches.filter((m) => m.ok).map((m) => m.text)}
            />
          </div>

          <div className="stack">
            <Panel>
              <SecLabel>
                <span>영상에서 확인된 것</span>
              </SecLabel>
              <ul className="obs">
                {selected.matches.map((m, i) => (
                  <li key={i} className={m.ok ? undefined : 'no'}>
                    <span className={`oi ${m.ok ? 'y' : 'n'}`}>
                      <MatchIcon ok={m.ok} size={12} strokeWidth={4} />
                    </span>
                    <span>
                      <span className="obs-t">{m.text}</span>
                      {m.note && <span className="obs-s">{m.note}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel>
              <SecLabel>
                <span>어떻게 하시겠어요?</span>
              </SecLabel>
              {/* §5.6 / spec Assessment A: top row = time-correction + accept only, bottom row
                  (outside this panel) = the sole "reject all" — never combine the two "no"s. */}
              <div className="btngrid" style={{ gap: 10 }}>
                <Button variant="primary" size="large" onClick={() => dispatch({ type: 'ACCEPT' })}>
                  네, 이 사건이 맞아요
                </Button>
                <div className="btngrid c2">
                  <Button onClick={() => dispatch({ type: 'SHIFT', direction: 'before' })}>조금 전이에요</Button>
                  <Button onClick={() => dispatch({ type: 'SHIFT', direction: 'after' })}>조금 후예요</Button>
                </div>
              </div>
            </Panel>
          </div>
        </div>
      )}

      <Panel>
        <SecLabel>
          <span>찾은 후보 {candidates.length}개 — 눌러서 비교하세요</span>
          <span className="n">
            {caseState.scope.from} – {caseState.scope.to}
          </span>
        </SecLabel>

        {sortedCandidates.length === 0 ? (
          <p style={{ fontSize: 'calc(15px * var(--font-scale))', color: 'var(--muted)', margin: '10px 0 0' }}>
            아직 없습니다
          </p>
        ) : (
          <div className="cands">
            {sortedCandidates.map((c) => {
              const n = MARKER_NUMBER.get(c.id) ?? 0;
              const isSelected = selected !== undefined && c.id === selected.id;
              return (
                <div
                  key={c.id}
                  className={`cand${isSelected ? ' sel' : ''}`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSelected}
                  aria-label={`후보 ${n} · ${c.time}`}
                  onClick={() => dispatch({ type: 'SELECT', id: c.id })}
                  onKeyDown={(e) => handleCardKeyDown(e, c.id)}
                  style={{ cursor: 'pointer' }}
                >
                  <EvidenceFrame size="small" scene={c.scene} time={c.time} />
                  <div className="cand-b">
                    <div className="cand-h">
                      <span style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                        <span className={`cnum${isSelected ? ' sel' : ''}`}>{n}</span>
                        <span className="cand-tc">{c.time}</span>
                      </span>
                      {isSelected && <span className="cand-tag">지금 보는 중</span>}
                    </div>
                    <ul className="mini">
                      {c.matches.map((m, i) => (
                        <li key={i} className={m.ok ? undefined : 'no'}>
                          <span className={`mi ${m.ok ? 'y' : 'n'}`}>
                            <MatchIcon ok={m.ok} size={9} strokeWidth={5} />
                          </span>
                          <span>{m.text}</span>
                        </li>
                      ))}
                    </ul>
                    {/* Mockup shows a "이 영상 보기" affordance on non-selected cards, but as a
                        plain (non-interactive) span, not a real button — the whole card already
                        dispatches SELECT on click, so a second nested interactive element here
                        would just be a duplicate/confusing click target. */}
                    {!isSelected && (
                      <span className="btn sm wide" style={{ marginTop: 'auto', pointerEvents: 'none' }}>
                        이 영상 보기
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="btnrow" style={{ marginTop: 16, justifyContent: 'flex-end' }}>
          <Button onClick={() => dispatch({ type: 'REJECT_ALL' })}>{rejectAllLabel(candidates.length)}</Button>
        </div>
      </Panel>
    </div>
  );
}
