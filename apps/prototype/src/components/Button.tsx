import type { JSX, ReactNode } from 'react';

const VARIANT_CLASS: Record<'default' | 'primary' | 'blue' | 'red' | 'orange', string> = {
  default: '',
  primary: 'btn-primary',
  blue: 'btn-blue',
  red: 'btn-red',
  orange: 'btn-orange',
};

export function Button(props: {
  variant?: 'default' | 'primary' | 'blue' | 'red' | 'orange';
  size?: 'default' | 'large';
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
}): JSX.Element {
  const variantClass = VARIANT_CLASS[props.variant ?? 'default'];
  const sizeClass = props.size === 'large' ? 'btn-lg' : '';
  const className = ['btn', variantClass, sizeClass].filter(Boolean).join(' ');
  return (
    <button type="button" className={className} disabled={props.disabled} onClick={props.onClick}>
      {props.children}
    </button>
  );
}
