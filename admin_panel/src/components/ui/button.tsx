import type { ButtonHTMLAttributes, ReactNode } from 'react';

import { cn } from '../../lib/utils';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children: ReactNode;
}

/** Shadcn-inspired button primitive with accessible focus and disabled states. */
export function Button({ className, variant = 'primary', type = 'button', children, ...props }: ButtonProps) {
  const variants: Record<ButtonVariant, string> = {
    primary: 'bg-indigo-500 text-white shadow-lg shadow-indigo-950/40 hover:bg-indigo-400',
    secondary: 'border border-slate-700 bg-slate-800/80 text-slate-100 hover:border-slate-600 hover:bg-slate-700',
    ghost: 'text-slate-400 hover:bg-slate-800 hover:text-white',
    danger: 'bg-rose-500 text-white hover:bg-rose-400',
  };
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
