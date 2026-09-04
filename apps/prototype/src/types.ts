// ---------- 상태 어휘 (Core Flow §3) ----------
export type InfoStatus =
  | 'source-verified'   // 출처 확인됨   green
  | 'user-confirmed'    // 사용자 확인됨 green solid
  | 'ai-estimated'      // AI 추정       blue
  | 'needs-review'      // 확인 필요     orange
  | 'unknown';          // 알 수 없음    slate

export type WorkStatus =
  | 'done' | 'running' | 'waiting' | 'partial' | 'stopped' | 'failed';

/** 정보 상태와 작업 상태는 같은 컴포넌트를 공유하지 않는다. */
export interface Field<T = string> {
  value: T | null;
  source: string;        // 사람이 읽는 출처 문장. 빈 문자열 금지
  status: InfoStatus;
}

// ---------- 화면 ----------
export type Step =
  | 'upload' | 'describe' | 'scope' | 'searching'
  | 'candidates' | 'no-result' | 'failed'
  | 'prepare' | 'review' | 'handoff';

// ---------- 사건 ----------
export interface Hints {          // 사용자가 말한 것을 AI가 구조화한 결과
  time: string;  vehicle: string;  event: string;  location: string;
  raw: string;                     // 원문. 「"흰 SUV"에서」 같은 근거 표시에 쓴다
}

export interface Candidate {
  id: string;
  time: string;                    // 18:31:48
  file: string;                    // FILE_023.MP4
  interval: string;                // 18:31:42 – 18:31:57
  axisPct: number;                 // 시간 막대 위 위치 0~100
  matches: { ok: boolean; text: string; note?: string }[];
  scene: 'solid-cross' | 'ambiguous-line' | 'dark-car';  // EvidenceFrame 변형
}

export interface CaseState {
  hints: Hints;
  scope: { from: string; to: string; files: number; totalFiles: number;
           fromPct: number; toPct: number };
  scannedPct: number;              // scope 내 진행. 0~100
  candidates: Candidate[];
  similar: Candidate[];            // 「비슷하지만 다른 장면」
  selectedId: string | null;
  plate: Field;
  occurredAt: Field;
  situation: Field;
  location: Field;
  reportType: Field;               // 신고유형 — AI 추정
  title: Field;                    // 신고 제목 — AI 추정
  reportBody: Field;                // 신고문 본문 — AI 추정 (fix wave finding #3: title과 분리)
  clip: { name: string; size: string; duration: string; source: string };
  correction: null | { kept: string[]; changed: string[] };  // §5.2
  scenarioResolved: boolean;   // ruling 1 — has this case already had its "surprise" outcome?
  searchMode: 'full' | 'shift'; // ruling 2 — which timer duration SearchingScreen should run
  // fix wave finding #2 — SHOW_SIMILAR가 case.candidates에 채운 값이 「비슷하지만 다른 장면」
  // (similar)인지, 진짜 후보인지 구분한다. CandidatesScreen이 이 플래그로 "동급이 아님" 안내를 낸다.
  viewingSimilar: boolean;
}

// ---------- 시나리오 / 앱 상태 / 액션 ----------
export interface ScenarioConfig {
  resultScenario: 'candidates' | 'no-result' | 'failed';
  plateVariant: 'partial' | 'unreadable' | 'clear';
  speed: 'normal' | 'instant';
}

export interface AppState {
  step: Step;
  case: CaseState;
  scenario: ScenarioConfig;
}

export type Action =
  | { type: 'NEXT' }
  | { type: 'SUBMIT_MEMORY'; raw: string }
  | { type: 'EDIT_HINT'; key: keyof Hints; value: string }
  | { type: 'EDIT_SCOPE'; from?: string; to?: string }
  | { type: 'START_SEARCH' }
  | { type: 'TICK'; scannedPct: number }
  | { type: 'REVEAL_CANDIDATE'; id: string }
  | { type: 'SEARCH_DONE' }
  | { type: 'STOP' }
  | { type: 'EDIT_CONDITION' }
  | { type: 'SELECT'; id: string }
  | { type: 'ACCEPT' }
  | { type: 'SHIFT'; direction: 'before' | 'after' }
  | { type: 'REJECT_ALL' }
  | { type: 'RESUME_SEARCH' }
  | { type: 'WIDEN' }
  | { type: 'REDESCRIBE' }
  | { type: 'EDIT_VEHICLE' }
  | { type: 'SHOW_SIMILAR' }
  | { type: 'RETRY' }
  | { type: 'SHOW_PARTIAL' }
  | {
      type: 'SET_FIELD';
      key: 'plate' | 'occurredAt' | 'situation' | 'location' | 'reportType' | 'title' | 'reportBody';
      field: Field;
    }
  | { type: 'BACK' }
  | { type: 'BUILD' }
  | { type: 'NEW_CASE' }
  | { type: 'SET_SCENARIO'; scenario: Partial<ScenarioConfig> }
  | { type: 'RESET' };
