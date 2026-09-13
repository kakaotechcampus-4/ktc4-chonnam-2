import type { CaseState } from '../types';
import { similarCandidates } from './candidates';
import { buildReportParagraph } from '../utils/reportBody';

/**
 * 초기 CaseState 팩토리. `NEW_CASE`가 매번 새 객체를 필요로 하므로 공유 mutable 객체가 아니라
 * 함수로 만든다. 값은 `docs/design/PROTOTYPE-SPEC.md` §7 "Mock 데이터"를 그대로 옮겼다.
 */
export const createInitialCase = (): CaseState => {
  const plate: CaseState['plate'] = {
    value: '12가 34?6',
    source: '번호판 프레임 4개 중 3개에서 판독',
    status: 'needs-review',
  };
  const occurredAt: CaseState['occurredAt'] = {
    value: '2026-08-24 18:31:48',
    source: 'FILE_023 타임스탬프',
    status: 'source-verified',
  };
  const situation: CaseState['situation'] = {
    value: '실선 구간에서 진로 변경',
    source: '영상 프레임 분석',
    status: 'ai-estimated',
  };
  const location: CaseState['location'] = {
    value: '미금역 인근',
    source: '"미금역 근처였던 것 같아요"에서',
    status: 'ai-estimated',
  };
  const clip: CaseState['clip'] = {
    name: 'daesingo_event_001.mp4',
    size: '84MB',
    duration: '15초',
    source: 'FILE_023에서 자동 추출',
  };

  return {
    hints: { time: '', vehicle: '', event: '', location: '', raw: '' },
    scope: { from: '18:15', to: '18:45', files: 9, totalFiles: 42, fromPct: 70.9, toPct: 85.1 },
    scannedPct: 0,
    candidates: [],
    similar: similarCandidates,
    selectedId: null,
    plate,
    occurredAt,
    situation,
    location,
    reportType: {
      value: '교통위반 › 진로변경 위반',
      source: 'AI 추정',
      status: 'ai-estimated',
    },
    title: {
      value: '백색 실선 침범 신고 (흰색 SUV 12가 3456)',
      source: 'AI 추정',
      status: 'ai-estimated',
    },
    // fix wave finding #3 — 신고문 본문 초깃값은 ReviewScreen/HandoffScreen이 공유하는
    // buildReportParagraph()로 만든 것과 완전히 같은 문장이어야, 편집 전까지는 두 화면이
    // 보여주는 문단이 어긋나지 않는다.
    reportBody: {
      value: buildReportParagraph({ occurredAt, location, plate, situation, clip }),
      source: 'AI 추정',
      status: 'ai-estimated',
    },
    clip,
    correction: null,
    scenarioResolved: false,
    searchMode: 'full',
    viewingSimilar: false,
  };
};
