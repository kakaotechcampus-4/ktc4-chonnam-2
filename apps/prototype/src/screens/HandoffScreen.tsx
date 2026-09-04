import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Check } from 'lucide-react';
import type { Action, AppState } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { Toast } from '../components/Toast';
import { reportBodyFor } from '../utils/reportBody';

/**
 * DESIGN-stage1-mockups.html 2177–2405 (화면 9 · 안전신문고로 옮겨 담기) + PROTOTYPE-SPEC.md §5.11.
 *
 * "이 화면의 정확성이 이번 프로토타입에서 두 번째로 중요하다" — the whole point of this screen
 * is that the left (blue) three items are things a real 안전신문고 text field can receive via
 * paste, and the right (orange) four items are not, so mixing a copy button into the right list
 * would be actively misleading (§5.11's own reasoning, restated in the mockup's cap text). That
 * split is kept structurally: `PASTE_ITEMS`-shaped rendering only ever appears in the left panel,
 * and the right panel's `<Xrow>` never accepts an onCopy at all (its only exception, 발생장소's
 * map-search-term copy, is wired through a distinct, separately-named handler so it can never be
 * confused with a generic "add a copy button here" knob).
 *
 * 신고 내용: rather than re-deriving the report paragraph a second time (and risking the two
 * drifting apart), this screen imports `reportBodyFor` from utils/reportBody.ts — the exact
 * same composition ReviewScreen uses, same source of truth (fix wave finding #3 moved this
 * helper there so `reportBody` — the separate `CaseState` field an edit on ReviewScreen now
 * writes to — has one place to live, instead of the edit being mapped onto `title`).
 *
 * 발생일자/발생시각: `state.case.occurredAt.value` is stored as one combined
 * `'YYYY-MM-DD HH:MM:SS'` string (see mock/caseData.ts); `parseOccurredAt` below actually splits
 * it apart (date vs time, and the guidance sentences' month/day/H:M) rather than hard-coding the
 * mock's '8월 24일' / '18:31:48' text, since (per machine.ts's SELECT handling) this value is
 * always reset to the same mock shape but is still a real Field the app could vary.
 *
 * 발생장소 예외: the mockup's example copies the bare place name ("미금역"), not the full field
 * value ("미금역 인근"). `deriveSearchTerm` strips a trailing 근처/인근/부근/앞/뒤 suffix so the
 * copied search term still tracks whatever `location.value` actually holds instead of a literal
 * hard-coded "미금역".
 *
 * "다른 사건 찾기" in the mockup's bottom button row is the one affordance in this screen's range
 * that reads as a "새 사건 시작"-type action, and it lines up exactly with `machine.ts`'s
 * `NEW_CASE` case (guarded to only fire from `state.step === 'handoff'`, resetting to a fresh
 * case at 'describe'). The mockup's neighboring "최종 확인으로" button is NOT wired: there is no
 * reducer case that takes 'handoff' back to 'review' (`BACK` is guarded to only fire from
 * 'review'), and this screen's brief only lists `NEW_CASE` as a consumed action — wiring
 * "최종 확인으로" would mean inventing new reducer behavior outside this task's scope, so it is
 * left out entirely rather than shipped as a dead button (no other screen in this app renders a
 * `.btn` with no effect).
 */

const SAFETY_REPORT_URL = 'https://www.safetyreport.go.kr/';
const TOAST_MESSAGE = '복사했습니다';
const TOAST_DURATION_MS = 2000;

/** §5.11 clipboard helper — try the modern API first, fall back to the hidden-textarea +
 * execCommand trick for browsers/contexts where `navigator.clipboard` is unavailable or denied. */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (!navigator.clipboard) throw new Error('navigator.clipboard unavailable');
    // Race against a short timeout, not just a catch on rejection: in some embedded/automated
    // contexts (verified while walking this screen end-to-end) the browser silently stalls on an
    // unanswerable clipboard permission prompt instead of rejecting, which would otherwise hang
    // this forever and never reach the execCommand fallback below.
    // Task 17 fix: if the timeout branch wins the race, `writeTextPromise` is still pending —
    // when it later settles with nothing awaiting it, an unhandled rejection would otherwise
    // surface as a console warning. Attaching a no-op `.catch` to a *separate* reference (not
    // the one passed into Promise.race) marks the promise as handled without swallowing its
    // rejection for the race itself — a fast rejection still loses the race correctly and falls
    // through to the execCommand fallback below.
    const writeTextPromise = navigator.clipboard.writeText(text);
    writeTextPromise.catch(() => {});
    await Promise.race([
      writeTextPromise,
      new Promise((_, reject) => setTimeout(() => reject(new Error('clipboard write timed out')), 1200)),
    ]);
    return true;
  } catch {
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.top = '-1000px';
      textarea.style.left = '-1000px';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(textarea);
      return ok;
    } catch {
      return false;
    }
  }
}

// §6-1 "복사 버튼은 value를 그대로 복사한다" — no reformatting, ever.
function plateValueText(c: AppState['case']): string {
  return c.plate.status === 'unknown' ? '' : (c.plate.value ?? '');
}

// Splits state.case.occurredAt.value ('YYYY-MM-DD HH:MM:SS') into the two right-column rows'
// display values and their "where to click" guidance sentences.
function parseOccurredAt(value: string | null): {
  dateValue: string;
  dateGuidance: string;
  timeValue: string;
  timeGuidance: string;
} {
  if (!value) {
    return {
      dateValue: '알 수 없음',
      dateGuidance: '달력에서 영상 속 발생일을 직접 고르세요.',
      timeValue: '알 수 없음',
      timeGuidance: '시·분을 각각 직접 고르세요.',
    };
  }
  const [datePart, timePart] = value.split(' ');
  const [, m, d] = (datePart ?? '').split('-').map((n) => Number.parseInt(n, 10));
  const [hh, mm] = (timePart ?? '').split(':');
  const dateGuidance =
    Number.isFinite(m) && Number.isFinite(d)
      ? `달력에서 ${m}월 ${d}일을 누르세요.`
      : '달력에서 해당 날짜를 누르세요.';
  const timeValue = hh && mm ? `${Number.parseInt(hh, 10)}시 ${Number.parseInt(mm, 10)}분` : (timePart ?? value);
  const timeGuidance = timePart
    ? `시·분을 각각 고르세요. 영상에 찍힌 시각은 ${timePart}입니다.`
    : '시·분을 각각 고르세요.';
  return { dateValue: datePart ?? value, dateGuidance, timeValue, timeGuidance };
}

// 발생장소 예외 — the mockup copies the bare place name ("미금역"), not the full field value
// ("미금역 인근"), so this strips a trailing 근처/인근/부근/앞/뒤 the same way a person would when
// typing it into a map search box.
function deriveSearchTerm(location: string | null): string | null {
  if (!location) return null;
  const stripped = location.replace(/\s*(근처|인근|부근|앞|뒤)$/u, '').trim();
  return stripped || location;
}

export function HandoffScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const { title, reportType, occurredAt, location, clip } = state.case;

  const reportContent = reportBodyFor(state.case);
  const titleText = title.value ?? '';
  const plateText = plateValueText(state.case);

  // Toast visibility — this screen owns the 2s timer (Toast itself has none, Task 4).
  // `toastNonce` increments on every successful copy so a second copy while the toast is still
  // showing restarts the full 2 seconds rather than being swallowed by an unchanged boolean.
  const [toastNonce, setToastNonce] = useState(0);
  const [toastVisible, setToastVisible] = useState(false);

  useEffect(() => {
    if (toastNonce === 0) return;
    setToastVisible(true);
    const timer = setTimeout(() => setToastVisible(false), TOAST_DURATION_MS);
    return () => clearTimeout(timer);
  }, [toastNonce]);

  async function handleCopy(text: string) {
    const ok = await copyToClipboard(text);
    if (ok) setToastNonce((n) => n + 1);
  }

  function handleCopyAll() {
    const combined = [`제목: ${titleText}`, `차량번호: ${plateText}`, `신고 내용: ${reportContent}`].join('\n');
    void handleCopy(combined);
  }

  function handleOpenSafetyReport() {
    window.open(SAFETY_REPORT_URL, '_blank', 'noopener');
  }

  function handleNewCase() {
    dispatch({ type: 'NEW_CASE' });
  }

  // No real file exists in this prototype — this creates a tiny placeholder text file under the
  // clip's real name so "영상 내려받기" still does something rather than being a dead button (no
  // other screen in this app ships a `.btn` with no effect).
  function handleDownloadClip() {
    const blob = new Blob(
      [`이 파일은 프로토타입 예시입니다. 실제 영상은 포함되어 있지 않습니다.\n\n파일명: ${clip.name}\n길이: ${clip.duration}\n용량: ${clip.size}`],
      { type: 'text/plain' },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = clip.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const { dateValue, dateGuidance, timeValue, timeGuidance } = parseOccurredAt(occurredAt.value);
  const searchTerm = deriveSearchTerm(location.value);

  return (
    <div className="pbody">
      <div className="ptop">
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          <span
            style={{
              width: 64, height: 64, borderRadius: 18, background: 'var(--green-soft)',
              display: 'grid', placeItems: 'center', flex: '0 0 64px',
            }}
          >
            <Check size={34} color="var(--green)" strokeWidth={2.6} />
          </span>
          <div>
            <h2 className="ptitle">신고자료가 준비됐어요</h2>
            <p className="psub">영상을 내려받고 안전신문고를 연 뒤, 아래 내용을 옮겨 담으시면 됩니다.</p>
          </div>
        </div>
      </div>

      <div className="hand" style={{ marginBottom: 20 }}>
        <div className="hc">
          <span className="hc-n">1</span>
          <span className="hc-t">영상 내려받기</span>
          <p className="hc-s">
            <span className="mono" style={{ color: 'var(--ink-2)', fontWeight: 700 }}>{clip.name}</span>
            <br />
            {clip.duration} · {clip.size} · {clip.source}
          </p>
          <button type="button" className="btn wide" onClick={handleDownloadClip}>영상 내려받기</button>
        </div>
        <div className="hc">
          <span className="hc-n">2</span>
          <span className="hc-t">안전신문고 열기</span>
          <p className="hc-s">새 창에서 열립니다. 이 화면은 그대로 두고 옆에 놓고 보세요.</p>
          <button type="button" className="btn wide" onClick={handleOpenSafetyReport}>안전신문고 열기</button>
        </div>
        <div className="hc go">
          <span className="hc-n">3</span>
          <span className="hc-t">아래 내용 옮겨 담기</span>
          <p className="hc-s">왼쪽은 복사해서 붙여넣고, 오른쪽은 안전신문고 화면에서 직접 고르시면 됩니다.</p>
        </div>
      </div>

      <div className="grid2 wide" style={{ alignItems: 'stretch' }}>
        {/* 왼쪽(파랑) — 붙여넣을 것 3개, 각각 복사 버튼 */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="xhd paste">
            <span className="xhd-ic">
              <Check size={19} color="#2563eb" strokeWidth={2.2} />
            </span>
            <span>
              <span className="xhd-t">복사해서 붙여넣을 것</span>
              <span className="xhd-s">입력칸에 그대로 붙여넣으면 됩니다 · 3개</span>
            </span>
          </div>
          <div className="xlist">
            <div className="xrow">
              <span>
                <span className="x-k">제목</span>
                <span className="x-v" style={{ fontSize: 'calc(17px * var(--font-scale))' }}>{titleText}</span>
              </span>
              <button type="button" className="btn sm" onClick={() => handleCopy(titleText)}>복사</button>
            </div>
            <div className="xrow">
              <span>
                <span className="x-k">차량번호</span>
                <span className="x-v mono">{plateText || '읽을 수 없음'}</span>
              </span>
              {/* Task 17 fix: plateText is '' when plate.status is 'unknown' (§9 flow 3 —
                  "읽을 수 없음으로 두기"), reachable via one of the 4 official completion
                  flows. Copying '' and still showing the "복사했습니다" success toast would
                  lie to the user; §6-1 says the button copies value as-is, but with no value
                  there is nothing to copy, so disable rather than fake success. */}
              <button type="button" className="btn sm" disabled={!plateText} onClick={() => handleCopy(plateText)}>복사</button>
            </div>
            <div className="xrow">
              <span>
                <span className="x-k">신고 내용</span>
                <span className="x-v body">{reportContent}</span>
              </span>
              <button type="button" className="btn sm" onClick={() => handleCopy(reportContent)}>복사</button>
            </div>
          </div>
          <div className="xnote" style={{ marginTop: 'auto' }}>
            세 가지를 한 번에 복사하려면 <b>전체 복사</b>를 누르세요. 붙여넣을 칸 이름과 함께 복사됩니다.
            <div style={{ marginTop: 10 }}>
              <button type="button" className="btn sm blue" onClick={handleCopyAll}>세 가지 전체 복사</button>
            </div>
          </div>
        </div>

        {/* 오른쪽(주황) — 직접 고를 것 4개. 복사 버튼 없음(발생장소의 검색어 복사만 예외). */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="xhd pick">
            <span className="xhd-ic">
              <Check size={19} color="#b45309" strokeWidth={2.2} />
            </span>
            <span>
              <span className="xhd-t">안전신문고에서 직접 고를 것</span>
              <span className="xhd-s">붙여넣기가 안 되는 항목입니다 · 4개</span>
            </span>
          </div>
          <div className="xlist">
            <div className="xrow">
              <span>
                <span className="x-k">신고유형</span>
                <span className="x-v" style={{ fontSize: 'calc(17px * var(--font-scale))' }}>{reportType.value ?? '알 수 없음'}</span>
                <span className="x-h">유형 목록에서 안내된 대분류를 고른 뒤, 그 안에서 세부 항목을 눌러 선택하세요.</span>
              </span>
              <StatusBadge status={reportType.status} sm />
            </div>
            <div className="xrow">
              <span>
                <span className="x-k">발생일자</span>
                <span className="x-v mono">{dateValue}</span>
                <span className="x-h">{dateGuidance}</span>
              </span>
              <StatusBadge status={occurredAt.status} sm />
            </div>
            <div className="xrow">
              <span>
                <span className="x-k">발생시각</span>
                <span className="x-v mono">{timeValue}</span>
                <span className="x-h">{timeGuidance}</span>
              </span>
              <StatusBadge status={occurredAt.status} sm />
            </div>
            <div className="xrow">
              <span>
                <span className="x-k">발생장소</span>
                <span className="x-v" style={{ fontSize: 'calc(17px * var(--font-scale))' }}>{location.value ?? '알 수 없음'}</span>
                <span className="x-h">
                  {searchTerm
                    ? `지도 검색창에 「${searchTerm}」을 붙여넣고 정확한 위치를 눌러 핀을 놓으세요.`
                    : '지도에서 발생 위치를 직접 검색해 핀을 놓으세요.'}
                </span>
                {searchTerm && (
                  <span className="kv-act">
                    <button type="button" className="btn sm" onClick={() => handleCopy(searchTerm)}>
                      검색어 「{searchTerm}」 복사
                    </button>
                  </span>
                )}
              </span>
              <StatusBadge status={location.status} sm />
            </div>
          </div>
          <div className="xnote" style={{ marginTop: 'auto' }}>
            이 네 가지는 <b>복사·붙여넣기가 되지 않습니다.</b> 안전신문고 화면에서 위 값과 같은 것을 눌러 고르셔야 합니다.
            발생장소만 검색어를 붙여넣은 뒤 지도에서 핀을 놓는 방식입니다.
          </div>
        </div>
      </div>

      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexWrap: 'wrap', gap: 14, marginTop: 18,
        }}
      >
        <div className="disc" style={{ flex: '1 1 420px' }}>
          <b>대신고는 정부·공공기관 서비스가 아닙니다.</b>
          신고 접수는 안전신문고에서 직접 하셔야 하며, 위반 여부는 관계기관이 판단합니다.
          대신고가 준비한 자료는 참고 자료입니다.
        </div>
        <button type="button" className="btn ghost" onClick={handleNewCase}>다른 사건 찾기</button>
      </div>

      <Toast message={TOAST_MESSAGE} visible={toastVisible} />
    </div>
  );
}
