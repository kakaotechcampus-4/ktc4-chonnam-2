// data/mock/case/*.json 로더.
//
// 저장소 원본을 그대로 읽는다(vite.config.ts의 server.fs.allow). 스냅샷을 이
// 앱 안에 복사해 두지 않는 이유는 「web이 CaseView를 값 재계산 없이 그대로
// 소비한다」를 증빙할 대상이 사본이 되면 안 되기 때문이다.

import type { CaseView, InfoState, Stage } from './caseView'

interface ScenarioFile {
  scenario_id: string
  module: string
  case_views: (CaseView & { contract?: string; contract_version?: string })[]
}

export interface Snapshot {
  scenarioId: string
  view: CaseView
  /** 파일 안에서의 순번(1부터) — rev 표기에 쓴다 */
  index: number
}

const STAGES: Stage[] = ['INTAKE', 'SEARCHING', 'CANDIDATE_REVIEW', 'EVIDENCE_REVIEW', 'READY']
const INFO_STATES: InfoState[] = [
  'INFO_AI_ESTIMATED',
  'INFO_SOURCE_VERIFIED',
  'INFO_USER_CONFIRMED',
  'INFO_NEEDS_REVIEW',
  'INFO_UNKNOWN',
]

const modules = import.meta.glob('../../../../data/mock/case/*.json', { eager: true }) as Record<
  string,
  { default: ScenarioFile }
>

export interface LoadIssue {
  where: string
  problem: string
}

/**
 * 등재값 검사. 값을 고치거나 기본값을 채우지 않는다 — 계약에 없는 값이 오면
 * 그 사실을 그대로 보고한다(value-state-display.md §4 「없는 상태를
 * INFO_SOURCE_VERIFIED로 간주하지 않는다」).
 */
function inspect(view: CaseView, where: string): LoadIssue[] {
  const issues: LoadIssue[] = []
  if (!STAGES.includes(view.stage)) issues.push({ where, problem: `미등재 stage: ${view.stage}` })

  const evidence = view.evidence
  if (evidence) {
    for (const key of [
      'plate_display',
      'event_time_display',
      'location_display',
      'case_type_display',
      'violation_display',
      'report_type_display',
    ] as const) {
      const display = evidence[key]
      if (!display) {
        issues.push({ where, problem: `${key} 없음` })
        continue
      }
      if (!INFO_STATES.includes(display.info_state)) {
        issues.push({ where, problem: `${key}.info_state 미등재: ${display.info_state}` })
      }
    }
  }

  for (const state of view.package ? Object.entries(view.package.report_field_states) : []) {
    if (!INFO_STATES.includes(state[1].info_state)) {
      issues.push({ where, problem: `report_field_states.${state[0]} 미등재: ${state[1].info_state}` })
    }
  }
  return issues
}

function load(): { snapshots: Snapshot[]; issues: LoadIssue[] } {
  const snapshots: Snapshot[] = []
  const issues: LoadIssue[] = []

  for (const path of Object.keys(modules).sort()) {
    const file = modules[path].default
    file.case_views.forEach((view, i) => {
      const where = `${file.scenario_id} #${i + 1}`
      snapshots.push({ scenarioId: file.scenario_id, view, index: i + 1 })
      issues.push(...inspect(view, where))
    })
  }
  return { snapshots, issues }
}

const loaded = load()

export const SNAPSHOTS = loaded.snapshots
export const LOAD_ISSUES = loaded.issues
export const SCENARIO_IDS = [...new Set(SNAPSHOTS.map((s) => s.scenarioId))]
