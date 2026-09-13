import { useState } from 'react';
import type { JSX } from 'react';
import type { Action, AppState, ScenarioConfig } from '../types';

/**
 * PROTOTYPE-SPEC.md §8 — the evaluation-only control bar. Fixed at the bottom
 * of every screen (wired in App.tsx alongside AppBar, outside the step
 * switch), never part of the "real product" — hence the visible label.
 *
 * Three of the four groups dispatch SET_SCENARIO (shallow-merged into
 * state.scenario by the reducer — Tasks 2/3); `처음부터 다시` dispatches RESET.
 * §8 also asks for the `--font-scale` toggle here, but that is a pure CSS
 * concern, not part of ScenarioConfig/the reducer — kept as local useState
 * that writes the CSS custom property straight onto the document root, which
 * is where tokens.css declares `--font-scale` on `:root` and every font-size
 * in global.css reads it back via `calc(Npx * var(--font-scale))`.
 */
const RESULT_OPTIONS: { value: ScenarioConfig['resultScenario']; label: string }[] = [
  { value: 'candidates', label: '후보 3개' },
  { value: 'no-result', label: '후보 없음' },
  { value: 'failed', label: '분석 실패' },
];

const PLATE_OPTIONS: { value: ScenarioConfig['plateVariant']; label: string }[] = [
  { value: 'partial', label: '일부 불확실' },
  { value: 'unreadable', label: '판독 불가' },
  { value: 'clear', label: '선명' },
];

const SPEED_OPTIONS: { value: ScenarioConfig['speed']; label: string }[] = [
  { value: 'normal', label: '보통 9초' },
  { value: 'instant', label: '즉시' },
];

const FONT_SCALE_OPTIONS: { value: string; label: string }[] = [
  { value: '1', label: '1x' },
  { value: '1.1', label: '1.1x' },
  { value: '1.2', label: '1.2x' },
];

export function ScenarioBar(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const [fontScale, setFontScale] = useState('1');

  function applyFontScale(value: string) {
    setFontScale(value);
    document.documentElement.style.setProperty('--font-scale', value);
  }

  return (
    <div className="scenariobar">
      <span className="badge badge-attention scenariobar-label">
        <span className="dot" />
        평가용 · 실제 제품에는 없습니다
      </span>

      <div className="scenariobar-group">
        <span className="scenariobar-gname">결과 시나리오</span>
        <div className="segrow">
          {RESULT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`segment sm${state.scenario.resultScenario === opt.value ? ' active' : ''}`}
              onClick={() => dispatch({ type: 'SET_SCENARIO', scenario: { resultScenario: opt.value } })}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="scenariobar-group">
        <span className="scenariobar-gname">번호판</span>
        <div className="segrow">
          {PLATE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`segment sm${state.scenario.plateVariant === opt.value ? ' active' : ''}`}
              onClick={() => dispatch({ type: 'SET_SCENARIO', scenario: { plateVariant: opt.value } })}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="scenariobar-group">
        <span className="scenariobar-gname">진행 속도</span>
        <div className="segrow">
          {SPEED_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`segment sm${state.scenario.speed === opt.value ? ' active' : ''}`}
              onClick={() => dispatch({ type: 'SET_SCENARIO', scenario: { speed: opt.value } })}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="scenariobar-group">
        <span className="scenariobar-gname">글자 크기</span>
        <div className="segrow">
          {FONT_SCALE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`segment sm${fontScale === opt.value ? ' active' : ''}`}
              onClick={() => applyFontScale(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="scenariobar-spacer" />

      <button type="button" className="btn sm" onClick={() => dispatch({ type: 'RESET' })}>
        처음부터 다시
      </button>
    </div>
  );
}
