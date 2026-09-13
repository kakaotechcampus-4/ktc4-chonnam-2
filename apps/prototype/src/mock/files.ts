import type { WorkStatus } from '../types';

/**
 * UploadScreen §5.2 / §6 <WorkList> — 5행만 보여준다 (완료 3 · 읽을 수 없음 1 · 올리는 중 1).
 * 라벨·부가문구는 DESIGN-stage1-mockups.html 1001–1157행의 실제 표기를 그대로 옮긴 것이다.
 */
export const uploadFiles: { label: string; status: WorkStatus; note?: string }[] = [
  { label: 'FILE_001.MP4', status: 'done', note: '15:40:02 시작' },
  { label: 'FILE_002.MP4', status: 'done', note: '15:43:02 시작' },
  { label: 'FILE_017.MP4', status: 'failed', note: '읽을 수 없어 건너뜁니다' },
  { label: 'FILE_023.MP4', status: 'done', note: '18:30:14 시작' },
  { label: 'FILE_042.MP4', status: 'running', note: '올리는 중 68%' },
];

// 주행 전체 — §7 "주행: 2026-08-24 15:40–19:12, 42개 파일, 3시간 32분, GPS 없음"
export const TOTAL_FILES = 42;
export const DRIVE_START = '15:40';
export const DRIVE_END = '19:12';
export const DRIVE_DURATION = '3시간 32분';
export const NO_GPS = true;
