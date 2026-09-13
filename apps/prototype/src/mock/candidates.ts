import type { Candidate } from '../types';

/**
 * 값의 출처.
 *
 * - time / file(FILE_023만) / matches 문구 / scene 배정 / axisPct(72.8·75.6·77.2) :
 *   DESIGN-stage1-mockups.html 1372–1695행 (화면 4 "찾는 중"의 apin 마커, 화면 5 "이 사건이 맞나요?"의
 *   후보 카드 3개)을 그대로 옮겼다. §5.6이 말하는 "카드 번호 1·2·3은 업로드 순서가 아니라 특정 시각에
 *   대응한다"는 규칙대로, 배열 순서 = 마커 번호 순서다: 1번(18:31:48, 가장 오른쪽/가장 늦은 시각) →
 *   2번(18:25:40) → 3번(18:19:03, 가장 왼쪽/가장 이른 시각).
 * - interval : PROTOTYPE-SPEC.md §3 Candidate 타입 주석이 candidate 1(FILE_023)의 실제 값으로
 *   `18:31:42 – 18:31:57`을 제시해 그대로 썼다. candidate 2·3의 interval은 스펙·목업 어디에도 없어
 *   같은 폭(-6s/+9s, time 기준)을 기계적으로 적용해 만든 값이다 — 지어낸 값임을 밝혀둔다.
 * - candidate 2·3의 file (FILE_022 / FILE_020) : 목업이 실제로 명시하지 않는다. FILE_023이
 *   18:30:14 시작·3분 재생이라는 사실(업로드 목록, 1077행)만 있고 다른 파일의 시작 시각은 없으므로,
 *   시간 순서상 FILE_023보다 앞선 인접 번호를 추정해 채웠다 — 지어낸 값임을 밝혀둔다.
 */
export const defaultCandidates: Candidate[] = [
  {
    id: 'c1',
    time: '18:31:48',
    file: 'FILE_023.MP4',
    interval: '18:31:42 – 18:31:57',
    axisPct: 77.2,
    matches: [
      { ok: true, text: '흰색 SUV' },
      { ok: true, text: '백색 실선 확인' },
      { ok: true, text: '선을 넘어 이동' },
    ],
    scene: 'solid-cross',
  },
  {
    id: 'c2',
    time: '18:25:40',
    file: 'FILE_022.MP4',
    interval: '18:25:34 – 18:25:49',
    axisPct: 75.6,
    matches: [
      { ok: true, text: '흰색 SUV' },
      { ok: false, text: '실선인지 점선인지 불분명' },
    ],
    scene: 'ambiguous-line',
  },
  {
    id: 'c3',
    time: '18:19:03',
    file: 'FILE_020.MP4',
    interval: '18:18:57 – 18:19:12',
    axisPct: 72.8,
    matches: [
      { ok: true, text: '백색 실선 확인' },
      { ok: false, text: '차량 색이 더 어둡습니다' },
    ],
    scene: 'dark-car',
  },
];

/**
 * 「비슷하지만 다른 장면」— §7: `18:38:22 검은 승용차` / `18:21:05 점선 구간`.
 * 실제 문구는 목업 1779·1786행("검은 승용차 · 실선 침범", "흰색 SUV · 점선 구간에서 차로 변경")을 그대로 썼다.
 * axisPct는 목업에 없어 scope 구간(18:15→70.9% ~ 18:45→85.1%, 분당 0.4733%p)의 선형 비율로 계산했다 —
 * 지어낸 값임을 밝혀둔다. file은 두 후보 사이 시간 순서에 맞춘 추정치다.
 */
export const similarCandidates: Candidate[] = [
  {
    id: 's1',
    time: '18:38:22',
    file: 'FILE_026.MP4',
    interval: '18:38:16 – 18:38:31',
    axisPct: 82.0,
    matches: [
      { ok: false, text: '흰색 SUV 아님 — 검은 승용차' },
      { ok: true, text: '백색 실선 침범 확인' },
    ],
    scene: 'dark-car',
  },
  {
    id: 's2',
    time: '18:21:05',
    file: 'FILE_021.MP4',
    interval: '18:20:59 – 18:21:14',
    axisPct: 73.8,
    matches: [
      { ok: true, text: '흰색 SUV' },
      { ok: false, text: '점선 구간 — 실선 아님' },
    ],
    scene: 'ambiguous-line',
  },
];

/**
 * §5.6 SHIFT — "차량·상황 유지, 시간만 변경". defaultCandidates와 matches/scene은 완전히 동일하고
 * time/interval/axisPct만 ±2분 이동한다 (§5.6 예시: `18:31:48` → `18:29:48`, "이전 2분").
 * axisPct는 defaultCandidates의 분당 비율(scope 30분=14.2%p → 0.4733%p/분)로 2분치(≈0.9%p)를 가감했다.
 *
 * file: candidate 1은 FILE_023이 18:30:14 시작·3분 재생(업로드 목록 1077행)이라는 근거가 있어,
 * 2분 이동한 시각이 그 재생 구간 밖으로 나가는 것이 확인되므로 인접 파일(FILE_022/FILE_024)로 바꿨다.
 * candidate 2·3은 그런 근거가 없어 파일명을 바꾸지 않았다(불필요한 추정을 늘리지 않기 위함).
 */
export const candidatesShiftedBefore: Candidate[] = [
  {
    ...defaultCandidates[0],
    id: 'c1b',
    time: '18:29:48',
    file: 'FILE_022.MP4',
    interval: '18:29:42 – 18:29:57',
    axisPct: 76.3,
  },
  {
    ...defaultCandidates[1],
    id: 'c2b',
    time: '18:23:40',
    interval: '18:23:34 – 18:23:49',
    axisPct: 74.7,
  },
  {
    ...defaultCandidates[2],
    id: 'c3b',
    time: '18:17:03',
    interval: '18:16:57 – 18:17:12',
    axisPct: 71.9,
  },
];

export const candidatesShiftedAfter: Candidate[] = [
  {
    ...defaultCandidates[0],
    id: 'c1a',
    time: '18:33:48',
    file: 'FILE_024.MP4',
    interval: '18:33:42 – 18:33:57',
    axisPct: 78.1,
  },
  {
    ...defaultCandidates[1],
    id: 'c2a',
    time: '18:27:40',
    interval: '18:27:34 – 18:27:49',
    axisPct: 76.5,
  },
  {
    ...defaultCandidates[2],
    id: 'c3a',
    time: '18:21:03',
    interval: '18:20:57 – 18:21:12',
    axisPct: 73.7,
  },
];
