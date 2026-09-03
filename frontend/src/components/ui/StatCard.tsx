import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/cn'

export function StatCard({
    icon: Icon,
    label,
    value,
    hint,
    iconClass,
    className,
}: {
    icon: LucideIcon
    label: string
    value: React.ReactNode
    hint?: string
    iconClass?: string
    className?: string
}) {
    return (
        <div
            className={cn(
                'card group relative overflow-hidden p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lift animate-fade-up',
                className,
            )}
        >
            <div className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br from-indigo-500/8 to-fuchsia-500/8 blur-xl transition-opacity duration-300 group-hover:from-indigo-500/15" />
            <div className="flex items-center justify-between">
                <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-400">
                    {label}
                </p>
                <div
                    className={cn(
                        'flex h-9 w-9 items-center justify-center rounded-lg ring-1 ring-inset',
                        iconClass ?? 'bg-indigo-50 text-indigo-600 ring-indigo-100',
                    )}
                >
                    <Icon size={17} strokeWidth={2.2} />
                </div>
            </div>
            <p className="mt-2 font-display text-[30px] font-semibold leading-none tracking-tight text-ink-900">
                {value}
            </p>
            {hint && <p className="mt-2 text-[12.5px] text-ink-400">{hint}</p>}
        </div>
    )
}
