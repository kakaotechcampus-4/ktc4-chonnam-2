// CaseView 소비 회귀 테스트.
//
// 눈으로 한 번 확인한 것은 fixture가 바뀌면 조용히 어긋난다. 「16건이 전부
// 렌더된다」·「미등록 값이 fallback으로 새지 않는다」를 여기서 고정한다.
// 렌더러가 아니라 계약 소비 지점(로더·화면 선택·라벨 맵)을 검증한다 — 화면
// 자체는 목업 설계가 들어오면 바뀌지만 이 규칙들은 바뀌지 않는다.

import { describe, expect, it } from 'vitest'
import { LOAD_ISSUES, SCENARIO_IDS, SNAPSHOTS, inspectView } from '../contracts/fixtures'
import {
  INFO_STATES,
  JOB_LABEL_FALLBACK_KEY,
  JOB_LABEL_KEYS,
  PROGRESS_STATES,
  READINESSES,
  REVIEW_REASON_CODES,
  SITUATION_CONFIRMATIONS,
} from '../contracts/registry'
import { ACTIONS, isAction, type InfoState } from '../contracts/caseView'
import {
  ACTION_LABELS,
  AT_PROVENANCE_FALLBACK,
  PROGRESS_LABELS,
  READINESS_NOT_CHECKED,
  REVIEW_REASON_FALLBACK,
  SITUATION_LABELS,
  jobLabel,
  readinessLabel,
  reviewReason,
  KNOWN_LABEL_KEYS,
  INFO_STATE_LABELS,
  NOTICE_FALLBACK,
  SOURCE_FALLBACK,
  atProvenanceLabel,
  noticeMessage,
  sourceLabel,
} from '../contracts/labels'
import { ACTION_INTENT, describeIntent } from '../contracts/actionIntent'
import { representativeJobs, selectScreen } from '../state/selectScreen'

const views = SNAPSHOTS.map((s) => s.view)

describe('Input (web)', () => {
  it('7 시나리오 16 스냅샷을 로딩한다', () => {
    expect(SCENARIO_IDS).toHaveLength(7)
    expect(SNAPSHOTS).toHaveLength(16)
  })

  it('등재값 위반이 없다', () => {
    expect(LOAD_ISSUES).toEqual([])
  })

  it('로더가 계약 값을 변형하지 않는다', () => {
    // 값 재계산 금지의 최소 회귀 — 로더를 통과한 객체가 원본 JSON과 같아야 한다.
    const happy = views.find((v) => v.case_id === 'case_h001' && v.stage === 'READY')
    expect(happy?.evidence?.location_display.info_state).toBe('INFO_NEEDS_REVIEW')
    expect(happy?.evidence?.location_display.needs_review).toBe(false)
  })
})

describe('화면 선택', () => {
  it('16건 전부 화면이 정해진다', () => {
    for (const view of views) expect(selectScreen(view).kind).toBeTruthy()
  })

  it('후보 0건은 실패가 아니라 빈 결과다', () => {
    const empty = views.find((v) => v.case_id === 'case_e001')!
    expect(selectScreen(empty).kind).toBe('NO_RESULT')
  })

  it('evidence 조립 전은 진행 상태 화면이다', () => {
    const before = views.filter((v) => v.stage === 'EVIDENCE_REVIEW' && v.evidence === null)
    expect(before.length).toBeGreaterThan(0)
    for (const view of before) expect(selectScreen(view).kind).toBe('PROGRESS')
  })

  it('READY + package면 신고자료 화면이다', () => {
    const ready = views.filter((v) => v.stage === 'READY')
    expect(ready.length).toBe(3)
    for (const view of ready) expect(selectScreen(view).kind).toBe('HANDOFF')
  })

  it('blocking notice는 non-blocking과 분리된다', () => {
    const all = views.map(selectScreen)
    const blocking = all.flatMap((s) => s.blocking)
    const info = all.flatMap((s) => s.info)
    expect(blocking).toHaveLength(1)
    expect(blocking[0].code).toBe('readout.plate_read_failed')
    expect(info.every((n) => n.blocking === false)).toBe(true)
  })

  it('같은 job_id는 대표 하나만 남는다', () => {
    // v5 fixture에 중복 job_id가 없어 합성 입력으로 규칙만 고정한다.
    const jobs = [
      { job_id: 'j1', kind: 'PLATE_READ', label_key: 'job.plate_read', status: 'PENDING' as const, attempt: 1 },
      { job_id: 'j1', kind: 'PLATE_READ', label_key: 'job.plate_read', status: 'RUNNING' as const, attempt: 2 },
      { job_id: 'j2', kind: 'COARSE_SEARCH', label_key: 'job.generic_processing', status: 'RUNNING' as const },
    ]
    const kept = representativeJobs(jobs)
    expect(kept).toHaveLength(2)
    expect(kept.find((j) => j.job_id === 'j1')?.attempt).toBe(2)
  })
})

describe('라벨 매핑 — fallback으로 새지 않는다', () => {
  it('notices message_key 전부가 매핑돼 있다', () => {
    const keys = [...new Set(views.flatMap((v) => v.notices.map((n) => n.message_key)))]
    expect(keys).toHaveLength(13)
    for (const key of keys) expect(noticeMessage(key)).not.toBe(NOTICE_FALLBACK)
  })

  it('fixture에 아직 없는 계약 등재 문구도 매핑돼 있다', () => {
    // 위 테스트는 fixture에 있는 키만 훑는다. #48에서 확정된 이 키는 아직
    // 어느 fixture도 내지 않아 그 그물에 안 걸린다 — 오타가 나면 화면에만
    // fallback이 뜨고 아무도 모른다.
    expect(noticeMessage('notice.location_search_keyword_missing'))
      .not.toBe(NOTICE_FALLBACK)
  })

  it('notices code는 12종이다', () => {
    const codes = [...new Set(views.flatMap((v) => v.notices.map((n) => n.code)))]
    expect(codes).toHaveLength(12)
  })

  it('source_label_key 전부가 매핑돼 있다', () => {
    const keys = new Set<string>()
    for (const view of views) {
      const e = view.evidence
      if (!e) continue
      for (const d of [
        e.plate_display,
        e.event_time_display,
        e.location_display,
        e.case_type_display,
        e.violation_display,
        e.report_type_display,
      ]) {
        if (d.source_label_key) keys.add(d.source_label_key)
      }
      for (const state of Object.values(view.package?.report_field_states ?? {})) {
        if (state.source_label_key) keys.add(state.source_label_key)
      }
    }
    for (const key of keys) expect(sourceLabel(key)).not.toBe(SOURCE_FALLBACK)
  })

  it('fixture의 actions는 전부 등재 7종 안에 있고 라벨을 갖는다', () => {
    const used = [...new Set(views.flatMap((v) => v.notices.flatMap((n) => n.actions)))]
    expect(used).toHaveLength(7)
    for (const action of used) {
      expect(isAction(action)).toBe(true)
      if (isAction(action)) expect(ACTION_LABELS[action]).toBeTruthy()
    }
    expect(ACTIONS).toHaveLength(7)
  })

  it('CaseView 안의 모든 *_label_key가 매핑돼 있다', () => {
    // 필드 이름을 열거하지 않고 훑는다. 계약에 새 label_key가 생기면
    // (v1.4의 at_provenance_label_key 등) 매핑을 만들기 전까지 여기서 깨진다.
    const found = new Set<string>()
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) return node.forEach(walk)
      if (node && typeof node === 'object') {
        for (const [key, value] of Object.entries(node)) {
          if (key.endsWith('_label_key') && typeof value === 'string') found.add(value)
          else walk(value)
        }
      }
    }
    walk(views)
    expect(found.size).toBeGreaterThan(0)
    for (const key of found) expect(KNOWN_LABEL_KEYS).toContain(key)
  })

  it('미등록 action은 버튼을 만들지 않는다', () => {
    expect(isAction('RESUME_SEARCH')).toBe(false)
  })

  it('at_provenance_label_key 등재 3종이 문구를 갖는다 (case-view/v1.4 §7)', () => {
    expect(atProvenanceLabel('candidate.at_provenance.filename_time')).not.toBe(AT_PROVENANCE_FALLBACK)
    expect(atProvenanceLabel('candidate.at_provenance.overlay_ocr')).not.toBe(AT_PROVENANCE_FALLBACK)
    expect(atProvenanceLabel('candidate.at_provenance.timeline_relative_only')).not.toBe(
      AT_PROVENANCE_FALLBACK,
    )
    for (const key of [
      'candidate.at_provenance.filename_time',
      'candidate.at_provenance.overlay_ocr',
      'candidate.at_provenance.timeline_relative_only',
    ]) {
      expect(KNOWN_LABEL_KEYS).toContain(key)
    }
  })

  it('label_key가 null이거나 미등록이면 같은 fallback 문구다 (§10-14)', () => {
    // 「매핑 안 되는 raw」와 「값 자체를 모름」을 나누지 않기로 한 결정.
    expect(atProvenanceLabel(null)).toBe(AT_PROVENANCE_FALLBACK)
    expect(atProvenanceLabel('candidate.at_provenance.made_up')).toBe(AT_PROVENANCE_FALLBACK)
    // v5 fixture는 계약이 Y로 정한 이 필드를 아직 안 내린다 — undefined도 같은 자리로.
    expect(atProvenanceLabel(undefined)).toBe(AT_PROVENANCE_FALLBACK)
  })

  it('raw at_provenance를 문구로 해석하지 않는다', () => {
    // raw 값이 label_key 자리에 잘못 들어오면 fallback으로 빠져야 한다.
    const raws = [...new Set(views.flatMap((v) => v.candidates.map((c) => c.at_provenance)))]
    expect(raws.length).toBeGreaterThan(0)
    for (const raw of raws) expect(atProvenanceLabel(raw)).toBe(AT_PROVENANCE_FALLBACK)
  })

  it('fixture가 at_provenance_label_key를 내리면 전부 매핑돼 있다', () => {
    // 지금은 0건이라 공회전한다. fixture 반영 시점에 이 단언이 살아난다.
    const keys = views
      .flatMap((v) => v.candidates)
      .map((c) => c.at_provenance_label_key)
      .filter((k): k is string => typeof k === 'string')
    for (const key of keys) expect(atProvenanceLabel(key)).not.toBe(AT_PROVENANCE_FALLBACK)
  })
})

describe('계약 등재 목록 전수 매핑 — fixture에 없는 값도 문구를 갖는다', () => {
  // fixture를 훑는 검사만 있으면 「계약엔 등재됐는데 fixture엔 아직 없는 값」이 영영 안 잡힌다.
  // 실제로 등재 label_key 4종 중 3종이 「처리 중」 fallback으로 뭉개지고 있었다.

  it('등재 label_key 4종이 fallback 문구로 새지 않는다', () => {
    const fallback = jobLabel(JOB_LABEL_FALLBACK_KEY)
    for (const key of JOB_LABEL_KEYS) {
      expect(jobLabel(key), key).not.toBe(fallback)
    }
    expect(jobLabel('job.not_registered_yet')).toBe(fallback)
  })

  it('progress 상태 5종 · 상황 확인 4종 · 정보 상태 5종이 전부 문구를 갖는다', () => {
    for (const state of PROGRESS_STATES) expect(PROGRESS_LABELS[state], state).toBeTruthy()
    for (const value of SITUATION_CONFIRMATIONS) expect(SITUATION_LABELS[value], value).toBeTruthy()
    for (const state of INFO_STATES) expect(INFO_STATE_LABELS[state], state).toBeTruthy()
  })

  it('readiness 4종이 등재값 그대로 화면에 나가지 않는다', () => {
    for (const readiness of READINESSES) {
      const label = readinessLabel(readiness)
      expect(label, readiness).toBeTruthy()
      expect(label, readiness).not.toBe(readiness)
    }
    // 객체 자체가 null인 것은 「아직 판정 안 함」이고 UNKNOWN과 다른 문구다(§10-10).
    expect(readinessLabel(null)).toBe(READINESS_NOT_CHECKED)
    expect(readinessLabel(undefined)).toBe(READINESS_NOT_CHECKED)
    expect(readinessLabel('UNKNOWN')).not.toBe(READINESS_NOT_CHECKED)
  })

  it('reason_code 3종이 매핑돼 있고 raw가 화면에 나가지 않는다', () => {
    for (const code of REVIEW_REASON_CODES) {
      expect(reviewReason(code), code).not.toBe(REVIEW_REASON_FALLBACK)
      expect(reviewReason(code), code).not.toContain(code)
    }
    expect(reviewReason(null)).toBe(REVIEW_REASON_FALLBACK)
    expect(reviewReason('evidence.something_new')).toBe(REVIEW_REASON_FALLBACK)
  })

  it('fixture가 쓰는 reason_code는 전부 등재 목록 안에 있다', () => {
    const used = views.map((v) => v.evidence?.reason_code).filter((c): c is string => !!c)
    expect(used.length).toBeGreaterThan(0)
    for (const code of used) expect(REVIEW_REASON_CODES).toContain(code)
  })
})

describe('로더 등재값 검사 — 문구 맵이 빈 칸을 뱉기 전에 잡는다', () => {
  const sample = (): ReturnType<typeof structuredClone<(typeof views)[number]>> =>
    structuredClone(views.find((v) => v.package !== null && v.candidates.length > 0) ?? views[0])

  it('미등재 progress.state를 잡는다', () => {
    const view = sample()
    view.progress[0] = { ...view.progress[0], state: 'SKIPPED' as never }
    expect(inspectView(view, 'test')).toHaveLength(1)
  })

  it('미등재 severity · readiness · situation_confirmation · job status를 잡는다', () => {
    const view = sample()
    if (view.notices.length > 0) view.notices[0] = { ...view.notices[0], severity: 'FATAL' as never }
    if (view.requirements_package) view.requirements_package.readiness = 'MAYBE' as never
    if (view.candidates.length > 0) {
      view.candidates[0] = { ...view.candidates[0], situation_confirmation: 'ASKED' as never }
    }
    view.running_jobs = [
      { job_id: 'job_t', kind: 'PLATE_READ', label_key: 'job.plate_read', status: 'DONE' as never },
    ]
    const problems = inspectView(view, 'test').map((i) => i.problem)
    expect(problems.some((p) => p.includes('readiness'))).toBe(true)
    expect(problems.some((p) => p.includes('situation_confirmation'))).toBe(true)
    expect(problems.some((p) => p.includes('status'))).toBe(true)
  })

  it('미등록 label_key는 문제로 보지 않는다 — 계약이 fallback을 명시했다(A절 §12)', () => {
    const view = sample()
    view.running_jobs = [
      { job_id: 'job_t', kind: 'NEW_KIND', label_key: 'job.brand_new', status: 'RUNNING' },
    ]
    expect(inspectView(view, 'test')).toEqual([])
  })
})

describe('값 상태 표시 규칙', () => {
  it('info_state 5종이 전부 fixture에 등장하고 라벨을 갖는다', () => {
    const seen = new Set<InfoState>()
    for (const view of views) {
      const e = view.evidence
      if (!e) continue
      for (const d of [
        e.plate_display,
        e.event_time_display,
        e.location_display,
        e.case_type_display,
        e.violation_display,
        e.report_type_display,
      ]) {
        seen.add(d.info_state)
      }
    }
    expect(seen.size).toBe(5)
    for (const state of seen) expect(INFO_STATE_LABELS[state]).toBeTruthy()
  })

  it('UNKNOWN·NOT_APPLICABLE 계열은 값이 null이다', () => {
    for (const view of views) {
      const e = view.evidence
      if (!e) continue
      if (e.plate_display.info_state === 'INFO_UNKNOWN') expect(e.plate_display.value).toBeNull()
    }
  })

  it('report_field_states가 report_fields 전 필드를 덮는다', () => {
    for (const view of views) {
      const pkg = view.package
      if (!pkg) continue
      for (const key of Object.keys(pkg.report_fields)) {
        expect(pkg.report_field_states[key]).toBeDefined()
      }
    }
  })

  it('unconfirmed_fields는 report_field_states에서 파생된 목록과 일치한다', () => {
    const UNCONFIRMED: InfoState[] = ['INFO_AI_ESTIMATED', 'INFO_NEEDS_REVIEW', 'INFO_UNKNOWN']
    for (const view of views) {
      const pkg = view.package
      if (!pkg) continue
      const derived = Object.entries(pkg.report_field_states)
        .filter(([, s]) => UNCONFIRMED.includes(s.info_state))
        .map(([k]) => k)
      expect([...pkg.unconfirmed_fields].sort()).toEqual(derived.sort())
    }
  })

  it('WARN에서도 제출 경로가 열린다', () => {
    const warn = views.find((v) => v.requirements_package?.readiness === 'WARN')
    expect(warn?.package?.capabilities).toHaveLength(3)
  })
})

describe('actions → 발주 매핑 (계약 A절 §7)', () => {
  it('등재 7종 전부에 발주 의도가 있다', () => {
    for (const action of ACTIONS) expect(ACTION_INTENT[action]).toBeDefined()
  })

  it('JobRecord를 만드는 건 3종뿐이다', () => {
    const jobs = ACTIONS.filter((a) => ACTION_INTENT[a].type === 'JOB')
    expect(jobs.sort()).toEqual(['GENERATE_REPORT_VIDEO', 'RETRY_PLATE_READ', 'RETRY_SEARCH'])
  })

  it('발주 kind가 계약 등재값이다', () => {
    const REGISTERED = ['PLATE_READ', 'COARSE_SEARCH', 'REPORT_VIDEO_EXPORT']
    for (const action of ACTIONS) {
      const intent = ACTION_INTENT[action]
      if (intent.type === 'JOB') expect(REGISTERED).toContain(intent.jobKind)
    }
  })

  it('재시도 계열은 force_rerun 없이 새 job_id로 성립한다', () => {
    // FAILED·candidates=[]는 cache hit 대상이 아니다(A절 §7). EvidenceNeeds의
    // PLATE_REREAD 경로가 force_rerun=true를 붙이는 것은 case 소관이라 다르다.
    for (const action of ['RETRY_PLATE_READ', 'RETRY_SEARCH'] as const) {
      const intent = ACTION_INTENT[action]
      expect(intent.type).toBe('JOB')
      if (intent.type === 'JOB') expect(intent.forceRerun).toBe(false)
    }
  })

  it('fixture에 실제로 오는 action은 전부 설명 가능하다', () => {
    const used = [...new Set(views.flatMap((v) => v.notices.flatMap((n) => n.actions)))]
    for (const action of used) {
      if (isAction(action)) expect(describeIntent(action)).toMatch(/발주/)
    }
  })
})
