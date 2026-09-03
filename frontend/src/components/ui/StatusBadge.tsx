import { statusMeta, type StatusTone } from '@/lib/format'
import { cn } from '@/lib/cn'

const TONE_STYLES: Record<StatusTone, string> = {
    success: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/15',
    processing: 'bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-600/15',
    error: 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/15',
    neutral: 'bg-ink-100 text-ink-600 ring-1 ring-inset ring-ink-500/10',
}

const TONE_DOTS: Record<StatusTone, string> = {
    success: 'bg-emerald-500',
    processing: 'bg-indigo-500',
    error: 'bg-rose-500',
    neutral: 'bg-ink-400',
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
    const meta = statusMeta(status)
    return (
        <span className={cn('pill', TONE_STYLES[meta.tone], className)}>
            <span
                className={cn(
                    'status-dot',
                    TONE_DOTS[meta.tone],
                    meta.busy && 'status-dot-pulse',
                )}
            />
            {meta.label}
        </span>
    )
}
