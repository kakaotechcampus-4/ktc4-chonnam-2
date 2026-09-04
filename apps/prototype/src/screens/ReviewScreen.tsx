import { useEffect, useState } from 'react';
import type { ChangeEvent, JSX } from 'react';
import { Check, ArrowRight } from 'lucide-react';
import type { Action, AppState, CaseState } from '../types';
import { Panel } from '../components/Panel';
import { SecLabel } from '../components/SecLabel';
import { Button } from '../components/Button';
import { KVRow } from '../components/KVRow';
import { reportBodyFor } from '../utils/reportBody';

/**
 * DESIGN-stage1-mockups.html 1966–2176 (화면 8 · 신고자료 최종 확인) + PROTOTYPE-SPEC.md §5.10.
 *
 * "전체를 다시 읽는 화면은 흐름 전체에서 여기 한 번뿐이다" — unlike PrepareScreen's per-field
 * KVRow (tinted, action buttons, drawers), every row here is plain (`tint` omitted, no `action`)
 * on purpose: this is the one read-everything-again moment, not a second correction UI.
 *
 * Final review fix wave finding #3: the editable "신고문" used to have no dedicated body field
 * in `CaseState` and was mapped onto `title` — which meant an edit here also overwrote the KV
 * row's 제목 value, so HandoffScreen then handed the user the exact same string for both 제목
 * and 신고 내용. `CaseState.reportBody` (utils/reportBody.ts) is now the real, separate field an
 * edit here writes to; `title` is untouched by this screen.
 *
 * `reportBodyFor`/`buildReportParagraph` live in utils/reportBody.ts (not here) so
 * mock/caseData.ts can also call them to seed `reportBody`'s initial value — same composition
 * everywhere, so an edit here and the handoff copy text never drift apart.
 */

function plateValueText(c: CaseState): string {
  return c.plate.status === 'unknown' ? '읽을 수 없음' : (c.plate.value ?? '');
}

const PREPARED_ITEMS: { label: string; note?: string }[] = [
  { label: '사건 영상' },
  { label: '차량번호' },
  { label: '발생시각' },
  { label: '신고 상황' },
  { label: '파일 크기', note: '84MB · 한도 130MB 이내' },
  { label: '신고기한', note: '기한 안에 있습니다' },
];

const TODO_ITEMS: { label: string; note?: string }[] = [
  { label: '붙여넣기 3개', note: '제목 · 신고 내용 · 차량번호' },
  { label: '직접 고르기 4개', note: '신고유형 · 발생일자 · 발생시각 · 발생장소' },
  { label: '영상 첨부하기' },
  { label: '신고 접수 누르기', note: '대신고는 대신 접수하지 않습니다' },
];

export function ReviewScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { state, dispatch } = props;
  const { occurredAt, location, plate, situation, reportType, title, clip } = state.case;

  const reportBody = reportBodyFor(state.case);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(reportBody);
  const [building, setBuilding] = useState(false);

  // §5.10 "이때만 clip 생성 연출 1.5초" — a local setTimeout, not a global loading state.
  // Guarded by `building` + cleaned up on unmount so an early BACK never leaves a stray dispatch.
  useEffect(() => {
    if (!building) return;
    const timer = setTimeout(() => dispatch({ type: 'BUILD' }), 1500);
    return () => clearTimeout(timer);
  }, [building, dispatch]);

  function startEdit() {
    setDraft(reportBody);
    setEditing(true);
  }
  function cancelEdit() {
    setEditing(false);
  }
  function handleDraftChange(e: ChangeEvent<HTMLTextAreaElement>) {
    setDraft(e.target.value);
  }
  function saveEdit() {
    if (!draft.trim()) return;
    dispatch({
      type: 'SET_FIELD',
      key: 'reportBody',
      field: { value: draft, source: '사용자 수정', status: 'user-confirmed' },
    });
    setEditing(false);
  }
  function handleBack() {
    if (building) return;
    dispatch({ type: 'BACK' });
  }
  function handleBuild() {
    if (building) return;
    setBuilding(true);
  }

  return (
    <div className="pbody">
      <div className="ptop">
        <div>
          <h2 className="ptitle">제출하기 전에 한 번만 읽어주세요</h2>
          <p className="psub">아래 내용이 실제 상황과 맞는지 확인해주세요. 「정보 수정」을 눌러 언제든 되돌아갈 수 있습니다.</p>
        </div>
      </div>

      <div className="sum" style={{ marginBottom: 18 }}>
        <div className="sumc">
          <span className="sum-ic" style={{ background: 'var(--green-soft)' }}>
            <Check size={22} color="var(--green)" />
          </span>
          <span>
            <span className="sum-k">발생시각</span>
            <span className="sum-v mono">{occurredAt.value ?? '알 수 없음'}</span>
          </span>
        </div>
        <div className="sumc">
          <span className="sum-ic" style={{ background: 'var(--green-soft)' }}>
            <Check size={22} color="var(--green)" />
          </span>
          <span>
            <span className="sum-k">차량번호</span>
            <span className="sum-v mono">{plateValueText(state.case)}</span>
          </span>
        </div>
        <div className="sumc">
          <span className="sum-ic" style={{ background: 'var(--blue-soft)' }}>
            <ArrowRight size={22} color="var(--blue)" />
          </span>
          <span>
            <span className="sum-k">신고유형 추천</span>
            <span className="sum-v" style={{ fontSize: 'calc(20px * var(--font-scale))' }}>{reportType.value ?? '알 수 없음'}</span>
          </span>
        </div>
      </div>

      <div className="grid2 wide">
        <div className="stack">
          <Panel>
            <SecLabel>
              <span>신고자료 내용</span>
            </SecLabel>
            <div className="kv">
              <KVRow label="제목" value={title.value ?? ''} source={title.source} status={title.status} />
              <KVRow label="신고유형" value={reportType.value ?? ''} source={reportType.source} status={reportType.status} />
              <KVRow label="발생시각" value={occurredAt.value ?? ''} source={occurredAt.source} status={occurredAt.status} />
              <KVRow label="차량번호" value={plateValueText(state.case)} source={plate.source} status={plate.status} />
              <KVRow label="신고 상황" value={situation.value ?? ''} source={situation.source} status={situation.status} />
              <KVRow label="위치" value={location.value ?? ''} source={location.source} status={location.status} />
              <KVRow
                label="신고용 영상"
                value={clip.name}
                source={`${clip.duration} · ${clip.source}`}
                status="source-verified"
              />
            </div>
          </Panel>

          <Panel>
            <SecLabel>
              <span>안전신문고에 붙여넣을 신고문</span>
              {!editing && (
                <button type="button" className="btn sm" onClick={startEdit}>수정</button>
              )}
            </SecLabel>
            {editing ? (
              <div className="stack" style={{ gap: 10 }}>
                <textarea
                  autoFocus
                  className="field"
                  value={draft}
                  onChange={handleDraftChange}
                  rows={5}
                  style={{ height: 'auto', minHeight: 140, alignItems: 'flex-start', lineHeight: 1.7, resize: 'vertical' }}
                />
                <div className="btngrid c2">
                  <Button variant="primary" onClick={saveEdit} disabled={!draft.trim()}>저장</Button>
                  <Button onClick={cancelEdit}>취소</Button>
                </div>
              </div>
            ) : (
              <div className="stmt">
                <p>{reportBody}</p>
              </div>
            )}
          </Panel>
        </div>

        <div className="stack">
          <Panel>
            <SecLabel>
              <span>대신고가 준비한 것</span>
            </SecLabel>
            <ul className="chk">
              {PREPARED_ITEMS.map((item) => (
                <li key={item.label}>
                  <span className="ci ok">
                    <Check size={12} color="#fff" strokeWidth={4} />
                  </span>
                  <span className="chk-t">
                    {item.label}
                    {item.note && <span className="chk-s">{item.note}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel>
            <SecLabel>
              <span>안전신문고에서 하실 일</span>
              <span className="n">복사 3 · 선택 4</span>
            </SecLabel>
            <p style={{ fontSize: 'calc(16px * var(--font-scale))', color: 'var(--muted)', fontWeight: 600, lineHeight: 1.6, margin: '0 0 12px' }}>
              제목·신고 내용·차량번호만 붙여넣을 수 있고, 나머지는 화면에서 골라야 합니다.
            </p>
            <ul className="chk">
              {TODO_ITEMS.map((item) => (
                <li key={item.label}>
                  <span className="ci ex">
                    <ArrowRight size={12} color="var(--blue)" strokeWidth={3.4} />
                  </span>
                  <span className="chk-t">
                    {item.label}
                    {item.note && <span className="chk-s">{item.note}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </Panel>

          <Button variant="primary" size="large" disabled={building} onClick={handleBuild}>
            {building ? '만드는 중…' : '신고자료 만들기'}
          </Button>
          <div className="btngrid c2">
            <Button disabled={building} onClick={handleBack}>정보 수정</Button>
          </div>
          <div className="disc">
            <b>대신고는 정부·공공기관 서비스가 아닙니다.</b>
            신고 접수는 안전신문고에서 직접 하셔야 하며, 위반 여부는 관계기관이 판단합니다.
          </div>
        </div>
      </div>
    </div>
  );
}
