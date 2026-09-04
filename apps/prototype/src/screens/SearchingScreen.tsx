import { useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import type { Action, AppState, WorkStatus } from '../types';
import { Panel } from '../components/Panel';
import { SecLabel } from '../components/SecLabel';
import { WorkList } from '../components/WorkList';
import { SearchAxis } from '../components/SearchAxis';
import { Button } from '../components/Button';
import { defaultCandidates, candidatesShiftedBefore, candidatesShiftedAfter } from '../mock/candidates';
import { DRIVE_START, DRIVE_END } from '../mock/files';

/**
 * DESIGN-stage1-mockups.html 1372–1502 (화면 4 · 찾는 중) + PROTOTYPE-SPEC.md §5.5 —
 * "가장 중요한 화면". This screen owns the only clock in the whole app (progress.md's
 * ruling: "Timer ownership lives entirely in SearchingScreen") — `machine.ts` never runs
 * one, it only reacts to the `TICK`/`REVEAL_CANDIDATE`/`SEARCH_DONE` this screen dispatches.
 */

const FULL_DURATION_MS = 9000; // §5.5 timeline table, canonical 0→100 scale for a 'full' run
const SHIFT_DURATION_MS = 3000; // ruling 2 — shift is always a short re-check, never the 9s sweep
const STEP_MS = 100;

/**
 * Canonical arrival marks (§5.5 timeline), keyed by defaultCandidates id. mock/candidates.ts's
 * own comment says array order = marker number order (c1→marker "1"/latest time, c2→"2",
 * c3→"3"/earliest time), while the spec's timeline table lists arrival by canonical elapsed
 * time: 3.0s→marker "3" (earliest scene), 5.0s→marker "2", 7.0s→marker "1" (latest scene) —
 * i.e. candidates surface in the opposite order from their marker numbers/on-axis position.
 */
const REVEAL_MARKS: { id: string; atMs: number }[] = [
  { id: 'c3', atMs: 3000 },
  { id: 'c2', atMs: 5000 },
  { id: 'c1', atMs: 7000 },
];

// Marker number = 1-based index within whichever family list a candidate id belongs to
// (mock/candidates.ts: "배열 순서 = 마커 번호 순서"). Spans all three 'full'/'shift' families so
// this same map works for both a fresh full run and a SHIFT re-entry (Task 12 reuses this
// component/this map's logic for the "찾은 후보" list's numbering).
const MARKER_NUMBER = new Map<string, number>([
  ...defaultCandidates.map((c, i): [string, number] => [c.id, i + 1]),
  ...candidatesShiftedBefore.map((c, i): [string, number] => [c.id, i + 1]),
  ...candidatesShiftedAfter.map((c, i): [string, number] => [c.id, i + 1]),
]);

function formatElapsed(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return m > 0 ? `${m}분 ${String(s).padStart(2, '0')}초` : `${s}초`;
}

export function SearchingScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const { case: caseState, scenario } = state;
  const { searchMode } = caseState;

  const [elapsedSec, setElapsedSec] = useState(0);
  const [skipped, setSkipped] = useState(false);
  // Set by whichever branch of the timer effect below is active, so the single
  // "빠르게 건너뛰기" button works no matter which path (reduced-motion / animated) is running.
  const finishNowRef = useRef<() => void>(() => {});

  // Elapsed-time counter — deliberately its own clock, NOT derived from scannedPct, so it keeps
  // counting in real seconds independent of the fill animation's easing/instant-mode shortcuts
  // (brief Step 2). This is the only "progress" readout on this screen — no percentage, no ETA.
  useEffect(() => {
    const id = window.setInterval(() => setElapsedSec((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  // ---- Step 1: the timer loop ----
  // Dependency is `searchMode` only (see brief: "on mount, and whenever searchMode changes, so
  // re-entry via SHIFT restarts the loop"). In practice every entry to this screen is already a
  // fresh mount — App.tsx only renders SearchingScreen while state.step === 'searching', so
  // leaving and re-entering (STOP→…→START_SEARCH, RETRY, SHIFT, WIDEN, RESUME_SEARCH) always
  // unmounts and remounts it. All the other scenario/case fields this effect reads are deliberately captured
  // once here rather than listed as deps: they're what this very timer is about to change
  // (scannedPct every tick) or are only meaningful at the instant this run starts.
  useEffect(() => {
    let cancelled = false;
    let intervalId: number | undefined;
    let timeoutId: number | undefined;

    const resultScenario = scenario.resultScenario;
    const scenarioResolved = caseState.scenarioResolved;
    // Mirrors SEARCH_DONE's own gates (machine.ts) exactly, so this screen's animation/reveal
    // choices stay in lockstep with what the reducer is about to do once SEARCH_DONE fires.
    const willFail = resultScenario === 'failed' && !scenarioResolved;
    const willNoResult = resultScenario === 'no-result' && !scenarioResolved;
    const headingToFailed = searchMode === 'full' && willFail; // ruling 4

    const targetPct = headingToFailed ? 60 : 100;

    // Resume vs fresh-start for a 'full' run's starting scannedPct — controller ruling, task-12
    // fix round 2: no discriminator at all. Every action that wants this run to look like a
    // fresh sweep (START_SEARCH, and now WIDEN — see machine.ts) sets `scannedPct: 0` itself in
    // the reducer *before* this screen ever mounts; every action that wants it continued in
    // place (RETRY leaving it at ruling 4's 60% cap; RESUME_SEARCH leaving it wherever a
    // voluntary STOP stopped it) simply leaves it untouched. So this screen can just always
    // resume from whatever `caseState.scannedPct` already is — it's correct by construction for
    // all four re-entry paths, with no need to inspect `resultScenario`/`scenarioResolved` at
    // all. (An earlier version of this logic tried to infer "reset vs resume" from
    // `resultScenario`/`scenarioResolved` instead of having the resetting actions just reset the
    // value — that discriminator went through two rounds of increasingly narrow patches
    // (task-12 fix rounds 1 and 2) before this rewrite retired it outright, including the
    // ScenarioBar-desync risk once flagged for Task 13, which no longer applies since there's no
    // discriminator left to desync.)
    const startPct = searchMode === 'full' ? Math.min(caseState.scannedPct, targetPct) : 0;

    // Only a 'full' run actually heading to the default candidates outcome reveals interim
    // candidates. A run bound for no-result/failed doesn't: the reducer doesn't care what's in
    // case.candidates for those branches, and revealing some anyway would visually contradict
    // the eventual "couldn't find it" / "something went wrong" outcome — documented choice per
    // the brief's "your call, document it". A 'shift' run never reveals progressively either:
    // SHIFT already populated case.candidates wholesale before this screen mounted, so the axis
    // and candidate list show all of them immediately, unaffected by this flag.
    const shouldReveal = searchMode === 'full' && !willFail && !willNoResult;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reduceMotion) {
      // §5.5 — no animation. A single TICK to the final value (not an animated one) right
      // before SEARCH_DONE keeps scannedPct correct for a later RETRY to resume from, without
      // reintroducing any animation.
      const finish = () => {
        if (cancelled) return;
        cancelled = true;
        dispatch({ type: 'TICK', scannedPct: targetPct });
        dispatch({ type: 'SEARCH_DONE' });
      };
      timeoutId = window.setTimeout(finish, 1000);
      finishNowRef.current = () => {
        if (timeoutId !== undefined) window.clearTimeout(timeoutId);
        finish();
      };
      return () => {
        cancelled = true;
        if (timeoutId !== undefined) window.clearTimeout(timeoutId);
      };
    }

    const runDurationMs =
      searchMode === 'shift' ? SHIFT_DURATION_MS : ((targetPct - startPct) / 100) * FULL_DURATION_MS;

    // '즉시' scenario speed only fast-forwards a 'full' run (ruling 2 — shift is already short
    // and always takes its fixed 3s even under 즉시). The skip button, however, can force-finish
    // either mode early — that's what finishNowRef flips this ref for, below.
    const forceInstant = { current: searchMode === 'full' && scenario.speed === 'instant' };
    finishNowRef.current = () => {
      forceInstant.current = true;
    };

    // Seeded from whatever's already in case.candidates (defensive — in this screen's own
    // reveal policy that's always empty at mount, but a resumed RETRY relies on this guard to
    // never re-dispatch REVEAL_CANDIDATE for an id the previous attempt already added).
    const revealed = new Set(caseState.candidates.map((c) => c.id));
    let elapsed = 0;
    let finished = false;

    function tick() {
      if (finished || cancelled) return;
      elapsed += STEP_MS;
      const effectiveDuration = forceInstant.current ? Math.min(runDurationMs, elapsed) : runDurationMs;
      const t = effectiveDuration <= 0 ? 1 : Math.min(elapsed / effectiveDuration, 1);
      const pct = startPct + (targetPct - startPct) * t;

      if (shouldReveal) {
        // Marks live on the canonical 0–9000ms full-run scale regardless of this run's actual
        // wall-clock duration (9s normal / near-0 instant / 3.6s resumed-after-failed etc.), so
        // scale the interpolated pct back onto that scale to decide what's "arrived" so far.
        const canonicalNow = (pct / 100) * FULL_DURATION_MS;
        for (const mark of REVEAL_MARKS) {
          if (!revealed.has(mark.id) && canonicalNow >= mark.atMs) {
            revealed.add(mark.id);
            dispatch({ type: 'REVEAL_CANDIDATE', id: mark.id });
          }
        }
      }

      if (t >= 1) {
        finished = true;
        if (intervalId !== undefined) window.clearInterval(intervalId);
        dispatch({ type: 'TICK', scannedPct: targetPct });
        dispatch({ type: 'SEARCH_DONE' });
        return;
      }
      dispatch({ type: 'TICK', scannedPct: pct });
    }

    // Fire once immediately: makes a truly-instant run (즉시 from the start, or skip clicked
    // before mount finishes rendering) resolve without an extra 100ms wait, and surfaces any
    // marks already behind a resumed run's starting point (e.g. RETRY resuming past 3s/5s
    // canonical time) right away instead of waiting for the first interval tick.
    tick();
    if (!finished) {
      intervalId = window.setInterval(tick, STEP_MS);
    }

    return () => {
      cancelled = true;
      if (intervalId !== undefined) window.clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see comment above the effect
  }, [searchMode]);

  function handleSkip() {
    setSkipped(true);
    finishNowRef.current();
  }

  const filesChecked = Math.min(
    caseState.scope.files,
    Math.round((caseState.scannedPct / 100) * caseState.scope.files),
  );

  const workItems: { label: string; status: WorkStatus; note?: string }[] = [
    {
      label: '찾아볼 구간 정하기',
      status: 'done',
      note: `${caseState.scope.totalFiles}개 → ${caseState.scope.files}개`,
    },
    searchMode === 'shift'
      ? { label: '조건을 반영해 다시 확인', status: 'running' }
      : {
          label: '사건 가능성이 있는 장면 확인',
          status: 'running',
          note: `${caseState.scope.files}개 중 ${filesChecked}개`,
        },
  ];

  const markers = caseState.candidates.map((c) => ({ n: MARKER_NUMBER.get(c.id) ?? 0, pct: c.axisPct }));
  const sortedCandidates = [...caseState.candidates].sort(
    (a, b) => (MARKER_NUMBER.get(a.id) ?? 0) - (MARKER_NUMBER.get(b.id) ?? 0),
  );

  return (
    <div className="pbody">
      <div className="ptop">
        <div>
          <h2 className="ptitle">
            {searchMode === 'shift' ? '조건을 조정해 다시 확인하고 있어요' : '사건을 찾고 있어요'}
          </h2>
          <p className="psub">창을 닫아도 계속 진행됩니다. 지금까지 찾은 후보는 사라지지 않습니다.</p>
          <p className="psub" style={{ marginTop: 6, fontWeight: 700 }}>
            경과 <span className="mono">{formatElapsed(elapsedSec)}</span>
          </p>
        </div>
        <div className="btnrow">
          <Button onClick={() => dispatch({ type: 'EDIT_CONDITION' })}>조건 수정</Button>
          <Button onClick={handleSkip} disabled={skipped}>
            빠르게 건너뛰기
          </Button>
          <Button onClick={() => dispatch({ type: 'STOP' })}>중단하기</Button>
        </div>
      </div>

      <div className="stack">
        {searchMode === 'shift' && caseState.correction && (
          <Panel className="axis-p">
            <div className="axis-hd">
              <span className="axis-t">달라지는 조건</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                <span className="chip">유지</span>
                <span
                  style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--ink-2)', fontWeight: 600 }}
                >
                  {caseState.correction.kept.join(' · ')}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                <span
                  className="chip"
                  style={{ background: 'var(--blue-soft)', borderColor: 'var(--blue-bd)', color: 'var(--blue)' }}
                >
                  변경
                </span>
                <span style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--ink)', fontWeight: 700 }}>
                  {caseState.correction.changed.join(' · ')}
                </span>
              </div>
            </div>
          </Panel>
        )}

        <Panel className="axis-p">
          <div className="axis-hd">
            <span className="axis-t">확인 중인 구간</span>
            <span className="axis-s">
              {searchMode === 'full' ? (
                <>
                  영상{' '}
                  <b>
                    {caseState.scope.files}개 중 {filesChecked}개
                  </b>{' '}
                  확인 · 후보 <b>{caseState.candidates.length}개</b> 발견
                </>
              ) : (
                <>
                  후보 <b>{caseState.candidates.length}개</b> 위치 다시 확인 중
                </>
              )}
            </span>
          </div>
          <SearchAxis
            from={DRIVE_START}
            to={DRIVE_END}
            scope={{ fromPct: caseState.scope.fromPct, toPct: caseState.scope.toPct }}
            scannedPct={caseState.scannedPct}
            markers={markers}
            legend
          />
        </Panel>

        <div className="grid2">
          <Panel>
            <SecLabel>진행 상황</SecLabel>
            <WorkList items={workItems} />
            {searchMode === 'full' && (
              <p
                style={{
                  fontSize: 'calc(15px * var(--font-scale))',
                  color: 'var(--muted)',
                  lineHeight: 1.6,
                  margin: '14px 0 0',
                  fontWeight: 550,
                }}
              >
                {caseState.candidates.length > 0
                  ? `지금까지 후보 장면 ${caseState.candidates.length}개를 찾았습니다.`
                  : '아직 확인된 후보가 없습니다.'}
              </p>
            )}
          </Panel>

          <Panel>
            <SecLabel>
              <span>지금까지 찾은 후보</span>
              <span className="n">{caseState.candidates.length}개</span>
            </SecLabel>
            {sortedCandidates.length === 0 ? (
              <p style={{ fontSize: 'calc(15px * var(--font-scale))', color: 'var(--muted)', margin: '10px 0 0' }}>
                아직 없습니다
              </p>
            ) : (
              <div className="kv" style={{ borderTop: 0 }}>
                {sortedCandidates.map((c) => (
                  <div
                    className="kvr"
                    key={c.id}
                    style={{ gridTemplateColumns: '26px 104px minmax(0,1fr)', alignItems: 'center' }}
                  >
                    <span className="cnum">{MARKER_NUMBER.get(c.id) ?? '?'}</span>
                    <span
                      className="mono"
                      style={{ fontSize: 'calc(17px * var(--font-scale))', color: 'var(--ink)', fontWeight: 700 }}
                    >
                      {c.time}
                    </span>
                    <span className="kv-src" style={{ marginTop: 0 }}>
                      {c.matches[0]?.text ?? ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
