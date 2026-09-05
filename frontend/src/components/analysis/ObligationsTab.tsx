'use client'

/**
 * Obligations tab — list view of obligations/timeline items with deadline
 * badges and status (10-frontend-spec.md §4; calendar toggle arrives with
 * the Phase 8 reports work).
 */
import { CalendarClock, CircleCheckBig, UserRound } from 'lucide-react'
import type { ObligationListResponse } from '@/lib/api-client'
import { CitationLink } from '@/components/analysis/CitationLink'
import {
    deadlineLabel,
    formatDate,
    obligationStatusMeta,
} from '@/lib/analysis-meta'
import { cn } from '@/lib/cn'

export default function ObligationsTab({
    obligations,
}: {
    obligations: ObligationListResponse
}) {
    if (obligations.items.length === 0) {
        return (
            <div className="card flex items-center gap-3 p-5 text-[13.5px] text-ink-500">
                <CircleCheckBig size={16} className="shrink-0 text-emerald-400" />
                No obligations or timeline items were extracted from this document.
            </div>
        )
    }

    return (
        <ol className="relative space-y-3">
            {/* timeline rail */}
            <span
                aria-hidden
                className="absolute bottom-4 left-[15px] top-4 w-px bg-gradient-to-b from-indigo-200 via-ink-100 to-transparent"
            />
            {obligations.items.map((obligation, i) => {
                const status = obligationStatusMeta(obligation.status)
                return (
                    <li
                        key={obligation.id}
                        className="card relative p-4 pl-12 animate-fade-up"
                        style={{ animationDelay: `${Math.min(i * 60, 300)}ms` }}
                    >
                        <span
                            className={cn(
                                'absolute left-[9px] top-5 flex h-3.5 w-3.5 items-center justify-center rounded-full ring-4 ring-white',
                                obligation.status === 'overdue'
                                    ? 'bg-rose-500'
                                    : obligation.status === 'due_soon'
                                      ? 'bg-amber-500'
                                      : obligation.status === 'completed'
                                        ? 'bg-emerald-500'
                                        : 'bg-indigo-400',
                            )}
                        />
                        <header className="flex flex-wrap items-center gap-2">
                            <span className={cn('pill', status.badge)}>
                                {status.label}
                            </span>
                            <span className="pill bg-ink-50 text-ink-500 ring-1 ring-inset ring-ink-500/10">
                                <CalendarClock size={10.5} />
                                {deadlineLabel(obligation.deadline_type)}
                            </span>
                            {obligation.deadline_date && (
                                <span
                                    className={cn(
                                        'text-[12.5px] font-semibold',
                                        obligation.status === 'overdue'
                                            ? 'text-rose-600'
                                            : 'text-ink-600',
                                    )}
                                >
                                    {formatDate(obligation.deadline_date)}
                                </span>
                            )}
                            <span className="ml-auto flex items-center gap-2">
                                {obligation.page_number != null && (
                                    <CitationLink
                                        pageNumber={obligation.page_number}
                                        highlightText={obligation.description}
                                    />
                                )}
                            </span>
                        </header>
                        <p className="mt-2 text-[13px] leading-relaxed text-ink-700">
                            {obligation.description}
                        </p>
                        <p className="mt-1.5 flex items-center gap-1.5 text-[12px] text-ink-400">
                            <UserRound size={11.5} />
                            Obligated party:{' '}
                            <span className="font-semibold text-ink-600">
                                {obligation.obligated_party}
                            </span>
                        </p>
                    </li>
                )
            })}
        </ol>
    )
}
