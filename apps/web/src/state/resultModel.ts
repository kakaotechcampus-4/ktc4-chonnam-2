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
 *   unlinked  — 영상은 있지만(artifact_ref) 파일로 받을 경로가 아직 없다
 * 「다운로드 가능」 상태는 없다 — artifact_ref를 파일로 바꾸는 API가 아직 없다
 * (src/daesingo/api 미구현, 전달 방식 Pending: contract-source-asset-media-stream §9-6).
 * 경로가 생기면 여기서 ready를 돌려주고 화면이 다운로드 버튼을 연다.
 */
export type ReportVideoState = 'none' | 'preparing' | 'failed' | 'unlinked'

export function reportVideoState(view: CaseView): ReportVideoState {
  if (view.running_jobs.some((j) => j.kind === 'REPORT_VIDEO_EXPORT' || j.label_key === 'job.report_video_export'))
    return 'preparing'
  if (view.notices.some((n) => n.code === 'recording.report_video_export_failed')) return 'failed'
  // 「아직 만들지 않음」 notice가 있으면 참조값이 남아 있어도 받을 영상이 없다
  if (!view.package?.artifact_ref || view.notices.some((n) => n.code === 'case.report_video_not_generated')) return 'none'
  return 'unlinked'
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
