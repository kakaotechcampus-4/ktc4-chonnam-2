// data/mock/case/*.json · data/real/case/*.json 로더.
//
// 저장소 원본을 그대로 읽는다(vite.config.ts의 server.fs.allow). 스냅샷을 이
// 앱 안에 복사해 두지 않는 이유는 「web이 CaseView를 값 재계산 없이 그대로
// 소비한다」를 증빙할 대상이 사본이 되면 안 되기 때문이다.

import type { CaseView } from './caseView'
import {
  INFO_STATES,
  JOB_STATUSES,
  PROGRESS_STATES,
  READINESSES,
  SEVERITIES,
  SITUATION_CONFIRMATIONS,
  STAGES,
} from './registry'

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

// mock pack과 실제 `case.get_view()` 산출물을 같은 로더로 읽는다. real 쪽은
// `scripts/dump_real_caseview.py`가 쓰고, 파일이 없으면 glob이 비어 mock만 뜬다.
// 화면이 둘을 다르게 다루지 않는 것이 요점이다 — 같은 계약이면 같은 경로로 그려진다.
const modules = {
  ...import.meta.glob('../../../../data/mock/case/*.json', { eager: true }),
  ...import.meta.glob('../../../../data/real/case/*.json', { eager: true }),
} as Record<string, { default: ScenarioFile }>

export interface LoadIssue {
  where: string
  problem: string
}

/**
 * 등재값 검사. 값을 고치거나 기본값을 채우지 않는다 — 계약에 없는 값이 오면
 * 그 사실을 그대로 보고한다(value-state-display.md §4 「없는 상태를
 * INFO_SOURCE_VERIFIED로 간주하지 않는다」).
 *
 * **검사 대상은 문구 맵이 `Record<enum, …>`로 직접 인덱싱하는 값 전부다.** 그 맵들은
 * 미등재 값이 오면 예외도 fallback도 아니고 `undefined`를 돌려주고, 화면에는 빈 칸이 뜬다 —
 * `progress[].state`에 `PARTIAL`이 v1.3에서 추가된 전례가 있으니 가상의 위험이 아니다.
 * 반대로 `label_key` 계열은 계약이 fallback을 명시했으므로(A절 §12) 여기서 보지 않는다.
 */
export function inspectView(view: CaseView, where: string): LoadIssue[] {
  const issues: LoadIssue[] = []
  const expect = (ok: boolean, problem: string): void => {
    if (!ok) issues.push({ where, problem })
  }

  expect(STAGES.includes(view.stage), `미등재 stage: ${view.stage}`)

  for (const step of view.progress) {
    expect(PROGRESS_STATES.includes(step.state),
      `progress[${step.step}].state 미등재: ${step.state}`)
  }
  for (const job of view.running_jobs) {
    expect(JOB_STATUSES.includes(job.status),
      `running_jobs[${job.job_id}].status 미등재: ${job.status}`)
  }
  for (const notice of view.notices) {
    expect(SEVERITIES.includes(notice.severity),
      `notices[${notice.code}].severity 미등재: ${notice.severity}`)
  }
  for (const candidate of view.candidates) {
    expect(SITUATION_CONFIRMATIONS.includes(candidate.situation_confirmation),
      `candidates[${candidate.candidate_id}].situation_confirmation 미등재: ` +
      `${candidate.situation_confirmation}`)
  }
  for (const [key, requirements] of [
    ['requirements_evidence', view.requirements_evidence],
    ['requirements_package', view.requirements_package],
  ] as const) {
    // 객체 자체가 null인 것은 정상이다(§10-10) — 값이 있을 때만 본다.
    if (requirements) {
      expect(READINESSES.includes(requirements.readiness),
        `${key}.readiness 미등재: ${requirements.readiness}`)
    }
  }

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
      issues.push(...inspectView(view, where))
    })
  }
  return { snapshots, issues }
}

const loaded = load()

export const SNAPSHOTS = loaded.snapshots
export const LOAD_ISSUES = loaded.issues
export const SCENARIO_IDS = [...new Set(SNAPSHOTS.map((s) => s.scenarioId))]
