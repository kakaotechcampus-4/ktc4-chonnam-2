import type { JSX, ReactNode } from 'react';

export function SecLabel(props: { children: ReactNode }): JSX.Element {
  return <div className="sec-label">{props.children}</div>;
}
