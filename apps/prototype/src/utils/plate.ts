/** 비교·검증 전용. 화면 표시에 쓰지 않는다. */
export const normalizePlate = (v: string) => v.replace(/\s+/g, '');

/** 형식 검사 — 통과하지 못해도 진행을 막지 않는다(경고만). */
export const isPlateShaped = (v: string) =>
  /^\d{2,3}[가-힣]\d{4}$/.test(normalizePlate(v));
