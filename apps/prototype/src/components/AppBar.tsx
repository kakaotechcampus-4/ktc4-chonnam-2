import type { JSX } from 'react';
import type { Step } from '../types';

const RAIL: { n: number; label: string }[] = [
  { n: 1, label: '영상 올리기' },
  { n: 2, label: '사건 설명' },
  { n: 3, label: '범위 확인' },
  { n: 4, label: '사건 찾기' },
  { n: 5, label: '사건 선택' },
  { n: 6, label: '정보 확인' },
  { n: 7, label: '신고자료' },
];

// Step -> rail index. Verified against DESIGN-stage1-mockups.html's own
// per-screen <div class="rail"> markup (§03 화면, 화면 1–9), not just the
// brief's prose guess: 화면7(prepare) shows "rl on" at index 6, but 화면8
// (review, "신고자료 최종 확인") and 화면9 (handoff) both show "rl on" at
// index 7 — review does NOT share index 6 with prepare. searching/no-result
// both show index 4, confirming that group (failed included by the same
// reasoning, since no separate screen exists for it in the 9-screen set).
const STEP_INDEX: Record<Step, number> = {
  upload: 1,
  describe: 2,
  scope: 3,
  searching: 4,
  'no-result': 4,
  failed: 4,
  candidates: 5,
  prepare: 6,
  review: 7,
  handoff: 7,
};

// Display-only progress rail — no click handlers, no navigation.
//
// Final review fix wave finding #6: this component used to also accept a `statusText?: string`
// prop for spec §5.1's "오른쪽 상태 텍스트는 화면마다 다르다", but App.tsx never passed one, so
// the whole feature was dead code — no per-step copy for that text exists anywhere in this
// task's briefs or the mockup captions to invent safely at this stage. Removed rather than wired
// up with guessed copy (lower-risk per the fix-wave brief's own "pick whichever is lower-risk").
export function AppBar(props: { step: Step }): JSX.Element {
  const current = STEP_INDEX[props.step];
  return (
    <header className="appbar">
      <div className="appbar-row">
        <div className="logo">
          <img className="logo-mark" src="/meerkat.png" alt="대신고" />
          <span className="logo-txt">
            <span className="logo-t">대신고</span>
            <span className="logo-sub">신고할 순간을 대신 찾아드립니다</span>
          </span>
        </div>
      </div>
      <div className="rail">
        {RAIL.map((r) => (
          <div key={r.n} className={`rl${r.n === current ? ' on' : r.n < current ? ' done' : ''}`}>
            <span className="rl-n">{r.n}</span>
            <span className="rl-t">{r.label}</span>
          </div>
        ))}
      </div>
    </header>
  );
}
