'use client'

/**
 * Contract Score + AI Confidence Score display with a clickable breakdown
 * of risk deductions (10-frontend-spec.md §4, Summary tab).
 */
import { useState } from 'react'
import { ChevronDown, Gauge, ShieldCheck, ShieldAlert } from 'lucide-react'
import type { ScoreOut } from '@/lib/api-client'
import { riskLabel, severityMeta } from '@/lib/analysis-meta'
import { cn } from '@/lib/cn'

export function contractScoreTone(score: number | null | undefined) {
    if (score == null) return { text: 'text-ink-400', stroke: 'stroke-ink-200' }
    if (score >= 80)
        return { text: 'text-emerald-600', stroke: 'stroke-emerald-400' }
    if (score >= 60) return { text: 'text-amber-600', stroke: 'stroke-amber-400' }
    return { text: 'text-rose-600', stroke: 'stroke-rose-400' }
}

function ScoreRing({
    value,
    max,
    label,
    tone,
}: {
    value: number
    max: number
    label: string
    tone: { text: string; stroke: string }
}) {
    const pct = Math.max(0, Math.min(100, (value / max) * 100))
    return (
        <div className="relative flex h-[104px] w-[104px] shrink-0 items-center justify-center">
            <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
                <circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    strokeWidth="9"
                    className="stroke-ink-100"
                />
                <circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    strokeWidth="9"
                    strokeLinecap="round"
                    strokeDasharray={`${(pct / 100) * 264} 264`}
                    className={cn('transition-all duration-700', tone.stroke)}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={cn('font-display text-[26px] font-semibold leading-none', tone.text)}>
                    {Math.round(value)}
                    {max === 1 && <span className="text-[15px]">%</span>}
                </span>
                <span className="mt-1 text-[9.5px] font-bold uppercase tracking-[0.14em] text-ink-300">
                    {label}
                </span>
            </div>
        </div>
    )
}

export default function ScoreCards({ score }: { score: ScoreOut }) {
    const [showBreakdown, setShowBreakdown] = useState(false)

    const contractTone = contractScoreTone(score.contract_score)
    const confidence = score.ai_confidence_score
    const confidenceTone =
        confidence == null
            ? { text: 'text-ink-400', stroke: 'stroke-ink-200' }
            : confidence >= 0.8
              ? { text: 'text-emerald-600', stroke: 'stroke-emerald-400' }
              : confidence >= 0.6
                ? { text: 'text-amber-600', stroke: 'stroke-amber-400' }
                : { text: 'text-rose-600', stroke: 'stroke-rose-400' }

    return (
        <div className="card overflow-hidden animate-fade-up">
            <div className="flex items-stretch divide-x divide-ink-100">
                <div className="flex flex-1 items-center gap-4 p-5">
                    <ScoreRing
                        value={score.contract_score ?? 0}
                        max={100}
                        label="Score"
                        tone={contractTone}
                    />
                    <div className="min-w-0">
                        <p className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-400">
                            <Gauge size={13} className="text-indigo-400" />
                            Contract score
                        </p>
                        <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-500">
                            Starts at 100; deductions applied per risk found.
                        </p>
                        <button
                            type="button"
                            onClick={() => setShowBreakdown(v => !v)}
                            aria-expanded={showBreakdown}
                            className="mt-2 inline-flex items-center gap-1 text-[12px] font-semibold text-indigo-600 transition-colors hover:text-indigo-700"
                        >
                            {showBreakdown ? 'Hide' : 'Show'} breakdown
                            <ChevronDown
                                size={13}
                                className={cn(
                                    'transition-transform duration-200',
                                    showBreakdown && 'rotate-180',
                                )}
                            />
                        </button>
                    </div>
                </div>

                <div className="flex flex-1 items-center gap-4 p-5">
                    <ScoreRing
                        value={(confidence ?? 0) * 100}
                        max={100}
                        label="AI conf."
                        tone={confidenceTone}
                    />
                    <div className="min-w-0">
                        <p className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-400">
                            {confidence != null && confidence < 0.6 ? (
                                <ShieldAlert size={13} className="text-rose-400" />
                            ) : (
                                <ShieldCheck size={13} className="text-emerald-400" />
                            )}
                            AI confidence
                        </p>
                        <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-500">
                            How certain the model is in its extractions
                            (v{score.scores_version}).
                        </p>
                    </div>
                </div>
            </div>

            {/* Breakdown */}
            {showBreakdown && (
                <div className="animate-scale-in border-t border-ink-100 bg-ink-50/60 px-5 py-4">
                    {score.breakdown.length === 0 ? (
                        <p className="text-[13px] text-ink-500">
                            No deductions — no risks were flagged for this document.
                        </p>
                    ) : (
                        <ul className="space-y-1.5">
                            {score.breakdown.map(item => {
                                const sev = severityMeta(item.severity)
                                return (
                                    <li
                                        key={item.risk_id}
                                        className="flex items-center gap-3 text-[13px]"
                                    >
                                        <span className={cn('h-1.5 w-1.5 rounded-full', sev.dot)} />
                                        <span className="min-w-0 flex-1 truncate text-ink-700">
                                            {riskLabel(item.risk_type)}
                                        </span>
                                        <span className={cn('pill', sev.badge)}>{sev.label}</span>
                                        <span className="w-10 text-right font-semibold text-rose-600">
                                            −{item.deduction}
                                        </span>
                                    </li>
                                )
                            })}
                            <li className="mt-2 flex items-center justify-between border-t border-ink-100 pt-2.5 text-[13px] font-semibold text-ink-800">
                                <span>Total deduction</span>
                                <span className="text-rose-600">
                                    −{score.total_deduction} →{' '}
                                    {score.contract_score ?? '—'}
                                </span>
                            </li>
                        </ul>
                    )}
                </div>
            )}
        </div>
    )
}
