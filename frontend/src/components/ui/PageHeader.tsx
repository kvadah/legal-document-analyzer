import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function PageHeader({
    eyebrow,
    title,
    description,
    actions,
    className,
}: {
    eyebrow?: string
    title: string
    description?: string
    actions?: ReactNode
    className?: string
}) {
    return (
        <div
            className={cn(
                'flex flex-wrap items-end justify-between gap-4 animate-fade-up',
                className,
            )}
        >
            <div className="min-w-0">
                {eyebrow && (
                    <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.18em] text-primary/70">
                        {eyebrow}
                    </p>
                )}
                <h1 className="font-display text-[32px] font-semibold leading-tight tracking-tight text-ink-900">
                    {title}
                </h1>
                {description && (
                    <p className="mt-1.5 max-w-2xl text-[15px] text-ink-500">{description}</p>
                )}
            </div>
            {actions && <div className="flex shrink-0 items-center gap-3">{actions}</div>}
        </div>
    )
}
