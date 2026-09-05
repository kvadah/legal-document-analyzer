'use client'

/**
 * Summary tab — Smart Summary fields, score cards (with breakdown), parties,
 * and a preview of the top risks (10-frontend-spec.md §4).
 */
import {
    CalendarDays,
    Coins,
    FileSignature,
    Landmark,
    ScrollText,
    Users,
    ShieldAlert,
} from 'lucide-react'
import type { RiskOut, ScoreOut, SummaryOut } from '@/lib/api-client'
import ScoreCards from '@/components/analysis/ScoreCards'
import { CitationLink } from '@/components/analysis/CitationLink'
import {
    formatDate,
    formatMoney,
    riskLabel,
    severityMeta,
    severityRank,
} from '@/lib/analysis-meta'
import { cn } from '@/lib/cn'

function Field({
    icon: Icon,
    label,
    children,
}: {
    icon: React.ComponentType<{ size?: number; className?: string }>
    label: string
    children: React.ReactNode
}) {
    return (
        <div className="rounded-xl border border-ink-100 bg-white p-4">
            <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-300">
                <Icon size={12} className="text-indigo-400" />
                {label}
            </p>
            <div className="mt-1.5 text-[13.5px] leading-relaxed text-ink-700">
                {children}
            </div>
        </div>
    )
}

const Dash = () => <span className="text-ink-300">—</span>

export default function SummaryTab({
    summary,
    risks,
    score,
}: {
    summary: SummaryOut
    risks: RiskOut[]
    score: ScoreOut
}) {
    const topRisks = [...risks]
        .sort((a, b) => severityRank(a.severity) - severityRank(b.severity))
        .slice(0, 3)

    return (
        <div className="space-y-4">
            <ScoreCards score={score} />

            {/* Parties */}
            {summary.parties.length > 0 && (
                <div className="card p-5 animate-fade-up">
                    <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-300">
                        <Users size={12} className="text-indigo-400" />
                        Parties
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {summary.parties.map((party, i) => (
                            <span
                                key={`${party.name}-${i}`}
                                className="inline-flex items-center gap-2 rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-1.5 text-[13px] font-semibold text-indigo-800"
                            >
                                {party.name}
                                {party.role && (
                                    <span className="text-[11px] font-medium capitalize text-indigo-500">
                                        {party.role}
                                    </span>
                                )}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Smart summary fields */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field icon={ScrollText} label="Purpose">
                    {summary.purpose ?? <Dash />}
                </Field>
                <Field icon={Landmark} label="Governing law">
                    {summary.governing_law ?? <Dash />}
                </Field>
                <Field icon={CalendarDays} label="Effective → Expiration">
                    {summary.effective_date || summary.expiration_date ? (
                        <span className="flex flex-wrap items-center gap-2">
                            <span>{formatDate(summary.effective_date)}</span>
                            <span className="text-ink-300">→</span>
                            <span>{formatDate(summary.expiration_date)}</span>
                        </span>
                    ) : (
                        <Dash />
                    )}
                </Field>
                <Field icon={CalendarDays} label="Duration">
                    {summary.duration ?? <Dash />}
                </Field>
                <Field icon={Coins} label="Contract value">
                    {summary.contract_value != null ? (
                        <span className="font-display text-[17px] font-semibold text-ink-900">
                            {formatMoney(summary.contract_value, summary.contract_currency)}
                        </span>
                    ) : (
                        <Dash />
                    )}
                </Field>
                <Field icon={Coins} label="Financial terms">
                    {summary.financial_terms ?? <Dash />}
                </Field>
                <div className="sm:col-span-2">
                    <Field icon={FileSignature} label="Termination conditions">
                        {summary.termination_conditions ?? <Dash />}
                    </Field>
                </div>
                <div className="sm:col-span-2">
                    <Field icon={ShieldAlert} label="Key risks (summary)">
                        {summary.key_risks ?? <Dash />}
                    </Field>
                </div>
            </div>

            {/* Top risks preview */}
            {topRisks.length > 0 && (
                <div className="card p-5 animate-fade-up">
                    <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-300">
                        <ShieldAlert size={12} className="text-rose-400" />
                        Top risks preview
                    </p>
                    <ul className="mt-3 space-y-2.5">
                        {topRisks.map(risk => {
                            const sev = severityMeta(risk.severity)
                            return (
                                <li
                                    key={risk.id}
                                    className="flex items-start gap-2.5 text-[13px] leading-relaxed"
                                >
                                    <span
                                        className={cn(
                                            'mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full',
                                            sev.dot,
                                        )}
                                    />
                                    <span className="min-w-0 flex-1 text-ink-700">
                                        <span className="font-semibold text-ink-900">
                                            {riskLabel(risk.risk_type)}
                                        </span>{' '}
                                        — {risk.description}
                                    </span>
                                    {risk.page_number != null && (
                                        <CitationLink
                                            pageNumber={risk.page_number}
                                            highlightText={risk.description}
                                        />
                                    )}
                                </li>
                            )
                        })}
                    </ul>
                </div>
            )}
        </div>
    )
}
