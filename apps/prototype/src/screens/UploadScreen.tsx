import { useEffect, useRef, useState } from 'react';
import type { DragEvent, JSX } from 'react';
import { Upload } from 'lucide-react';
import type { Action, AppState, WorkStatus } from '../types';
import { Panel } from '../components/Panel';
import { SecLabel } from '../components/SecLabel';
import { KVRow } from '../components/KVRow';
import { WorkList } from '../components/WorkList';
import { Button } from '../components/Button';
import {
  uploadFiles,
  TOTAL_FILES,
  DRIVE_START,
  DRIVE_END,
  DRIVE_DURATION,
  NO_GPS,
} from '../mock/files';

/**
 * DESIGN-stage1-mockups.html 1001–1157 (화면 1 · 신규 — 블랙박스 영상 올리기).
 * Establishes the { state, dispatch } prop contract every later screen follows.
 *
 * §5.2 — drag/drop and the file <input> are real DOM mechanics, but neither
 * path ever reads the dropped/selected file's content: both just reveal the
 * same mock 5-row summary already seeded from mock/files.ts. The "올리는 중"
 * row's flip to `done` 3s after mount is local, presentational state (a
 * timer that lives in the screen, per Toast.tsx's convention) — later
 * screens never need to know a file finished uploading.
 */
export function UploadScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { dispatch } = props;
  void props.state; // upload has no case-state to read yet — kept for the shared prop contract

  const [items, setItems] = useState(uploadFiles);
  const [uploading, setUploading] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Task 17 fix: dragenter/dragleave fire per-element, not per-region — moving the pointer from
  // the dropzone onto one of its own children (icon/text/button) fires dragenter(child) then
  // dragleave(dropzone) (the browser fires the enter for the newly-entered element before the
  // leave for the vacated one), even though the pointer never left the dropzone visually. The
  // old code set `dragOver` unconditionally on every dragleave targeting the dropzone, so that
  // dragleave(dropzone) still flipped it off regardless of the just-fired dragenter(child) —
  // confirmed live via claude-in-chrome by dispatching that exact enter-then-leave sequence
  // against a child of the dropzone and observing `.drop.on` drop to `.drop` for one frame. A
  // depth counter fixes it: every enter/leave on a nested child nets to a stable non-zero depth
  // while the pointer stays somewhere inside the dropzone, so only the true final dragleave
  // (depth back to 0) turns dragOver off — verified live with the same reproduction (enter
  // child → leave dropzone → enter dropzone → leave child → leave dropzone), which now stays
  // `.drop.on` until the last, real exit.
  const dragDepthRef = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setItems((prev) =>
        prev.map((item) =>
          item.status === 'running'
            ? ({ ...item, status: 'done' as WorkStatus, note: '19:09:12 시작' })
            : item,
        ),
      );
      setUploading(false);
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  const completed = uploading ? TOTAL_FILES - 1 : TOTAL_FILES;

  function handleDragEnter(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    dragDepthRef.current += 1;
    setDragOver(true);
  }
  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(true);
  }
  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setDragOver(false);
  }
  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    dragDepthRef.current = 0;
    setDragOver(false);
    // Dropped file content is never read — the mock list below already stands in for it.
  }
  function handleChoosePick() {
    fileInputRef.current?.click();
  }
  function handleFileInputChange() {
    // Selected file content is never read either — same mock list stands.
  }

  return (
    <div className="pbody">
      <div className="ptop">
        <div>
          <h2 className="ptitle">블랙박스 영상을 올려주세요</h2>
          <p className="psub">여러 파일을 한 번에 올리셔도 됩니다. 촬영 시각은 파일에서 자동으로 읽습니다.</p>
        </div>
      </div>

      <div className="grid2 wide">
        <div className="stack">
          <div
            className={`drop${dragOver ? ' on' : ''}`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <span className="drop-ic">
              <Upload size={30} color="var(--green)" strokeWidth={2.2} />
            </span>
            <p className="drop-t">여기에 영상 파일을 끌어다 놓으세요</p>
            <p className="drop-s">폴더째로 끌어다 놓으셔도 됩니다</p>
            <Button variant="primary" onClick={handleChoosePick}>파일 선택</Button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="video/*"
              style={{ display: 'none' }}
              onChange={handleFileInputChange}
            />
            <p className="drop-f">MP4 · AVI · MOV · MKV · 파일 하나당 최대 4GB</p>
          </div>

          <Panel>
            <SecLabel>
              <span>올린 영상</span>
              <span className="n">{TOTAL_FILES}개 중 {completed}개 완료</span>
            </SecLabel>
            <WorkList items={items} />
            <div className="ftot">
              <span className="ftot-k">
                {uploading ? '마지막 파일을 올리고 있습니다' : '모든 파일을 올렸습니다'}
              </span>
              <span className="ftot-v">
                <span className="mono">{completed}</span> / <span className="mono">{TOTAL_FILES}</span>개 ·{' '}
                <span className="mono">{DRIVE_DURATION}</span>
              </span>
            </div>
          </Panel>
        </div>

        <div className="stack">
          <Panel>
            <SecLabel>영상에서 읽은 정보</SecLabel>
            <div className="kv">
              <KVRow
                label="촬영 시간"
                value={`${DRIVE_START} – ${DRIVE_END}`}
                source={`2026년 8월 24일 · ${DRIVE_DURATION}`}
                status="source-verified"
              />
              <KVRow
                label="화면 시각"
                value="영상에 시각이 찍혀 있습니다"
                source="발생시각을 정확하게 알 수 있습니다"
                status="source-verified"
              />
              <KVRow
                label="GPS 기록"
                value={NO_GPS ? '없습니다' : '있습니다'}
                source="위치는 마지막에 안전신문고 지도에서 직접 고르셔야 합니다"
                status="unknown"
              />
            </div>
          </Panel>
        </div>
      </div>

      <div className="btnrow" style={{ marginTop: 18 }}>
        <Button variant="primary" size="large" onClick={() => dispatch({ type: 'NEXT' })}>
          다음 · 사건 설명하기
        </Button>
      </div>
    </div>
  );
}
