// 표시 키 → 화면 문구.
//
// 규칙(value-state-display.md §3-2): web은 label_key로 문구를 고르고
// source.kind 문자열을 직접 해석하지 않는다. 미등록 키는 지어내지 않고
// fallback 문구를 쓴다 — 단 actions[]만은 fallback 없이 버튼을 렌더하지
// 않는다(계약 B절 §7).

import type { Action, InfoState, ProgressState, SituationConfirmation } from './caseView'

/** 값의 출처 — `*_display.source_label_key` (v5 fixture 실측 9종) */
const SOURCE_LABELS: Record<string, string> = {
  'plate.source.plate_ocr': '번호판 판독',
  'time.source.filename': '파일명',
  'time.source.filename_time': '파일명 시각',
  'time.source.overlay_ocr': '영상 화면 시각',
  'time.source.user_correction': '사용자 정정',
  'location.source.user_hint': '사용자가 말한 위치',
  'event.source.visual_inference': '영상 분석',
  'event.source.category_mapping': '분류 매핑',
  'event.source.violation_expression': 'AI 작성 위반 문장',
}

/** 미등록 키 fallback — 계약이 `running_jobs[].label_key`에 정한 것과 같은 패턴 */
export const SOURCE_FALLBACK = '출처 확인 중'

export function sourceLabel(key: string | null): string | null {
  if (key === null) return null
  return SOURCE_LABELS[key] ?? SOURCE_FALLBACK
}

/** 진행 중 작업 — `running_jobs[].label_key` */
const JOB_LABELS: Record<string, string> = {
  'job.generic_processing': '처리 중',
  'job.plate_read': '번호판 판독 중',
}

export function jobLabel(key: string): string {
  return JOB_LABELS[key] ?? JOB_LABELS['job.generic_processing']
}

/** 안내 문구 — `notices[].message_key` (v5 fixture 실측 13종) */
const NOTICE_MESSAGES: Record<string, string> = {
  'notice.event_time_needs_review': '사건 시각을 확인해 주세요.',
  'notice.time_conflict': '시각 단서가 서로 달라 확인이 필요합니다.',
  'notice.post_stamp_required': '촬영 후 찍힌 시각이라 확인이 필요합니다.',
  'notice.time_post_stamp_required': '촬영 후 찍힌 시각이라 확인이 필요합니다.',
  'notice.overlay_not_present': '영상에 시각 표시가 없습니다.',
  'notice.overlay_presence_undetermined': '영상에 시각 표시가 있는지 확인하지 못했습니다.',
  'notice.overlay_ocr_failed': '영상의 시각 표시를 읽지 못했습니다.',
  'notice.plate_abstained': '번호판을 확정하지 못했습니다.',
  'notice.plate_read_failed_retry_exhausted': '번호판 판독에 실패했습니다.',
  'notice.plate_read_cancelled': '번호판 판독이 중단됐습니다.',
  'notice.search_no_candidates': '조건에 맞는 장면을 찾지 못했습니다.',
  'notice.visual_event_unconfirmed': '어떤 상황인지 아직 확인되지 않았습니다.',
  'notice.report_video_not_generated': '신고용 영상이 아직 만들어지지 않았습니다.',
}

export const NOTICE_FALLBACK = '확인이 필요한 항목이 있습니다.'

export function noticeMessage(key: string): string {
  return NOTICE_MESSAGES[key] ?? NOTICE_FALLBACK
}

/** 버튼 — 닫힌 7종. 미등록 값은 렌더하지 않으므로 fallback을 두지 않는다. */
export const ACTION_LABELS: Record<Action, string> = {
  EDIT_EVENT_TIME: '시각 직접 입력',
  MANUAL_PLATE_INPUT: '번호판 직접 입력',
  GENERATE_REPORT_VIDEO: '신고용 영상 만들기',
  REVIEW_TIME: '시각 확인하기',
  RETRY_PLATE_READ: '번호판 다시 읽기',
  EDIT_HINT: '설명 고치기',
  RETRY_SEARCH: '다시 찾기',
}

/** 과거 timeline revision 기준 후보 — `candidates[].stale_revision_label_key` */
const STALE_LABELS: Record<string, string> = {
  'candidate.stale_timeline_revision': '이전 기준으로 찾은 장면',
}

export const STALE_FALLBACK = '이전 기준'

export function staleLabel(key: string | null): string | null {
  if (key === null) return null
  return STALE_LABELS[key] ?? STALE_FALLBACK
}

/**
 * 상황 확인 — 닫힌 4종이고 label_key가 내려오지 않아 web이 문구를 갖는다
 * (value-state-display.md §5-3). NOT_ASKED와 USER_UNSURE를 같은 빈칸으로
 * 합치지 않는 것이 이 필드가 생긴 이유다.
 */
export const SITUATION_LABELS: Record<SituationConfirmation, string> = {
  NOT_ASKED: '아직 확인하지 않음',
  CONFIRMED: '사용자 확인됨',
  CORRECTED: '사용자가 고침',
  USER_UNSURE: '모르겠다고 답함',
}

/** 정보 상태 5종 — `core-user-flow.md` §3-1 이름을 그대로 쓴다 */
export const INFO_STATE_LABELS: Record<InfoState, string> = {
  INFO_USER_CONFIRMED: '사용자 확인됨',
  INFO_SOURCE_VERIFIED: '출처 확인됨',
  INFO_AI_ESTIMATED: 'AI 추정',
  INFO_NEEDS_REVIEW: '확인 필요',
  INFO_UNKNOWN: '알 수 없음',
}

const STEP_LABELS: Record<string, string> = {
  file_intake: '영상 등록',
  coarse_search: '장면 찾기',
  candidate_review: '후보 확인',
  plate_read: '번호판 판독',
  overlay_time_read: '화면 시각 판독',
  evidence_assembly: '증거 정리',
  requirement_check: '신고요건 확인',
  package_assembly: '신고자료 만들기',
}

export function stepLabel(step: string): string {
  return STEP_LABELS[step] ?? step
}

export const PROGRESS_LABELS: Record<ProgressState, string> = {
  PENDING: '대기',
  RUNNING: '진행 중',
  DONE: '완료',
  FAILED: '실패',
  PARTIAL: '부분 완료',
}

const REPORT_FIELD_LABELS: Record<string, string> = {
  safety_report_type: '신고 유형',
  occurred_at: '발생 시각',
  location: '발생 장소',
  vehicle_number: '차량 번호',
  violation_expression: '위반 내용',
}

export function reportFieldLabel(key: string): string {
  return REPORT_FIELD_LABELS[key] ?? key
}
