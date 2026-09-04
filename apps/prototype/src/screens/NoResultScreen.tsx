import { Search } from 'lucide-react';
import type { JSX } from 'react';
import type { Action, AppState } from '../types';
import { Panel } from '../components/Panel';
import { SecLabel } from '../components/SecLabel';
import { Button } from '../components/Button';
import { EvidenceFrame } from '../components/EvidenceFrame';
import { DRIVE_START, DRIVE_END } from '../mock/files';
import { computeWidenedScope } from '../utils/widen';

/**
 * DESIGN-stage1-mockups.html 1696–1799 (화면 6 · 못 찾았을 때) + PROTOTYPE-SPEC.md §5.7.
 *
 * The mockup's cost-preview axis overlays two ranges on a single bar at once — the
 * already-scanned scope (green, `.aseg.scanned`) sitting inside the wider proposed scope
 * (blue-grey, `.aseg.scope`). SearchAxis's prop shape (Task 5) only expresses one "scope"
 * window whose green scanned-fill always starts flush with that window's own left edge — it
 * can't place a narrower green sub-range in the middle of a wider blue-grey range the way this
 * screen needs. Rather than reworking SearchAxis's shared contract this late (per this task's
 * brief), this screen builds its own small axis strip locally below, reusing the exact
 * `.axis`/`.aseg`/`.aruler`/`.abr`/`.alegend` classes SearchAxis itself renders with.
 *
 * Final review fix wave finding #1: the widened from/to/pct/file-count preview below and the
 * scope machine.ts's WIDEN reducer actually applies now both come from `computeWidenedScope`
 * (utils/widen.ts) — previously this screen computed its own preview locally while the reducer
 * left `case.scope` untouched, so what this screen promised ("9개 → 21개", "17:45 – 19:12")
 * never matched what SearchingScreen went on to show after the click.
 */

function parseMinutes(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

/**
 * DRIVE_START–DRIVE_END 정시 눈금. SearchAxis.tsx의 `hourTicks`와 계산이 같지만 그 함수는
 * export되지 않고, 이 화면은 (위 주석대로) SearchAxis 컴포넌트 자체를 쓰지 않는 로컬 스트립이라
 * 여기서 다시 계산한다.
 */
function hourTicks(from: string, to: string): { label: string; pct: number }[] {
  const start = parseMinutes(from);
  const end = parseMinutes(to);
  if (start === null || end === null || end <= start) return [];
  const ticks: { label: string; pct: number }[] = [];
  const firstHour = Math.floor(start / 60) + 1;
  for (let h = firstHour; h * 60 < end; h++) {
    const minutes = h * 60;
    if (minutes <= start) continue;
    ticks.push({ label: `${String(h % 24).padStart(2, '0')}:00`, pct: ((minutes - start) / (end - start)) * 100 });
  }
  return ticks;
}

export function NoResultScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const { scope, similar } = state.case;

  // Widened scope preview — same helper machine.ts's WIDEN reducer calls when the button below
  // is actually clicked, so what this screen promises and what gets applied can never drift
  // apart. For the default case (18:15–18:45 ±30분) this reproduces the mockup's own
  // "17:45 – 19:12" / "9개 → 21개" exactly (18:45+30분 would be 19:15, past DRIVE_END, so the
  // end is capped there).
  const widened = computeWidenedScope(scope, DRIVE_START, DRIVE_END);
  const widenFromLabel = widened.from;
  const widenToLabel = widened.to;
  const widenFromPct = widened.fromPct;
  const widenToPct = widened.toPct;

  const ticks = hourTicks(DRIVE_START, DRIVE_END);

  return (
    <div className="pbody">
      <div className="empty" style={{ marginBottom: 18 }}>
        <div className="empty-ic">
          <Search size={34} color="#64748b" strokeWidth={2} />
        </div>
        <h2 className="empty-t">
          {scope.from} – {scope.to} 구간에서는 찾지 못했어요
        </h2>
        <p className="empty-s">
          영상 {scope.files}개를 모두 확인했지만 말씀하신 상황과 맞는 장면이 없었습니다. 아래 방법 중 하나를 골라주세요.
        </p>
        <div className="btnrow" style={{ justifyContent: 'center' }}>
          <Button variant="primary" size="large" onClick={() => dispatch({ type: 'WIDEN' })}>
            앞뒤 30분 더 찾아보기
          </Button>
          <Button size="large" onClick={() => dispatch({ type: 'REDESCRIBE' })}>
            시간을 다시 말할게요
          </Button>
          <Button size="large" onClick={() => dispatch({ type: 'EDIT_VEHICLE' })}>
            차량 특징 고치기
          </Button>
        </div>
      </div>

      <div className="grid2">
        <Panel className="axis-p">
          <div className="axis-hd">
            <span className="axis-t">넓히면 이만큼 더 찾습니다</span>
            <span className="axis-s">
              영상 <b>{scope.files}개 → {widened.files}개</b> · 약 <span className="mono">4분</span> 더 걸립니다
            </span>
          </div>
          <div className="axis" style={{ marginTop: 34 }}>
            <div className="aseg rest" style={{ left: 0, right: 0 }} />
            <div
              className="aseg scope"
              style={{ left: `${widenFromPct}%`, width: `${widenToPct - widenFromPct}%` }}
            />
            <div
              className="aseg scanned"
              style={{ left: `${scope.fromPct}%`, width: `${scope.toPct - scope.fromPct}%` }}
            />
            <div className="aticks" />
            <div className="abr" style={{ left: `${widenFromPct}%`, width: `${widenToPct - widenFromPct}%` }}>
              <span className="abr-l">
                {widenFromLabel} – {widenToLabel}
              </span>
            </div>
          </div>
          <div className="aruler">
            <span className="atk e0">{DRIVE_START}</span>
            {ticks.map((tick) => (
              <span key={tick.label} className="atk" style={{ left: `${tick.pct}%` }}>
                {tick.label}
              </span>
            ))}
            <span className="atk e1">{DRIVE_END}</span>
          </div>
          <div className="alegend">
            <span className="alg">
              <i className="scanned" />
              이미 확인함
            </span>
            <span className="alg">
              <i className="scope" />
              새로 확인할 구간
            </span>
          </div>
        </Panel>

        <Panel>
          <SecLabel>
            <span>비슷하지만 다른 장면 {similar.length}개</span>
          </SecLabel>
          <p
            style={{
              fontSize: 'calc(16px * var(--font-scale))',
              color: 'var(--muted)',
              fontWeight: 550,
              lineHeight: 1.6,
              margin: '0 0 14px',
            }}
          >
            말씀하신 조건과 일부만 맞습니다. 혹시 이 중에 있는지 확인해보세요.
          </p>
          <div className="kv" style={{ borderTop: 0 }}>
            {similar.map((c, i) => (
              <div
                key={c.id}
                className="kvr"
                style={{
                  gridTemplateColumns: '82px minmax(0,1fr) auto',
                  alignItems: 'center',
                  borderBottom: i === similar.length - 1 ? 0 : undefined,
                }}
              >
                <div style={{ width: 82, borderRadius: 6, overflow: 'hidden' }}>
                  <EvidenceFrame size="small" scene={c.scene} time={c.time} />
                </div>
                <span>
                  <span className="kv-val mono" style={{ fontSize: 'calc(17px * var(--font-scale))' }}>
                    {c.time}
                  </span>
                  <span className="kv-src">{c.matches.map((m) => m.text).join(' · ')}</span>
                </span>
                <button type="button" className="btn sm" onClick={() => dispatch({ type: 'SHOW_SIMILAR' })}>
                  보기
                </button>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
