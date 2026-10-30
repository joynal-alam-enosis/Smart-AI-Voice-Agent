import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '../../lib/utils';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

/** Shadcn-inspired panel primitive used for elevated operational content. */
export function Card({ className, children, ...props }: CardProps) {
  return (
    <section className={cn('surface rounded-2xl', className)} {...props}>
      {children}
    </section>
  );
}
