import type { CaseState } from '../types';

/**
 * 최종 리뷰 fix wave finding #1 — "앞뒤 30분 더 찾아보기".
 *
 * 예전에는 NoResultScreen.tsx가 넓혀질 시간 라벨(from/to)과 축 위 %(fromPct/toPct)만 화면
 * 미리보기용으로 계산하고 실제 파일 개수("9개 → 21개")는 그냥 문자열로 박아뒀다. machine.ts의
 * WIDEN 리듀서는 그 계산을 아예 쓰지 않고 candidates/scannedPct만 리셋했으므로, 버튼을 눌러도
 * case.scope가 그대로 남아 SearchingScreen이 여전히 원래 좁은 구간·9개를 보여주는 버그가 있었다.
 *
 * 이제 이 함수 하나를 NoResultScreen(미리보기 표시)과 machine.ts(WIDEN 실제 반영) 양쪽이 함께
 * 호출해서, 화면이 약속하는 값과 실제로 반영되는 case.scope가 항상 같은 계산에서 나오게 한다.
 */
export const WIDEN_MINUTES = 30; // "앞뒤 30분 더 찾아보기"

function parseMinutes(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function toHHMM(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/**
 * @param scope 넓히기 전 scope (case.scope)
 * @param driveStart/driveEnd 전체 주행 커버리지 (mock/files.ts DRIVE_START/DRIVE_END) — 넓힌
 *   구간이 실제 촬영 범위를 벗어나지 않도록 이 안에서 clamp한다.
 */
export function computeWidenedScope(
  scope: CaseState['scope'],
  driveStart: string,
  driveEnd: string,
): CaseState['scope'] {
  const fromMin = parseMinutes(scope.from);
  const toMin = parseMinutes(scope.to);
  const driveStartMin = parseMinutes(driveStart);
  const driveEndMin = parseMinutes(driveEnd);

  // 잘못된 형식이면 안전하게 원래 scope를 그대로 돌려준다 — 넓히기를 실패시키기보다는
  // no-op이 낫다(이 화면에 오는 scope는 항상 'HH:MM' 형식이라 실제로는 일어나지 않는다).
  if (fromMin === null || toMin === null || driveStartMin === null || driveEndMin === null || toMin <= fromMin) {
    return { ...scope };
  }

  const widenFromMin = Math.max(driveStartMin, fromMin - WIDEN_MINUTES);
  const widenToMin = Math.min(driveEndMin, toMin + WIDEN_MINUTES);

  // 축 위 %는 scope 자신의 분당 비율(fromPct~toPct가 이미 encode하고 있는 비율)로 바깥쪽에도
  // 그대로 적용한다 — NoResultScreen.tsx가 원래 하던 계산 그대로.
  const pctPerMinute = (scope.toPct - scope.fromPct) / (toMin - fromMin);
  const widenOffsetPct = WIDEN_MINUTES * pctPerMinute;
  const fromPct = Math.max(0, scope.fromPct - widenOffsetPct);
  const toPct = Math.min(100, scope.toPct + widenOffsetPct);

  // 파일 개수: 스펙/목업 어디에도 "넓힌 뒤 개수"의 일반 공식은 없다 — 목업이 보여주는 건 기본
  // 시나리오(18:15–18:45 → 17:45–19:12)의 "9개 → 21개"라는 고정된 예시 값 하나뿐이다. 여기서는
  // 전체 주행의 분당 평균 파일 밀도(scope.totalFiles / 주행 전체 분)를 "새로 넓어진 분"에 곱해
  // 올림한 값을 더한다: 42개/212분 ≈ 0.198개/분 × 추가 57분(87분-30분) ≈ 11.3 → 올림 12개 →
  // 9+12=21개 — 기본 시나리오의 21을 그대로 재현한다. 올림(ceil)을 쓰는 이유는 "이만큼 더
  // 확인합니다"라는 안내를 실제보다 적게 약속하지 않기 위해서다.
  const driveDurationMin = Math.max(1, driveEndMin - driveStartMin);
  const filesPerMinute = scope.totalFiles / driveDurationMin;
  const addedMinutes = Math.max(0, widenToMin - widenFromMin - (toMin - fromMin));
  const files = Math.min(scope.totalFiles, scope.files + Math.ceil(filesPerMinute * addedMinutes));

  return {
    from: toHHMM(widenFromMin),
    to: toHHMM(widenToMin),
    files,
    totalFiles: scope.totalFiles,
    fromPct,
    toPct,
  };
}
