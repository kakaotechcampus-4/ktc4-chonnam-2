import type { JSX } from 'react';

/**
 * 마커 28px 원이 겹치지 않을 최소 간격(퍼센트 포인트)의 근사치.
 *
 * DESIGN-stage1-mockups.html 1434–1438행(화면 4의 `.apins`)이 실측으로 남긴 좌표
 * (72.8% / 75.6% / 77.2%)가 이 값의 근거다: 2.8%p 간격(75.6↔77.2, 72.8↔75.6)은
 * 겹쳐서 가운데 마커("2")가 `.apin.r1`(2번째 줄)로 내려가지만, 4.4%p 간격
 * (72.8↔77.2, "3"↔"1")은 겹치지 않고 둘 다 1번째 줄에 남는다. 실제 축 너비는
 * 반응형이라 px 단위로 정확히 계산할 방법이 없으므로, 목업이 보여준 이 두 경계값
 * 사이의 값을 상수로 고정했다.
 */
const COLLISION_THRESHOLD_PCT = 3.5;

type Marker = { n: number; pct: number; selected?: boolean };

/**
 * 겹치는 마커는 아래 줄로 내리고 연결선을 늘린다 — PROTOTYPE-SPEC.md §6이
 * "1단계에서 두 번 고친 규칙"이라 부르는 그 규칙. `pct` 오름차순으로 훑으면서,
 * 마지막으로 1번째 줄에 놓인 마커와 너무 가까우면 2번째 줄(`r1`)로 내린다.
 */
function computeRows(markers: Marker[]): Map<number, 0 | 1> {
  const rows = new Map<number, 0 | 1>();
  const sorted = [...markers].sort((a, b) => a.pct - b.pct);
  let anchorPct: number | null = null;
  for (const marker of sorted) {
    if (anchorPct === null || marker.pct - anchorPct >= COLLISION_THRESHOLD_PCT) {
      rows.set(marker.n, 0);
      anchorPct = marker.pct;
    } else {
      rows.set(marker.n, 1);
    }
  }
  return rows;
}

function parseMinutes(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

/**
 * `from`–`to` 사이의 정시(예: 16:00, 17:00) 눈금. 목업(1428–1432행)은 이 값들을
 * 실제 영상 구간에 맞춰 손으로 박아뒀지만, 이 컴포넌트는 임의의 `from`/`to`
 * 문자열을 받으므로 "HH:MM" 형식을 파싱해 정시 경계를 계산한다. 파싱에 실패하면
 * (형식이 다르면) 중간 눈금 없이 양끝 라벨만 그린다 — 축 자체는 여전히 올바르다.
 */
function hourTicks(from: string, to: string): { label: string; pct: number }[] {
  const start = parseMinutes(from);
  const end = parseMinutes(to);
  if (start === null || end === null || end <= start) return [];
  const ticks: { label: string; pct: number }[] = [];
  const firstHour = Math.floor(start / 60) + 1;
  for (let h = firstHour; h * 60 < end; h++) {
    const minutes = h * 60;
    if (minutes <= start) continue;
    ticks.push({
      label: `${String(h % 24).padStart(2, '0')}:00`,
      pct: ((minutes - start) / (end - start)) * 100,
    });
  }
  return ticks;
}

export function SearchAxis(props: {
  from: string;
  to: string;
  scope: { fromPct: number; toPct: number };
  scannedPct: number;
  markers: Marker[];
  legend?: boolean;
}): JSX.Element {
  const scopeLeft = props.scope.fromPct;
  const scopeWidth = props.scope.toPct - props.scope.fromPct;
  const clampedScanned = Math.min(100, Math.max(0, props.scannedPct));
  // §5.5: scannedPct는 scope 구간 자체의 진행률이다 — 전체 축이 아니라
  // scope 너비(scopeWidth) 안에서만 초록으로 채운다.
  const scannedWidth = scopeWidth * (clampedScanned / 100);
  const rows = computeRows(props.markers);
  const ticks = hourTicks(props.from, props.to);

  return (
    <>
      <div className="axis">
        <div className="aseg rest" style={{ left: 0, right: 0 }} />
        <div className="aseg scope" style={{ left: `${scopeLeft}%`, width: `${scopeWidth}%` }} />
        <div className="aseg scanned" style={{ left: `${scopeLeft}%`, width: `${scannedWidth}%` }} />
        <div className="aticks" />
        <div className="abr" style={{ left: `${scopeLeft}%`, width: `${scopeWidth}%` }} />
      </div>
      <div className="aruler">
        <span className="atk e0">{props.from}</span>
        {ticks.map((tick) => (
          <span key={tick.label} className="atk" style={{ left: `${tick.pct}%` }}>
            {tick.label}
          </span>
        ))}
        <span className="atk e1">{props.to}</span>
      </div>
      <div className="apins">
        {/* 시각은 여기 쓰지 않는다 — PROTOTYPE-SPEC.md §6 "시각은 막대에 쓰지 않는다".
            시각은 옆 목록(WorkList/후보 카드)에서 읽는다. */}
        {props.markers.map((marker) => (
          <div
            key={marker.n}
            className={`apin${rows.get(marker.n) === 1 ? ' r1' : ''}${marker.selected ? ' sel' : ''}`}
            style={{ left: `${marker.pct}%` }}
          >
            <b>{marker.n}</b>
            <i />
          </div>
        ))}
      </div>
      {props.legend && (
        <div className="alegend">
          <span className="alg">
            <i className="scanned" />
            확인 끝난 구간
          </span>
          <span className="alg">
            <i className="scope" />
            남은 구간
          </span>
          <span className="alg">
            <i className="marker" />
            찾은 후보 · 시각은 오른쪽 목록에
          </span>
        </div>
      )}
    </>
  );
}
