import { Check } from 'lucide-react';
import type { JSX } from 'react';
import type { WorkStatus } from '../types';

// Work states never share a component with StatusBadge/InfoStatus — see
// DESIGN.md §Components "작업 상태 — 배지를 쓰지 않는다". Row icon mapping:
// done -> check, running -> filled dot ("now" in the mockup's own CSS),
// everything else (waiting/partial/stopped/failed) -> the plain outline
// circle .wic already renders with no icon inside it.
function rowClassName(status: WorkStatus): string {
  if (status === 'done') return 'done';
  if (status === 'running') return 'now';
  return '';
}

export function WorkList(props: {
  items: { label: string; status: WorkStatus; note?: string }[];
}): JSX.Element {
  return (
    <ul className="work">
      {props.items.map((item, i) => (
        <li key={i} className={rowClassName(item.status)}>
          <span className="wic">
            {item.status === 'done' && <Check size={14} color="#fff" strokeWidth={3} />}
            {item.status === 'running' && <i />}
          </span>
          <span className="w-t">{item.label}</span>
          {item.note && <span className="w-s">{item.note}</span>}
        </li>
      ))}
    </ul>
  );
}
