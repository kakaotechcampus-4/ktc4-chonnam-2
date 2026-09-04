import type { JSX } from 'react';

// No internal timer here on purpose — the caller (HandoffScreen, Task 16)
// owns visibility and the 2-second auto-hide, consistent with "timers live
// in screens".
export function Toast(props: { message: string; visible: boolean }): JSX.Element {
  return (
    <div className={`toast${props.visible ? ' visible' : ''}`} role="status" aria-live="polite">
      {props.message}
    </div>
  );
}
