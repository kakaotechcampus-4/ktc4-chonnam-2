import type { Action, AppState, Candidate } from './types';
import {
  defaultCandidates,
  similarCandidates,
  candidatesShiftedBefore,
  candidatesShiftedAfter,
} from './mock/candidates';
import { createInitialCase } from './mock/caseData';
import { computeWidenedScope } from './utils/widen';
import { DRIVE_START, DRIVE_END } from './mock/files';

/**
 * Lookup table for REVEAL_CANDIDATE — spans every mock candidate list so a candidate id
 * can be resolved regardless of which attempt (default / shifted-before / shifted-after /
 * similar) revealed it. Ids are unique across all four lists (see mock/candidates.ts).
 */
const allCandidatesById = new Map<string, Candidate>(
  [...defaultCandidates, ...candidatesShiftedBefore, ...candidatesShiftedAfter, ...similarCandidates].map(
    (c) => [c.id, c] as const,
  ),
);

// ---------- spec §5.3 hint regexes — parsed as-is, unmatched fields fall back to '' ----------
const TIME_RE = /(\d+)시\s*(반|\d+분)?/;
const VEHICLE_RE = /(흰|검은|은색|빨간)\s*(SUV|승용차|오토바이|트럭)/;
const EVENT_RE = /실선|중앙선|신호|끼어들|안전모/;
const LOCATION_RE = /(\S+역|\S+IC|\S+사거리)/;

export function createInitialState(): AppState {
  return {
    step: 'upload',
    case: createInitialCase(),
    scenario: { resultScenario: 'candidates', plateVariant: 'partial', speed: 'normal' },
  };
}

export function reduce(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'NEXT': {
      if (state.step === 'upload') {
        return { ...state, step: 'describe' };
      }
      if (state.step === 'prepare') {
        // spec §4.2 gate — plate must not be needs-review, situation must be user-confirmed.
        const plateOk = state.case.plate.status !== 'needs-review';
        const situationOk = state.case.situation.status === 'user-confirmed';
        if (plateOk && situationOk) {
          return { ...state, step: 'review' };
        }
        return state;
      }
      return state;
    }

    case 'SUBMIT_MEMORY': {
      if (state.step !== 'describe') return state;
      const raw = action.raw;
      const timeMatch = TIME_RE.exec(raw);
      const vehicleMatch = VEHICLE_RE.exec(raw);
      const eventMatch = EVENT_RE.exec(raw);
      const locationMatch = LOCATION_RE.exec(raw);
      return {
        ...state,
        step: 'scope',
        case: {
          ...state.case,
          hints: {
            time: timeMatch ? timeMatch[0] : '',
            vehicle: vehicleMatch ? vehicleMatch[0] : '',
            event: eventMatch ? eventMatch[0] : '',
            location: locationMatch ? locationMatch[0] : '',
            raw,
          },
        },
      };
    }

    case 'EDIT_HINT': {
      if (state.step !== 'scope') return state;
      return {
        ...state,
        case: {
          ...state.case,
          hints: { ...state.case.hints, [action.key]: action.value },
        },
      };
    }

    case 'EDIT_SCOPE': {
      if (state.step !== 'scope') return state;
      return {
        ...state,
        case: {
          ...state.case,
          scope: {
            ...state.case.scope,
            ...(action.from !== undefined ? { from: action.from } : {}),
            ...(action.to !== undefined ? { to: action.to } : {}),
          },
        },
      };
    }

    case 'START_SEARCH': {
      if (state.step !== 'scope') return state;
      return {
        ...state,
        step: 'searching',
        case: { ...state.case, searchMode: 'full', scannedPct: 0, candidates: [], viewingSimilar: false },
      };
    }

    case 'TICK': {
      if (state.step !== 'searching') return state;
      return { ...state, case: { ...state.case, scannedPct: action.scannedPct } };
    }

    case 'REVEAL_CANDIDATE': {
      if (state.step !== 'searching') return state;
      const found = allCandidatesById.get(action.id);
      if (!found) return state;
      return {
        ...state,
        case: { ...state.case, candidates: [...state.case.candidates, found] },
      };
    }

    case 'SEARCH_DONE': {
      if (state.step !== 'searching') return state;
      const { resultScenario } = state.scenario;
      const alreadyResolved = state.case.scenarioResolved;

      // Ruling 4: failure only fires the first time this case's scenario resolves.
      if (resultScenario === 'failed' && !alreadyResolved) {
        return {
          ...state,
          step: 'failed',
          case: { ...state.case, scenarioResolved: true, viewingSimilar: false },
        };
      }

      // Ruling 1: no-result only fires the first time; a later WIDEN search resolves normally.
      if (resultScenario === 'no-result' && !alreadyResolved) {
        return {
          ...state,
          step: 'no-result',
          case: { ...state.case, scenarioResolved: true, viewingSimilar: false },
        };
      }

      // Default outcome — either resultScenario === 'candidates', or this case already
      // spent its one "surprise" outcome (failed/no-result) and now resolves normally.
      const finalCandidates = state.case.candidates.length > 0 ? state.case.candidates : defaultCandidates;
      return {
        ...state,
        step: 'candidates',
        case: { ...state.case, candidates: finalCandidates, scenarioResolved: true, viewingSimilar: false },
      };
    }

    case 'STOP': {
      if (state.step !== 'searching') return state;
      // Partial results: keep whatever candidates/scannedPct/searchMode already accumulated.
      // viewingSimilar: false (re-review fix) — a STOP reached via SHOW_SIMILAR → REJECT_ALL →
      // WIDEN could otherwise land on 'candidates' with real, freshly-revealed partial results
      // still flagged as 「비슷하지만 다른 장면」, wrongly showing the not-a-peer caveat and
      // suppressing the real §5.5 partial-results banner.
      return { ...state, step: 'candidates', case: { ...state.case, viewingSimilar: false } };
    }

    case 'EDIT_CONDITION': {
      if (state.step !== 'searching') return state;
      return { ...state, step: 'scope' };
    }

    case 'SELECT': {
      if (state.step !== 'candidates') return state;
      if (action.id === state.case.selectedId) return state; // already selected — no-op
      // Ruling 5: a different candidate resets only occurredAt/clip/situation, not plate.
      const fresh = createInitialCase();
      return {
        ...state,
        case: {
          ...state.case,
          occurredAt: fresh.occurredAt,
          clip: fresh.clip,
          situation: fresh.situation,
          selectedId: action.id,
        },
      };
    }

    case 'ACCEPT': {
      if (state.step !== 'candidates') return state;
      return { ...state, step: 'prepare' };
    }

    case 'SHIFT': {
      if (state.step !== 'candidates') return state;
      // Ruling 3: swap in the pre-built alternate list, no plate/situation reset (§4.3).
      const shifted = action.direction === 'before' ? candidatesShiftedBefore : candidatesShiftedAfter;
      return {
        ...state,
        step: 'searching',
        case: {
          ...state.case,
          searchMode: 'shift',
          candidates: shifted,
          viewingSimilar: false,
          correction: {
            kept: ['차량: 흰색 SUV', '상황: 실선 침범'],
            changed: [
              action.direction === 'before'
                ? '시간 범위: 이전 2분 (18:29:48 – 18:31:48)'
                : '시간 범위: 이후 2분 (18:33:48 – 18:35:48)',
            ],
          },
        },
      };
    }

    case 'REJECT_ALL': {
      if (state.step !== 'candidates') return state;
      return { ...state, step: 'no-result' };
    }

    // Controller ruling (task-12 fix round): CandidatesScreen's "이어서 찾기" banner
    // (shown when a STOP mid-search left scannedPct < 100) needs its own action, distinct
    // from RETRY (failure-recovery only). "이어서" means continue, not restart — scannedPct
    // and candidates are deliberately left untouched here; SearchingScreen.tsx's own
    // startPct logic is what actually resumes from scannedPct instead of 0 (it now just
    // always resumes from whatever scannedPct already is — see WIDEN's comment below for
    // why no reset/resume discriminator is needed there anymore).
    case 'RESUME_SEARCH': {
      if (state.step !== 'candidates') return state;
      return { ...state, step: 'searching', case: { ...state.case, searchMode: 'full' } };
    }

    case 'WIDEN': {
      if (state.step !== 'no-result') return state;
      // Fresh accumulator for the widened search (same as START_SEARCH) — without this,
      // REVEAL_CANDIDATE would append onto whatever candidates survived REJECT_ALL/no-result,
      // producing duplicate ids if the widened attempt reveals the same defaultCandidates.
      // scannedPct: 0 (controller ruling, task-12 fix round 2) — WIDEN now resets its own
      // starting point here in the reducer, same as START_SEARCH, instead of leaving it stale
      // for SearchingScreen to special-case. This retires the old resultScenario/scenarioResolved
      // discriminator that used to tell WIDEN's "restart" apart from RETRY/RESUME_SEARCH's
      // "resume" in SearchingScreen.tsx — every 'full' re-entry can now just resume from
      // whatever scannedPct already is, because every action that wants a fresh 0 (START_SEARCH,
      // now WIDEN) sets it to 0 itself.
      //
      // Final review fix wave finding #1: this used to leave `case.scope` completely untouched,
      // so NoResultScreen's "영상 9개 → 21개"/"17:45 – 19:12" promise never actually took effect —
      // SearchingScreen kept showing the original narrow scope/file count after the widen. Both
      // screens now derive the widened scope from the same `computeWidenedScope` helper, so what
      // gets promised here is exactly what SearchingScreen goes on to show.
      //
      // viewingSimilar: false (re-review fix) — reachable via SHOW_SIMILAR → REJECT_ALL →
      // WIDEN, which without this would carry the flag into the fresh 'full' search and (if the
      // user then hits STOP mid-search) mislabel real partial results as 「비슷하지만 다른 장면」.
      return {
        ...state,
        step: 'searching',
        case: {
          ...state.case,
          searchMode: 'full',
          candidates: [],
          scannedPct: 0,
          scope: computeWidenedScope(state.case.scope, DRIVE_START, DRIVE_END),
          viewingSimilar: false,
        },
      };
    }

    case 'REDESCRIBE': {
      if (state.step !== 'no-result') return state;
      return { ...state, step: 'describe' };
    }

    case 'EDIT_VEHICLE': {
      if (state.step !== 'no-result') return state;
      return { ...state, step: 'scope' };
    }

    case 'SHOW_SIMILAR': {
      if (state.step !== 'no-result') return state;
      // Final review fix wave finding #2: `viewingSimilar` marks that `case.candidates` now
      // holds `similar` (「비슷하지만 다른 장면」), not real search candidates, so CandidatesScreen
      // can keep spec §5.7's "같은 위계로 두지 않는다" framing instead of rendering them as
      // indistinguishable peers. Cleared again by whatever action next populates real candidates
      // or leaves 'searching' for 'candidates' (START_SEARCH/SEARCH_DONE/SHIFT/SHOW_PARTIAL/
      // STOP/WIDEN — re-review fix round: STOP/WIDEN were originally missed here, letting a
      // SHOW_SIMILAR → REJECT_ALL → WIDEN → STOP path carry the flag onto real partial results).
      return {
        ...state,
        step: 'candidates',
        case: { ...state.case, candidates: state.case.similar, viewingSimilar: true },
      };
    }

    case 'RETRY': {
      if (state.step !== 'failed') return state;
      // §5.8 — scannedPct is deliberately left untouched, this continues rather than restarts.
      return { ...state, step: 'searching', case: { ...state.case, searchMode: 'full' } };
    }

    case 'SHOW_PARTIAL': {
      if (state.step !== 'failed') return state;
      return { ...state, step: 'candidates', case: { ...state.case, viewingSimilar: false } };
    }

    case 'SET_FIELD': {
      // Task 15: ReviewScreen's editable report text also dispatches SET_FIELD (mapped onto
      // 'reportBody', see utils/reportBody.ts — final review fix wave finding #3 moved this off
      // 'title', which it used to overwrite) to mark the edit as user-confirmed, so the guard now
      // admits 'review' alongside 'prepare' rather than only the screen that introduced it.
      if (state.step !== 'prepare' && state.step !== 'review') return state;
      return { ...state, case: { ...state.case, [action.key]: action.field } };
    }

    case 'BACK': {
      if (state.step !== 'review') return state;
      return { ...state, step: 'prepare' };
    }

    case 'BUILD': {
      if (state.step !== 'review') return state;
      return { ...state, step: 'handoff' };
    }

    case 'NEW_CASE': {
      if (state.step !== 'handoff') return state;
      // Fresh case, but the ScenarioBar's selection survives (per §4.1's handoff row).
      return { step: 'describe', case: createInitialCase(), scenario: state.scenario };
    }

    case 'SET_SCENARIO': {
      return { ...state, scenario: { ...state.scenario, ...action.scenario } };
    }

    case 'RESET': {
      return createInitialState();
    }

    default: {
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}
