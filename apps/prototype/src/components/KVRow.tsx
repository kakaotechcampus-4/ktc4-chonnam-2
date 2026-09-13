import type { JSX } from 'react';
import type { InfoStatus } from '../types';
import { StatusBadge } from './StatusBadge';

// §5.9 "행 배경 = 그 행의 상태 색" — needs-review는 주황, ai-estimated는 파랑.
// 확정 상태(source-verified/user-confirmed)와 unknown은 흰색/panel 그대로 두므로
// 매핑에 없다. global.css의 `.kv-row.act`/`.kv-row.est`를 그대로 쓴다 — 새 CSS 아님.
const TINT_CLASS: Partial<Record<InfoStatus, string>> = {
  'needs-review': 'act',
  'ai-estimated': 'est',
};

// Mono-Is-Evidence 규칙(DESIGN.md)을 프로퍼티가 아니라 `value`의 생김새로 판단한다
// 이 선택은 prop이 아니라 호출자가 `value`를 포맷하는 방식으로 전달해, 이 컴포넌트를
// 판단 없는 상태로 유지한다. 시각·구간·번호판·파일명처럼 숫자를
// 포함하고 문장 부호가 없는 짧은 문자열만 "데이터"로 보고 mono를 입힌다 — 완전한
// 문장(조사가 붙은 한국어 서술문 등)은 숫자가 없거나 이 패턴을 벗어나 자동으로
// 제외된다. 호출자가 값을 어떻게 "포맷"하는지가 곧 이 판단의 입력이다.
const DATA_SHAPE = /^[0-9A-Za-z가-힣.:_\-–\s?]+$/;

function isDataValue(value: string): boolean {
  return value.length <= 24 && /\d/.test(value) && DATA_SHAPE.test(value);
}

export function KVRow(props: {
  label: string;
  value: string;
  source?: string;
  status?: InfoStatus;
  action?: { label: string; onClick: () => void };
  tint?: boolean;
}): JSX.Element {
  const tintClass = props.tint && props.status ? TINT_CLASS[props.status] : undefined;
  const rowClassName = ['kv-row', tintClass].filter(Boolean).join(' ');
  const valueClassName = [
    'kv-val',
    isDataValue(props.value) ? 'mono' : undefined,
    props.status === 'unknown' ? 'unk' : undefined,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={rowClassName}>
      <span className="kv-k">{props.label}</span>
      <span className="kv-v">
        <span className={valueClassName}>{props.value}</span>
        {props.source && <span className="kv-src">{props.source}</span>}
        {props.action && (
          <span className="kv-act">
            <button type="button" className="btn sm" onClick={props.action.onClick}>
              {props.action.label}
            </button>
          </span>
        )}
      </span>
      {props.status && <StatusBadge status={props.status} />}
    </div>
  );
}
