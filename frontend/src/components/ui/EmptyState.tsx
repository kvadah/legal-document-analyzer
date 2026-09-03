import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function EmptyState({
    icon: Icon,
    title,
    description,
    action,
    className,
}: {
    icon: LucideIcon
    title: string
    description: string
    action?: ReactNode
    className?: string
}) {
    return (
        <div
            className={cn(
                'relative overflow-hidden rounded-2xl border border-dashed border-ink-200 bg-white/60 px-8 py-16 text-center animate-fade-up',
                className,
            )}
        >
            <div className="bg-grid mask-fade-b pointer-events-none absolute inset-0 opacity-60" />
            <div className="relative">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-b from-indigo-500 to-violet-600 text-white shadow-glow animate-float">
                    <Icon size={26} strokeWidth={1.8} />
                </div>
                <h3 className="mt-6 font-display text-xl font-semibold text-ink-900">{title}</h3>
                <p className="mx-auto mt-2 max-w-md text-[14.5px] leading-relaxed text-ink-500">
                    {description}
                </p>
                {action && <div className="mt-6 flex justify-center">{action}</div>}
            </div>
        </div>
    )
}
