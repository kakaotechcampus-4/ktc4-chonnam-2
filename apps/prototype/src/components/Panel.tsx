import type { JSX, ReactNode } from 'react';

export function Panel(props: { title?: string; children: ReactNode; className?: string }): JSX.Element {
  const className = ['panel', 'panel-p', props.className].filter(Boolean).join(' ');
  return (
    <div className={className}>
      {props.title && <h3 className="panel-title">{props.title}</h3>}
      {props.children}
    </div>
  );
}
