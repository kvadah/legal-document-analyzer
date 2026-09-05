'use client'

/**
 * Clauses tab — cards per detected clause type with confidence, summary,
 * extracted text (expandable) and a citation jump; plus a "Not found"
 * section listing absent clause types (10-frontend-spec.md §4).
 */
import { useState } from 'react'
import { ChevronDown, FileCheck2, SearchX, ShieldQuestion } from 'lucide-react'
import type { ClauseListResponse } from '@/lib/api-client'
import { CitationLink } from '@/components/analysis/CitationLink'
import { clauseLabel, formatConfidence } from '@/lib/analysis-meta'
import { cn } from '@/lib/cn'

function confidencePill(score: number | null | undefined) {
    if (score == null) return 'bg-ink-100 text-ink-500 ring-1 ring-inset ring-ink-500/10'
    if (score >= 0.8) return 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/15'
    if (score >= 0.6) return 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20'
    return 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/20'
}

function ClauseCard({
    clause,
    index,
}: {
    clause: ClauseListResponse['items'][number]
    index: number
}) {
    const [expanded, setExpanded] = useState(false)
    const isLong = clause.extracted_text.length > 260
    const text = expanded
        ? clause.extracted_text
        : clause.extracted_text.slice(0, 260)

    return (
        <article
            className="card group p-4 animate-fade-up"
            style={{ animationDelay: `${Math.min(index * 60, 300)}ms` }}
        >
            <header className="flex flex-wrap items-center gap-2">
                <h3 className="text-[14px] font-bold text-ink-900">
                    {clauseLabel(clause.clause_type)}
                </h3>
                <span className={cn('pill', confidencePill(clause.confidence_score))}>
                    <ShieldQuestion size={10.5} />
                    {formatConfidence(clause.confidence_score)}
                </span>
                {clause.page_number != null && (
                    <CitationLink
                        pageNumber={clause.page_number}
                        highlightText={clause.extracted_text}
                        className="ml-auto"
                    />
                )}
            </header>

            {clause.summary && (
                <p className="mt-2 text-[13px] leading-relaxed text-ink-600">
                    {clause.summary}
                </p>
            )}

            <blockquote className="mt-2.5 rounded-lg border-l-2 border-indigo-200 bg-indigo-50/40 px-3.5 py-2.5 text-[12.5px] leading-relaxed text-ink-600">
                “{text}
                {isLong && !expanded && '…’'}
                {!isLong && '’'}
                {isLong && expanded && '’'}
                {isLong && (
                    <button
                        type="button"
                        onClick={() => setExpanded(v => !v)}
                        className="ml-1.5 font-semibold text-indigo-600 transition-colors hover:text-indigo-700"
                    >
                        {expanded ? 'Show less' : 'Show more'}
                    </button>
                )}
            </blockquote>
        </article>
    )
}

export default function ClausesTab({ clauses }: { clauses: ClauseListResponse }) {
    return (
        <div className="space-y-4">
            {clauses.items.length === 0 && clauses.not_found.length > 0 && (
                <div className="card flex items-center gap-3 p-5 text-[13.5px] text-ink-500">
                    <SearchX size={16} className="shrink-0 text-ink-300" />
                    No clauses were detected in this document.
                </div>
            )}

            <div className="space-y-3">
                {clauses.items.map((clause, i) => (
                    <ClauseCard key={clause.id} clause={clause} index={i} />
                ))}
            </div>

            {clauses.not_found.length > 0 && (
                <section className="card p-5 animate-fade-up">
                    <h3 className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-300">
                        <ChevronDown size={12} className="text-ink-300" />
                        Not found ({clauses.not_found.length})
                    </h3>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {clauses.not_found.map(type => (
                            <span
                                key={type}
                                className="pill bg-ink-50 text-ink-400 ring-1 ring-inset ring-ink-200"
                                title={`No ${clauseLabel(type)} clause was detected`}
                            >
                                <FileCheck2 size={10.5} className="opacity-50" />
                                {clauseLabel(type)}
                            </span>
                        ))}
                    </div>
                    <p className="mt-3 text-[12px] leading-relaxed text-ink-400">
                        These standard clause types were not detected. Their absence may
                        itself be a risk — check the Risks tab.
                    </p>
                </section>
            )}
        </div>
    )
}
