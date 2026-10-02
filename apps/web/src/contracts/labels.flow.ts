// 진행 화면 전용 문구 — `labels.ts`에 합치는 것은 web Owner가 한다.
//
// 여기 있는 것은 계약의 `*_label_key`가 아니다. `progress[].step` 이름을 진행 화면의
// 안내 문구로 바꾸는 표이고, 키는 이 파일이 소유한다(`labels.candidate.ts`와 같은 취급).

import { stepLabel } from './labels'

/** 단계 하나가 실패했을 때의 안내. 조사가 단계마다 달라 문장째로 둔다 */
const STEP_FAILED: Record<string, string> = {
  plate_read: '번호판을 읽지 못했어요.',
  overlay_time_read: '영상에 표시된 시간을 읽지 못했어요.',
  evidence_assembly: '증거를 정리하지 못했어요.',
  requirement_check: '신고요건을 확인하지 못했어요.',
}

// 받침이 있으면 「을」, 없으면 「를」. 한글이 아니면 「을」로 둔다.
function objectParticle(word: string): string {
  const code = word.charCodeAt(word.length - 1) - 0xac00
  if (code < 0 || code > 11171) return '을'
  return code % 28 === 0 ? '를' : '을'
}

export function stepFailedLabel(step: string): string {
  const known = STEP_FAILED[step]
  if (known) return known
  const label = stepLabel(step)
  return `「${label}」${objectParticle(label)} 마치지 못했어요.`
}

/** 두 단계 이상 실패했을 때 — 줄을 반복하지 않고 요약한다. 어느 단계인지는 단계 목록에 있다 */
export const SOME_STEPS_FAILED = '일부 작업을 마치지 못했어요.'

/** 다른 단계가 실제로 RUNNING일 때만 붙인다 */
export const OTHERS_CONTINUING = '나머지 작업은 계속하고 있어요.'

/**
 * 큰 제목 아래 상태 줄. 제목은 단계 이름이라 「완료」만 쓰면 전체 작업이 끝난 것처럼
 * 읽힌다 — 끝난 상태에는 「이 단계」를 붙인다.
 */
export const CURRENT_STEP_STATE = {
  RUNNING: '진행 중',
  DONE: '이 단계 완료',
  FAILED: '이 단계 실패',
  PARTIAL: '이 단계 부분 완료',
  PENDING: '대기',
} as const

/** 파일이 여러 개일 때 접힌 목록의 제목 */
export const videoCount = (n: number): string => `영상 ${n}개`

/** 진행 화면 오른쪽 단계 목록 제목과 개수(progress 길이 그대로) */
export const STEPS_HEADING = '진행 단계'
export const stepCount = (n: number): string => `전체 ${n}단계`

/** 업로드에서 정상으로 받아들인 첫 파일의 정지 화면 자리. 분석 중인 파일이라는 뜻이 아니다 */
export const REPRESENTATIVE_VIDEO = '대표 영상'

/** 상황 설명 제목 — 결과 없음 화면의 「적어 주신 상황」과 같은 말 */
export const SITUATION_HEADING = '적어 주신 상황'
