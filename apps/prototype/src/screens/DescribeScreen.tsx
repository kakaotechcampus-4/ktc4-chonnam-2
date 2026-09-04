import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';
import type { Action, AppState } from '../types';
import { Panel } from '../components/Panel';
import { SecLabel } from '../components/SecLabel';
import { Button } from '../components/Button';
import { DRIVE_START, DRIVE_END } from '../mock/files';

/**
 * DESIGN-stage1-mockups.html 1158–1269 (화면 2 · 기억나는 사건 설명하기).
 *
 * §5.3 — the preset button and the empty-textarea submit-label switch are prototype-only
 * affordances (not present in the static mockup, which only ever shows the filled state):
 * evaluators need a one-click way to fill the textarea, and an empty submit must never be
 * blocked — it should read as "search everything, no time hint" instead of look disabled.
 *
 * This screen never parses `raw` itself — TIME_RE/VEHICLE_RE/EVENT_RE/LOCATION_RE all live in
 * machine.ts's SUBMIT_MEMORY handler (Task 3). The textarea pre-fills from
 * `state.case.hints.raw` so a future REDESCRIBE (re-entering from `no-result`, per §4.1) shows
 * the user's prior text rather than a blank box.
 */
const PRESET_TEXT = '6시 반쯤 흰 SUV가 실선을 넘어 끼어들었어요. 미금역 근처였던 것 같아요';

export function DescribeScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const [raw, setRaw] = useState(state.case.hints.raw);

  const isEmpty = raw.trim().length === 0;

  function handleChange(e: ChangeEvent<HTMLTextAreaElement>) {
    setRaw(e.target.value);
  }
  function handlePreset() {
    setRaw(PRESET_TEXT);
  }
  function handleSubmit() {
    dispatch({ type: 'SUBMIT_MEMORY', raw });
  }

  return (
    <div className="pbody">
      <div className="ptop">
        <div>
          <h2 className="ptitle">무슨 일이 있었는지 말씀해주세요</h2>
          <p className="psub">기억나는 만큼만 적으시면 됩니다. 정확하지 않아도 괜찮습니다.</p>
        </div>
      </div>

      <div className="grid2 wide">
        <div className="stack">
          <div className="memo">
            <textarea
              className="memo-t"
              value={raw}
              onChange={handleChange}
              aria-label="사건 설명"
              placeholder="예: 6시 반쯤, 흰색 SUV, 실선 침범, 미금역 근처"
              rows={3}
              style={{
                width: '100%',
                border: 'none',
                outline: 'none',
                resize: 'vertical',
                background: 'transparent',
                fontFamily: 'inherit',
                padding: 0,
              }}
            />
            <div className="memo-f">
              <span className="psub" style={{ margin: 0 }}>바로 적기 어려우면 예시를 넣어보세요</span>
              <Button variant="default" onClick={handlePreset}>예시 문장 넣기</Button>
            </div>
          </div>

          <Panel>
            <SecLabel>
              <span>내 영상 전체</span>
              <span className="n">{DRIVE_START} – {DRIVE_END}</span>
            </SecLabel>
            <div className="axis">
              <div className="aseg rest" style={{ left: 0, right: 0 }} />
              <div className="aticks" />
            </div>
            <div className="aruler">
              <span className="atk e0">{DRIVE_START}</span>
              <span className="atk" style={{ left: '23.4%' }}>16:00</span>
              <span className="atk" style={{ left: '51.9%' }}>17:00</span>
              <span className="atk" style={{ left: '80.3%' }}>18:00</span>
              <span className="atk e1">{DRIVE_END}</span>
            </div>
            <p style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--muted)', fontWeight: 600, margin: '14px 0 0' }}>
              말씀하신 시간에 맞춰 먼저 찾아볼 구간을 정합니다. 나머지 영상도 그대로 남습니다.
            </p>
          </Panel>

          <div className="btnrow">
            <Button variant="primary" size="large" onClick={handleSubmit}>
              {isEmpty ? '시간 단서 없이 전체 찾기' : '사건 찾기'}
            </Button>
          </div>
        </div>

        <div className="stack">
          <Panel>
            <SecLabel>이런 것을 적어주세요</SecLabel>
            <div className="egs">
              <div className="eg">
                <span className="eg-k">시간</span>
                <span className="eg-v">6시 반쯤<br />퇴근길 7시 전후</span>
              </div>
              <div className="eg">
                <span className="eg-k">상황</span>
                <span className="eg-v">빨간불인데 직진<br />실선 넘어 끼어듦</span>
              </div>
              <div className="eg">
                <span className="eg-k">차량</span>
                <span className="eg-v">흰색 SUV<br />검은 승용차 · 오토바이</span>
              </div>
              <div className="eg">
                <span className="eg-k">위치</span>
                <span className="eg-v">미금역 근처<br />○○IC 지난 뒤</span>
              </div>
            </div>
          </Panel>

          <Panel>
            <SecLabel>대신고가 찾을 수 있는 것</SecLabel>
            <div className="chips" style={{ marginBottom: 14 }}>
              <span className="chip gray">신호위반</span>
              <span className="chip gray">중앙선 침범</span>
              <span className="chip gray">진로변경</span>
              <span className="chip gray">이륜차 안전모 미착용</span>
            </div>
            <p style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--ink-2)', lineHeight: 1.6, margin: '0 0 12px', fontWeight: 550 }}>
              결과는 <b>신고할 가능성이 있는 사건 후보</b>이며 법적 위반 확정이 아닙니다.
              실제 사건과 신고정보는 제출 전에 직접 확인해주세요.
            </p>
            <div className="disc">
              <b>대신고는 정부·공공기관 서비스가 아닙니다.</b>
              신고 접수는 안전신문고에서 직접 하셔야 합니다.
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
