import { useState } from 'react';
import type { ChangeEvent, JSX, KeyboardEvent } from 'react';
import { Bell, CheckCircle } from 'lucide-react';
import type { Action, AppState, Field } from '../types';
import { Panel } from '../components/Panel';
import { SecLabel } from '../components/SecLabel';
import { Button } from '../components/Button';
import { KVRow } from '../components/KVRow';
import { isPlateShaped } from '../utils/plate';

/**
 * DESIGN-stage1-mockups.html 1800–1965 (화면 7 · 불확실한 번호판 확인하기) + PROTOTYPE-SPEC.md §5.9/§4.2/§6-1.
 *
 * The mockup's own `.plate-stage`/`.plate`/`.frames`/`.fr`/`.sum` CSS (global.css "PLATE
 * (PrepareScreen)" block, Task 1) was already built with this exact screen in mind, so this
 * component leans on those classes/markup shapes verbatim rather than inventing new ones.
 *
 * `EvidenceFrame`'s `scene` prop is typed `Candidate['scene']` and doesn't fit the four plate-
 * quality close-ups (선명/흔들림/반사/가림) — those are built locally below as `PlateFrameThumb`,
 * a separate small inline-SVG component using the `.fr` class (not `.ev`), per the brief.
 */

type FrameEffect = 'clean' | 'shaky' | 'glare' | 'occluded';

const FRAME_DEFS: { effect: FrameEffect; label: string; time: string }[] = [
  { effect: 'clean', label: '선명', time: '18:31:51' },
  { effect: 'shaky', label: '흔들림', time: '18:31:52' },
  { effect: 'glare', label: '반사', time: '18:31:53' },
  { effect: 'occluded', label: '가림', time: '18:31:54' },
];

// scenario.plateVariant (ScenarioBar, task-10) is a *demo-only* lens over the always-partial
// state.case.plate mock value — it decides what this screen's left-side close-up/frames show,
// never what state.case.plate actually holds. 'unreadable' presents the plate as if
// value:null; 'clear' presents a legible '12가 3456' that still requires user action (no
// shortcut "already confirmed" state exists — see PrepareScreen §5.9's "이 번호가 맞아요" ban).
function derivePlateDisplayValue(
  variant: AppState['scenario']['plateVariant'],
  actualValue: string | null,
): string | null {
  if (variant === 'unreadable') return null;
  if (variant === 'clear') return '12가 3456';
  return actualValue; // 'partial' — state.case.plate.value as-is, e.g. '12가 34?6'
}

/** Splits on the first '?' to wrap the uncertain character in `.q` styling, same as the mockup's
 * `12가&nbsp;34<span class="q">?</span>6`. No-op (plain text) when there's no '?' to highlight. */
function PlateGlyph(props: { value: string }): JSX.Element {
  const qIndex = props.value.indexOf('?');
  if (qIndex === -1) {
    return <span className="plate">{props.value}</span>;
  }
  return (
    <span className="plate">
      {props.value.slice(0, qIndex)}
      <span className="q">?</span>
      {props.value.slice(qIndex + 1)}
    </span>
  );
}

/**
 * One of the four selectable plate-quality close-ups. Purely cosmetic (brief: "clickable to
 * swap which one is shown large; ... no state implications") — `text` already reflects the
 * current scenario.plateVariant, this component only draws the per-frame quality effect on
 * top (blur / glare / obstruction), it never decides plate content itself.
 */
function PlateFrameThumb(props: {
  effect: FrameEffect;
  time: string;
  text: string | null;
  active: boolean;
  index: number;
  onSelect: () => void;
}): JSX.Element {
  const { effect, time, text, active, index, onSelect } = props;
  const plaqueFill = text === null ? '#454d57' : '#e7eaee';

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect();
    }
  }

  return (
    <div
      className={`fr${active ? ' on' : ''}`}
      role="button"
      tabIndex={0}
      aria-pressed={active}
      aria-label={`${FRAME_DEFS[index].label} 장면 · ${time}`}
      onClick={onSelect}
      onKeyDown={handleKeyDown}
      style={{ cursor: 'pointer' }}
    >
      <svg
        viewBox="0 0 160 100"
        preserveAspectRatio="none"
        aria-hidden="true"
        style={effect === 'shaky' ? { filter: 'blur(1.6px)' } : undefined}
      >
        <rect width="160" height="100" fill="#232a33" />
        <rect x="30" y="34" width="100" height="32" rx="4" fill={plaqueFill} />
        {text !== null && (
          <text
            x="80"
            y="57"
            fontFamily="'Roboto Mono', monospace"
            fontSize="18"
            fontWeight="700"
            fill="#151a20"
            textAnchor="middle"
          >
            {text.replace(/\s+/g, '')}
          </text>
        )}
        {effect === 'glare' && <rect x="72" y="20" width="30" height="60" fill="#fff" opacity="0.82" />}
        {effect === 'occluded' && <rect x="96" y="26" width="46" height="48" fill="#3d444d" />}
      </svg>
      <span className="fr-n">{index + 1}</span>
      <span className="fr-l">{time}</span>
    </div>
  );
}

// Presentational-only observation copy for the situation "읽고 확인하기" drawer — restates
// state.case.situation.source/.value, invents nothing new (brief's explicit instruction).
function situationObservationLines(situation: Field): string[] {
  const value = situation.value ?? '기록된 상황 정보가 없습니다';
  return [
    `${situation.source}을 바탕으로 정리한 내용입니다.`,
    `정리된 상황: ${value}`,
    '실제와 다르면 아래에서 다른 상황으로 고치거나, 잘 모르겠다고 남겨두세요.',
  ];
}

export function PrepareScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const { plate, occurredAt, situation, location, reportType } = state.case;

  const [activeFrame, setActiveFrame] = useState(0);
  const [plateEditing, setPlateEditing] = useState(false);
  const [plateDraft, setPlateDraft] = useState('');

  const [situationExpanded, setSituationExpanded] = useState(false);
  const [situationDraft, setSituationDraft] = useState<string | null>(null); // non-null = "다른 상황" edit mode

  // ---------- §4.2 gate — UX-only mirror of machine.ts's real NEXT guard, never a second source
  // of truth. occurredAt/location/reportType never count (Core Flow §13, spec's explicit
  // "사용자 확인을 요구하지 않는다"). ----------
  const plateOk = plate.status !== 'needs-review';
  const situationOk = situation.status === 'user-confirmed';
  const missing: string[] = [];
  if (!plateOk) missing.push('차량번호를 확인해주세요');
  if (!situationOk) missing.push('신고 상황을 확인해주세요');
  const remaining = missing.length;

  const headerTitle = remaining === 0 ? '확인이 끝났습니다' : missing[0];
  const headerSub =
    remaining === 0
      ? '다음 단계로 넘어갈 준비가 됐습니다.'
      : remaining === 2
        ? '차량번호와 신고 상황을 모두 확인하면 다음 단계로 넘어갈 수 있어요.'
        : !plateOk
          ? '다섯 번째 글자를 확실하게 읽지 못했습니다. 장면을 넘겨보며 확인해주세요.'
          : '영상에서 관찰한 내용이 맞는지 읽고 확인해주세요.';

  // ---------- plate close-up (left) — presentational only, see derivePlateDisplayValue ----------
  const displayPlateValue = derivePlateDisplayValue(state.scenario.plateVariant, plate.value);
  const activeDef = FRAME_DEFS[activeFrame];
  const frameCaption =
    displayPlateValue === null
      ? '네 장면 모두 번호판 글자를 알아볼 수 없습니다.'
      : state.scenario.plateVariant === 'clear'
        ? '네 장면 모두 번호판이 선명하게 보입니다.'
        : '2번은 흔들렸고, 3번은 빛이 반사됐고, 4번은 뒷차에 가렸습니다.';

  function handlePlateDraftChange(e: ChangeEvent<HTMLInputElement>) {
    setPlateDraft(e.target.value);
  }
  function openPlateEdit() {
    setPlateDraft('');
    setPlateEditing(true);
  }
  function cancelPlateEdit() {
    setPlateEditing(false);
    setPlateDraft('');
  }
  function savePlate() {
    if (!plateDraft.trim()) return;
    // §6-1 — store exactly what was typed, never reformatted.
    dispatch({ type: 'SET_FIELD', key: 'plate', field: { value: plateDraft, source: '사용자 입력', status: 'user-confirmed' } });
    setPlateEditing(false);
    setPlateDraft('');
  }
  function markPlateUnknown() {
    // §5.9 — no confirm dialog, immediate.
    dispatch({ type: 'SET_FIELD', key: 'plate', field: { value: null, source: '판독 불가', status: 'unknown' } });
    setPlateEditing(false);
    setPlateDraft('');
  }
  const plateShapeWarning = plateDraft.trim() !== '' && !isPlateShaped(plateDraft);

  // ---------- situation drawer (right) ----------
  function closeSituationPanel() {
    setSituationExpanded(false);
    setSituationDraft(null);
  }
  function confirmSituation() {
    dispatch({ type: 'SET_FIELD', key: 'situation', field: { ...situation, status: 'user-confirmed' } });
    closeSituationPanel();
  }
  function saveSituationEdit() {
    if (situationDraft === null || !situationDraft.trim()) return;
    dispatch({
      type: 'SET_FIELD',
      key: 'situation',
      field: { value: situationDraft.trim(), source: '사용자 수정', status: 'user-confirmed' },
    });
    closeSituationPanel();
  }
  function leaveSituationUnsure() {
    // §5.9 — stays 'ai-estimated'. Still calls SET_FIELD (brief: all three buttons dispatch it).
    dispatch({ type: 'SET_FIELD', key: 'situation', field: { ...situation, status: 'ai-estimated' } });
    closeSituationPanel();
  }

  function plateValueText(field: Field): string {
    if (field.status === 'unknown') return '읽을 수 없음';
    return field.value ?? '';
  }

  return (
    <div className="pbody">
      <div className="ptop">
        <div>
          <h2 className="ptitle">{headerTitle}</h2>
          <p className="psub">{headerSub}</p>
        </div>
        <div className="sum" style={{ gridTemplateColumns: '1fr', minWidth: 210 }}>
          <div className="sumc" style={{ padding: '13px 16px', gap: 12 }}>
            <span
              className="sum-ic"
              style={{
                width: 42,
                height: 42,
                flex: '0 0 42px',
                borderRadius: 11,
                background: remaining > 0 ? 'var(--orange-soft)' : 'var(--green-soft)',
                color: remaining > 0 ? 'var(--orange-ink)' : 'var(--green-deep)',
              }}
            >
              {remaining > 0 ? <Bell size={22} /> : <CheckCircle size={22} />}
            </span>
            <span>
              <span className="sum-k">남은 확인</span>
              <span className="sum-v">{remaining}개</span>
            </span>
          </div>
        </div>
      </div>

      <div className="grid2 wide">
        <div className="stack">
          <Panel>
            <SecLabel>
              <span>{FRAME_DEFS[activeFrame].label} 장면</span>
              <span className="n">FILE_023.MP4 · {activeDef.time}</span>
            </SecLabel>
            <div className="plate-stage">
              {/* PROTOTYPE-SPEC.md §2: "모든 글꼴 크기는 calc(Npx * var(--font-scale))로 쓴다" —
                  fixed at 14px (Task 17 fix), not a raw px literal that ignores the ScenarioBar's
                  font-scale control. 14px sits inside this video-mockup overlay's 11px floor. */}
              <span className="ev-chip tr" style={{ fontSize: 'calc(14px * var(--font-scale))' }}>4.0배 확대</span>
              {displayPlateValue === null ? (
                <div style={{ textAlign: 'center' }}>
                  <span className="plate" style={{ opacity: 0.32, filter: activeDef.effect === 'shaky' ? 'blur(2px)' : undefined }}>
                    ········
                  </span>
                  <p style={{ marginTop: 14, color: '#c6ccd4', fontWeight: 700, fontSize: 'calc(16px * var(--font-scale))' }}>
                    이 장면에서는 번호판을 알아볼 수 없습니다
                  </p>
                </div>
              ) : (
                <div style={activeDef.effect === 'shaky' ? { filter: 'blur(2px)' } : undefined}>
                  <PlateGlyph value={displayPlateValue} />
                </div>
              )}
              {activeDef.effect === 'glare' && (
                <div
                  style={{
                    position: 'absolute', top: '28%', left: '38%', width: '20%', height: '58%',
                    background: 'rgba(255,255,255,.55)', filter: 'blur(6px)', pointerEvents: 'none',
                  }}
                />
              )}
              {activeDef.effect === 'occluded' && (
                <div
                  style={{
                    position: 'absolute', top: '22%', right: '16%', width: '20%', height: '56%',
                    background: '#232a33', pointerEvents: 'none',
                  }}
                />
              )}
            </div>

            <div style={{ marginTop: 20 }}>
              <SecLabel>
                <span>다른 장면에서도 확인해보세요</span>
              </SecLabel>
            </div>
            <div className="frames">
              {FRAME_DEFS.map((def, i) => (
                <PlateFrameThumb
                  key={def.effect}
                  effect={def.effect}
                  time={def.time}
                  text={displayPlateValue}
                  active={i === activeFrame}
                  index={i}
                  onSelect={() => setActiveFrame(i)}
                />
              ))}
            </div>
            <p style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--muted)', fontWeight: 550, margin: '12px 0 0', lineHeight: 1.55 }}>
              {frameCaption}
            </p>
          </Panel>

          <Panel>
            <SecLabel>
              <span>어떻게 하시겠어요?</span>
            </SecLabel>
            {plateEditing ? (
              <div className="stack" style={{ gap: 10 }}>
                <input
                  autoFocus
                  className="field"
                  value={plateDraft}
                  onChange={handlePlateDraftChange}
                  placeholder="예: 12가3456"
                  style={{ fontFamily: "'Roboto Mono', 'SF Mono', Consolas, monospace", fontWeight: 700 }}
                />
                {plateShapeWarning && (
                  <p style={{ margin: 0, fontSize: 'calc(15px * var(--font-scale))', color: 'var(--orange-ink)', fontWeight: 600 }}>
                    일반적인 번호판 형식과 달라 보여요. 그래도 저장할 수 있습니다.
                  </p>
                )}
                <div className="btngrid c2">
                  <Button variant="primary" onClick={savePlate} disabled={!plateDraft.trim()}>저장</Button>
                  <Button onClick={cancelPlateEdit}>취소</Button>
                </div>
              </div>
            ) : (
              <>
                <div className="btngrid c2">
                  <Button variant="primary" size="large" onClick={openPlateEdit}>번호 직접 입력</Button>
                  <Button size="large" onClick={markPlateUnknown}>읽을 수 없음으로 두기</Button>
                </div>
                <p style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--muted)', fontWeight: 550, margin: '12px 0 0', lineHeight: 1.55 }}>
                  읽을 수 없음으로 두면 차량번호 없이 신고자료를 만듭니다.
                </p>
              </>
            )}
          </Panel>
        </div>

        <Panel>
          <SecLabel>
            <span>사건 기록</span>
            <span className="n" style={{ color: remaining > 0 ? 'var(--orange-ink)' : 'var(--green-deep)' }}>
              확인할 항목 {remaining}개
            </span>
          </SecLabel>
          <div className="kv">
            <KVRow
              tint
              label="차량번호"
              value={plateValueText(plate)}
              source={plate.source}
              status={plate.status}
            />
            <KVRow
              tint
              label="발생시각"
              value={occurredAt.value ?? ''}
              source={occurredAt.source}
              status={occurredAt.status}
            />
            <KVRow
              tint
              label="신고 상황"
              value={situation.value ?? ''}
              source={situation.source}
              status={situation.status}
              action={
                situation.status !== 'user-confirmed' && !situationExpanded
                  ? { label: '읽고 확인하기', onClick: () => setSituationExpanded(true) }
                  : undefined
              }
            />
            {situationExpanded && (
              <div style={{ padding: '4px 0 18px', borderBottom: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
                  <button type="button" className="btn sm" onClick={closeSituationPanel}>접기</button>
                </div>
                <ul style={{ listStyle: 'none', margin: '0 0 14px', padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {situationObservationLines(situation).map((line, i) => (
                    <li
                      key={i}
                      style={{
                        display: 'flex', gap: 8, fontSize: 'calc(16px * var(--font-scale))',
                        color: 'var(--ink-2)', fontWeight: 600, lineHeight: 1.5,
                      }}
                    >
                      <span style={{ color: 'var(--muted)', flex: '0 0 auto' }}>{i + 1}.</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
                {situationDraft === null ? (
                  <div className="btngrid c3">
                    <Button variant="primary" onClick={confirmSituation}>맞아요</Button>
                    <Button onClick={() => setSituationDraft(situation.value ?? '')}>다른 상황</Button>
                    <Button onClick={leaveSituationUnsure}>잘 모르겠어요</Button>
                  </div>
                ) : (
                  <div className="stack" style={{ gap: 10 }}>
                    <input
                      autoFocus
                      className="field"
                      value={situationDraft}
                      onChange={(e) => setSituationDraft(e.target.value)}
                    />
                    <div className="btngrid c2">
                      <Button variant="primary" onClick={saveSituationEdit} disabled={!situationDraft.trim()}>저장</Button>
                      <Button onClick={() => setSituationDraft(null)}>취소</Button>
                    </div>
                  </div>
                )}
              </div>
            )}
            <KVRow
              tint
              label="위치"
              value={location.value ?? ''}
              source={location.source}
              status={location.status}
            />
            <KVRow
              tint
              label="신고유형"
              value={reportType.value ?? ''}
              source={reportType.source}
              status={reportType.status}
            />
          </div>
        </Panel>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14, marginTop: 18 }}>
        <p style={{ margin: 0, fontSize: 'calc(16px * var(--font-scale))', fontWeight: 700, color: remaining > 0 ? 'var(--orange-ink)' : 'var(--green-deep)' }}>
          {remaining > 0 ? missing.join(' · ') : '확인이 모두 끝났습니다.'}
        </p>
        <Button variant="primary" size="large" disabled={remaining > 0} onClick={() => dispatch({ type: 'NEXT' })}>
          다음
        </Button>
      </div>
    </div>
  );
}
