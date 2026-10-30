// 결과 화면이 CaseView에서 읽어 내는 규칙 — 화면 부품과 떼어 테스트한다.
// 값을 새로 만들거나 판정하지 않는다. 계약이 준 값을 나누거나(일자·시간), 상태를 고르기만 한다.

import type { CaseView } from '../contracts/caseView'

/**
 * 발생 일시(occurred_at, RFC3339 한 값)를 안전신문고 양식처럼 일자·시간으로 나눈다.
 * 시간만 있으면 일자를 추측하지 않고, 읽을 수 없는 모양이면 둘 다 null이다.
 */
export function splitDateTime(value: string | null): { date: string | null; time: string | null } {
  if (value === null) return { date: null, time: null }
  const full = value.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)/)
  if (full) return { date: full[1], time: full[2] }
  const dateOnly = value.match(/^(\d{4}-\d{2}-\d{2})$/)
  if (dateOnly) return { date: dateOnly[1], time: null }
  const timeOnly = value.match(/^(\d{2}:\d{2}(?::\d{2})?)$/)
  if (timeOnly) return { date: null, time: timeOnly[1] }
  return { date: null, time: null }
}

/**
 * 신고용 영상의 상태. 미리보기와 다운로드는 따로 판단한다.
 *   none      — 아직 만들지 않음(artifact_ref 없음)
 *   preparing — 만드는 작업이 진행 중(running_jobs의 REPORT_VIDEO_EXPORT)
 *   failed    — 만들기 실패 notice
 *   held      — 영상은 만들어졌지만 신고자료 묶음 전이라 받을 수 없다(#447)
 *   ready     — 영상이 있다(artifact_ref). `GET /cases/{case_id}/assets/{artifact_ref}`로 받는다
 * 실제로 받을 수 있는지는 받아 봐야 안다(서버가 UNAVAILABLE을 돌려주면 화면이 실패로 바꾼다).
 */
export type ReportVideoState = 'none' | 'preparing' | 'failed' | 'held' | 'ready'

export function reportVideoState(view: CaseView): ReportVideoState {
  if (view.running_jobs.some((j) => j.kind === 'REPORT_VIDEO_EXPORT' || j.label_key === 'job.report_video_export'))
    return 'preparing'
  if (view.notices.some((n) => n.code === 'recording.report_video_export_failed')) return 'failed'
  // 「아직 만들지 않음」 notice가 있으면 참조값이 남아 있어도 받을 영상이 없다
  if (view.notices.some((n) => n.code === 'case.report_video_not_generated')) return 'none'
  if (!view.package) return videoCheckPassed(view) ? 'held' : 'none'
  if (!view.package.artifact_ref) return 'none'
  return 'ready'
}

// 묶음 전에는 package가 없어 영상 ref를 못 받는다. 영상이 만들어졌는지는 이 check 하나로만 안다(#447)
function videoCheckPassed(view: CaseView): boolean {
  return (view.requirements_package?.checks ?? []).some(
    (c) => (c as { code?: string; outcome?: string }).code === 'package.asset.report_video.exists' && (c as { outcome?: string }).outcome === 'PASS',
  )
}

/** 지금 기준 후보의 id — 결과가 이 후보 것인지 대조하는 데 쓴다 */
export function selectedCandidateId(view: CaseView): string | null {
  return view.candidates.find((c) => c.selected)?.candidate_id ?? null
}

/**
 * 받은 CaseView를 화면에 그려도 되는지. 후보를 바꾼 뒤 늦게 온 이전 후보의 결과가
 * 새 후보 화면을 덮지 않게 한다(case-view 계약 §10 불변조건 — 더 최신 case_rev가 있으면 stale,
 * 이전 선택 context의 결과는 대체 사용하지 않음).
 */
export function acceptView(incoming: CaseView, expected: { caseRev: number; candidateId: string | null }): boolean {
  if (incoming.case_rev < expected.caseRev) return false
  if (expected.candidateId !== null && selectedCandidateId(incoming) !== expected.candidateId) return false
  return true
}
