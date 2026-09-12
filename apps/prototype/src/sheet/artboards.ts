import type { Action, AppState, ScenarioConfig, Step } from '../types';
import { createInitialState, reduce } from '../machine';

/**
 * Figma 반입용 아트보드 정의.
 *
 * 상태는 손으로 적지 않는다. `machine.ts`의 `reduce()`에 실제 액션을 흘려서 만든다 —
 * 프로토타입이 바뀌면 시트도 같이 바뀌고, 시트가 앱과 다른 화면을 그릴 수 없다.
 *
 * 이 파일은 프로토타입의 동작을 바꾸지 않는다. 읽기만 한다.
 */

export type Lane = 'main' | 'branch' | 'plate' | 'edge';

export interface Artboard {
  /** Figma 레이어 이름이 되는 값 */
  id: string;
  lane: Lane;
  /** 아트보드 제목 (사람이 읽는 이름) */
  title: string;
  /** 이 화면이 무엇인지 한 줄 */
  note: string;
  /** 9/14 회의에서 이 화면을 두고 물을 것 */
  questions: string[];
  /**
   * 화면 자체 타이머(UploadScreen 3초 등)를 몇 ms 지난 뒤 얼려서 담을지.
   * 생략하면 즉시 언다.
   */
  freezeMs?: number;
  state: AppState;
}

export const LANE_LABEL: Record<Lane, string> = {
  main: 'A · 메인 동선 — 성공 경로',
  branch: 'B · 결과 분기 — 못 찾았을 때',
  plate: 'C · 번호판 판독 변형',
  edge: 'D · 값이 비었을 때',
};

export const LANE_ORDER: Lane[] = ['main', 'branch', 'plate', 'edge'];

// ---------------------------------------------------------------- 상태 조립
function seq(scenario: Partial<ScenarioConfig>, actions: Action[]): AppState {
  let s = createInitialState();
  if (Object.keys(scenario).length > 0) s = reduce(s, { type: 'SET_SCENARIO', scenario });
  for (const a of actions) s = reduce(s, a);
  return s;
}

/** PROTOTYPE-SPEC.md §5.3의 예시 진술. machine.ts의 네 정규식에 전부 걸린다 */
const RAW = '어제 저녁 6시 반쯤 미금역 근처에서 흰 SUV가 실선에서 끼어들었어요';

const TO_DESCRIBE: Action[] = [{ type: 'NEXT' }];
const TO_SCOPE: Action[] = [...TO_DESCRIBE, { type: 'SUBMIT_MEMORY', raw: RAW }];
const TO_SEARCHING: Action[] = [...TO_SCOPE, { type: 'START_SEARCH' }];
const TO_CANDIDATES: Action[] = [
  ...TO_SEARCHING,
  { type: 'TICK', scannedPct: 100 },
  { type: 'SEARCH_DONE' },
];
const TO_PREPARE: Action[] = [...TO_CANDIDATES, { type: 'SELECT', id: 'c1' }, { type: 'ACCEPT' }];

const CONFIRM_PLATE: Action = {
  type: 'SET_FIELD',
  key: 'plate',
  field: { value: '12가 3456', source: '사용자 입력', status: 'user-confirmed' },
};
const CONFIRM_SITUATION: Action = {
  type: 'SET_FIELD',
  key: 'situation',
  field: { value: '실선 구간에서 진로 변경', source: '사용자 확인', status: 'user-confirmed' },
};

const TO_REVIEW: Action[] = [...TO_PREPARE, CONFIRM_PLATE, CONFIRM_SITUATION, { type: 'NEXT' }];
const TO_HANDOFF: Action[] = [...TO_REVIEW, { type: 'BUILD' }];

// ---------------------------------------------------------------- 아트보드
export const ARTBOARDS: Artboard[] = [
  // ============================== A · 메인 동선
  {
    id: '01-upload-uploading',
    lane: 'main',
    title: '업로드 — 옮기는 중',
    note: 'SD카드에서 파일을 끌어다 놓은 직후. 42개 중 1개가 아직 처리 중이다.',
    questions: [
      '멘토: "SD카드에서 영상 뽑고 넣은 다음"—여기까지는 동의. 이 화면에서 읽어야 하는 글자가 몇 줄인가?',
      '파일별 진행 목록이 지금 단계에서 정말 필요한가, 한 줄 요약으로 충분한가?',
    ],
    freezeMs: 1200,
    state: createInitialState(),
  },
  {
    id: '02-upload-done',
    lane: 'main',
    title: '업로드 — 끝난 상태',
    note: '같은 화면의 3초 뒤. 다음 단계 버튼이 열린다.',
    questions: [
      '업로드 완료를 굳이 사용자가 확인하고 눌러야 하는가? 자동으로 넘어가면 안 되는 이유는?',
    ],
    freezeMs: 3600,
    state: createInitialState(),
  },
  {
    id: '03-describe',
    lane: 'main',
    title: '진술 — 무슨 일이 있었는지',
    note: '멘토가 지목한 "초반 화면". 자유 문장 하나를 받는다.',
    questions: [
      '멘토: "몇시쯤 ...한 상황이 있었어 만 넣어준 다음"—멘토가 생각하는 입력은 이 화면 하나뿐이다.',
      '이 화면 이후 모든 단계를 사용자 확인 없이 진행하면 무엇이 깨지는가? (= 간편신고의 정의)',
      '예시 문장·안내문이 몇 줄인가. 입력창보다 설명이 길지 않은가?',
    ],
    state: seq({}, TO_DESCRIBE),
  },
  {
    id: '04-scope',
    lane: 'main',
    title: '이해 확인 — 이렇게 이해했어요',
    note: '진술에서 뽑은 4개 힌트(시각·차량·상황·장소)와 탐색 범위를 사용자가 고친다.',
    questions: [
      '동선에서 가장 의심스러운 단계다. 없애고 바로 검색하면? (틀렸을 때만 되돌리기)',
      '힌트 4개를 다 보여줘야 하는가, 틀리기 쉬운 것만 보여주면 되는가?',
      '범위(18:15–18:45) 조정이 사용자가 지금 할 수 있는 판단인가?',
    ],
    state: seq({}, TO_SCOPE),
  },
  {
    id: '05-searching',
    lane: 'main',
    title: '찾는 중 — 45%',
    note: '후보 1개를 찾은 시점. 작업 목록·시간축·경과 시간이 동시에 돈다.',
    questions: [
      '멘토: "자고 일어나면 알아서 신고가 되어 있으면 좋겠다"—사용자가 이 화면을 지켜봐야 하는가?',
      '지켜보지 않아도 되게 하려면 무엇이 필요한가? (알림·이어받기·백그라운드)',
      '작업 목록 4줄 + 시간축 + 경과시간 + 후보 카드. 동시에 봐야 할 정보가 몇 개인가?',
    ],
    state: seq({}, [
      ...TO_SEARCHING,
      { type: 'TICK', scannedPct: 45 },
      { type: 'REVEAL_CANDIDATE', id: 'c3' },
    ]),
  },
  {
    id: '06-candidates',
    lane: 'main',
    title: '후보 확인 — 이 사건이 맞나요',
    note: '후보 3개. 각 후보마다 일치 근거가 붙는다.',
    questions: [
      '후보가 1개뿐일 때도 이 화면을 거쳐야 하는가?',
      '일치 근거 문장이 후보마다 3~4줄. 사용자가 실제로 읽는가, 썸네일만 보는가?',
    ],
    state: seq({}, TO_CANDIDATES),
  },
  {
    id: '07-prepare-needs-review',
    lane: 'main',
    title: '번호판 확인 — 확인 필요',
    note: '다섯 번째 글자를 못 읽은 상태. 이 화면의 기본값이다.',
    questions: [
      '번호판이 안 읽힐 때만 이 화면이 뜨면 되는데 지금은 항상 뜬다. 맞나?',
      '프레임 4장 넘겨보기를 사용자에게 시키는 게 맞는가?',
    ],
    state: seq({}, TO_PREPARE),
  },
  {
    id: '08-review',
    lane: 'main',
    title: '제출 전 검토',
    note: '신고문·첨부·체크리스트를 마지막으로 읽는 화면.',
    questions: [
      '전체에서 글자량이 가장 많다. 멘토 지적 "글자가 너무 많다"의 1순위 대상.',
      '체크리스트(붙여넣기 3개 / 직접 고르기 4개)를 여기서 미리 보여주는 게 도움인가 부담인가?',
    ],
    state: seq({}, TO_REVIEW),
  },
  {
    id: '09-handoff',
    lane: 'main',
    title: '전달 — 신고자료 준비됨',
    note: '안전신문고로 넘기기 직전. 복사 버튼과 직접 골라야 하는 항목 안내.',
    questions: [
      '대신고는 대신 접수하지 않는다 — 이 제약이 사용자에게 언제 처음 전달되는가?',
      '멘토가 말한 "자고 일어나면 신고 완료"와 이 화면의 거리가 정확히 얼마인가?',
    ],
    state: seq({}, TO_HANDOFF),
  },

  // ============================== B · 결과 분기
  {
    id: '10-no-result',
    lane: 'branch',
    title: '결과 없음',
    note: '지정 범위에서 아무것도 못 찾았다. 다음 수를 여러 개 제시한다.',
    questions: [
      '선택지를 동시에 다 줘야 하는가? 하나를 기본으로 밀면 안 되는가?',
      '사용자가 여기서 이탈하면 업로드한 42개 파일은 어떻게 되는가?',
    ],
    state: seq({ resultScenario: 'no-result' }, [
      ...TO_SEARCHING,
      { type: 'TICK', scannedPct: 100 },
      { type: 'SEARCH_DONE' },
    ]),
  },
  {
    id: '11-searching-widened',
    lane: 'branch',
    title: '찾는 중 — 범위 확장 후',
    note: '결과 없음에서 범위를 넓혀 다시 도는 중. 영상 9개 → 21개.',
    questions: ['확장 결과가 화면에 반영됐는지 여기서 확인되는가? (파일 수·시간 범위)'],
    state: seq({ resultScenario: 'no-result' }, [
      ...TO_SEARCHING,
      { type: 'TICK', scannedPct: 100 },
      { type: 'SEARCH_DONE' },
      { type: 'WIDEN' },
      { type: 'TICK', scannedPct: 30 },
    ]),
  },
  {
    id: '12-candidates-similar',
    lane: 'branch',
    title: '후보 — 비슷하지만 다른 장면',
    note: '결과 없음에서 "비슷한 장면 보기"로 들어온 상태. 진짜 후보와 같은 위계로 두지 않는다.',
    questions: ['"같은 위계가 아님"이 시각적으로 전달되는가, 안내 문장에만 기대고 있는가?'],
    state: seq({ resultScenario: 'no-result' }, [
      ...TO_SEARCHING,
      { type: 'TICK', scannedPct: 100 },
      { type: 'SEARCH_DONE' },
      { type: 'SHOW_SIMILAR' },
    ]),
  },
  {
    id: '13-candidates-partial',
    lane: 'branch',
    title: '후보 — 중간에 멈춘 결과',
    note: '62%에서 사용자가 멈춤. 아직 안 본 구간이 남아 있다는 배너가 뜬다.',
    questions: ['"이어서 찾기"를 사용자가 기억해서 돌아올 것 같은가?'],
    state: seq({}, [
      ...TO_SEARCHING,
      { type: 'TICK', scannedPct: 62 },
      { type: 'REVEAL_CANDIDATE', id: 'c3' },
      { type: 'REVEAL_CANDIDATE', id: 'c2' },
      { type: 'STOP' },
    ]),
  },
  {
    id: '14-failed',
    lane: 'branch',
    title: '검색 실패',
    note: '분석이 중단됐다. 사용자 잘못이 아니라는 것을 먼저 말한다.',
    questions: [
      '실패가 사용자 탓이 아님이 첫 줄에서 읽히는가?',
      '다시 시도가 "이어서"인지 "처음부터"인지 구분되는가?',
    ],
    state: seq({ resultScenario: 'failed' }, [
      ...TO_SEARCHING,
      { type: 'TICK', scannedPct: 41 },
      { type: 'REVEAL_CANDIDATE', id: 'c3' },
      { type: 'SEARCH_DONE' },
    ]),
  },
  {
    id: '15-candidates-from-failed',
    lane: 'branch',
    title: '후보 — 실패 전까지 찾은 것',
    note: '실패 화면에서 "찾은 것만 보기"로 들어온 상태.',
    questions: ['실패했는데 결과를 보여주는 것이 신뢰를 주는가, 혼란을 주는가?'],
    state: seq({ resultScenario: 'failed' }, [
      ...TO_SEARCHING,
      { type: 'TICK', scannedPct: 41 },
      { type: 'REVEAL_CANDIDATE', id: 'c3' },
      { type: 'SEARCH_DONE' },
      { type: 'SHOW_PARTIAL' },
    ]),
  },

  // ============================== C · 번호판 변형
  {
    id: '16-prepare-unreadable',
    lane: 'plate',
    title: '번호판 — 네 장면 모두 판독 불가',
    note: '번호를 아예 못 읽는 경우. "알 수 없음"으로 남기고 진행할 수 있다.',
    questions: ['번호판 없이 접수 가능한 신고 유형이 무엇인지 이 화면이 알려주는가?'],
    state: seq({ plateVariant: 'unreadable' }, TO_PREPARE),
  },
  {
    id: '17-prepare-clear',
    lane: 'plate',
    title: '번호판 — 선명하게 읽힘',
    note: '판독에 문제가 없는 경우.',
    questions: ['이 경우에도 확인을 시켜야 하는가? 이 화면을 건너뛸 수 있는 조건은?'],
    state: seq({ plateVariant: 'clear' }, TO_PREPARE),
  },
  {
    id: '18-prepare-ready',
    lane: 'plate',
    title: '번호판 — 둘 다 확인 끝',
    note: '차량번호·신고 상황을 모두 확인해 다음으로 넘어갈 수 있는 상태.',
    questions: ['확인이 끝났다는 것이 버튼 활성화 말고 무엇으로 보이는가?'],
    state: seq({}, [...TO_PREPARE, CONFIRM_PLATE, CONFIRM_SITUATION]),
  },

  // ============================== D · 값이 비었을 때
  {
    id: '19-handoff-unknown-time',
    lane: 'edge',
    title: '전달 — 발생시각을 모를 때',
    note: '영상에 타임스탬프가 없어 날짜·시각을 사용자가 직접 골라야 하는 경우.',
    questions: [
      '"달력에서 직접 고르세요" 안내가 몇 줄인가. 이게 가장 자주 나는 실패 경로인가?',
      '시각을 모르면 신고 자체가 되는가? 안 되면 더 앞에서 막아야 하지 않나?',
    ],
    state: seq({}, [
      ...TO_REVIEW,
      {
        type: 'SET_FIELD',
        key: 'occurredAt',
        field: { value: null, source: '영상에 타임스탬프 없음', status: 'unknown' },
      },
      { type: 'BUILD' },
    ]),
  },
];

/** AppBar에 넘길 단계 — 조립된 상태에서 그대로 읽는다 */
export function stepOf(a: Artboard): Step {
  return a.state.step;
}
