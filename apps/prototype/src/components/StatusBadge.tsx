import type { ComponentType, JSX } from 'react';
import { Bell, CheckCircle, Info } from 'lucide-react';
import type { InfoStatus } from '../types';

interface StatusBadgeSpec {
  className: string;
  label: string;
  Icon: ComponentType<{ size?: number }> | null;
}

// props.status is typed as InfoStatus (never a union that also admits
// WorkStatus) — this is the whole of the "타입 에러가 나도록 union을 좁힌다"
// requirement. WorkStatus and InfoStatus share no string literals, so passing
// a WorkStatus value here is already a compile error with no runtime check
// needed on top of it.
const SPECS: Record<InfoStatus, StatusBadgeSpec> = {
  'source-verified': { className: 'badge-confirmed', label: '출처 확인됨', Icon: CheckCircle },
  'user-confirmed': { className: 'badge-user-confirmed', label: '사용자 확인됨', Icon: CheckCircle },
  'ai-estimated': { className: 'badge-estimated', label: 'AI 추정', Icon: Info },
  'needs-review': { className: 'badge-attention', label: '확인 필요', Icon: Bell },
  unknown: { className: 'badge-unknown', label: '알 수 없음', Icon: null },
};

export function StatusBadge(props: { status: InfoStatus; sm?: boolean }): JSX.Element {
  const spec = SPECS[props.status];
  const { Icon } = spec;
  return (
    <span className={`badge ${spec.className}${props.sm ? ' sm' : ''}`}>
      <span className="dot" />
      {Icon && <Icon size={14} />}
      <span>{spec.label}</span>
    </span>
  );
}
