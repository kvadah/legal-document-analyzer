'use client'

/**
 * Risks tab — severity-sorted risk cards with a triage status control
 * (flagged / acknowledged / dismissed). Updates are optimistic with
 * rollback on failure (10-frontend-spec.md §4 & §9).
 */
import { useState } from 'react'
import { AlertTriangle, Lightbulb, Loader2, ShieldAlert } from 'lucide-react'
import {
    apiUpdateRiskStatus,
    type DocumentOut,
    type RiskListResponse,
    type RiskOut,
    type RiskTriageStatus,
} from '@/lib/api-client'
import { CitationLink } from '@/components/analysis/CitationLink'
import {
    formatConfidence,
    riskLabel,
    RISK_TRIAGE_META,
    severityMeta,
    severityRank,
} from '@/lib/analysis-meta'
import { cn } from '@/lib/cn'

const TRIAGE_ORDER: RiskTriageStatus[] = ['flagged', 'acknowledged', 'dismissed']

function RiskCard({
    risk,
    documentId,
    onStatusChange,
    index,
}: {
    risk: RiskOut
    documentId: string
    onStatusChange: (riskId: string, status: RiskTriageStatus) => Promise<void>
    index: number
}) {
    const [pending, setPending] = useState<RiskTriageStatus | null>(null)
    const sev = severityMeta(risk.severity)

    async function handleTriage(status: RiskTriageStatus) {
        if (status === risk.status || pending) return
        setPending(status)
        try {
            await onStatusChange(risk.id, status)
        } finally {
            setPending(null)
        }
    }

    return (
        <article
            className="card relative overflow-hidden p-4 animate-fade-up"
            style={{ animationDelay: `${Math.min(index * 60, 300)}ms` }}
        >
            <span className={cn('absolute inset-y-0 left-0 w-1', sev.bar)} />

            <header className="flex flex-wrap items-center gap-2 pl-2">
                <span className={cn('pill', sev.badge)}>
                    <span className={cn('status-dot', sev.dot)} />
                    {sev.label}
                </span>
                <h3 className="text-[14px] font-bold text-ink-900">
                    {riskLabel(risk.risk_type)}
                </h3>
                {risk.confidence_score != null && (
                    <span className="pill bg-ink-50 text-ink-500 ring-1 ring-inset ring-ink-500/10">
                        {formatConfidence(risk.confidence_score)} confidence
                    </span>
                )}
                {risk.page_number != null && (
                    <CitationLink
                        pageNumber={risk.page_number}
                        highlightText={risk.description}
                        className="ml-auto"
                    />
                )}
            </header>

            <p className="mt-2.5 pl-2 text-[13px] leading-relaxed text-ink-700">
                {risk.description}
            </p>

            {risk.recommendation && (
                <p className="mt-2 flex items-start gap-2 rounded-lg bg-amber-50/70 px-3 py-2.5 pl-2 text-[12.5px] leading-relaxed text-amber-900">
                    <Lightbulb size={14} className="mt-0.5 shrink-0 text-amber-500" />
                    <span>
                        <span className="font-semibold">Recommendation:</span>{' '}
                        {risk.recommendation}
                    </span>
                </p>
            )}

            {/* Triage control */}
            <div
                className="mt-3 flex items-center gap-1.5 pl-2"
                role="group"
                aria-label={`Triage status for ${riskLabel(risk.risk_type)}`}
            >
                {TRIAGE_ORDER.map(status => {
                    const meta = RISK_TRIAGE_META[status]
                    const isActive = risk.status === status
                    return (
                        <button
                            key={status}
                            type="button"
                            disabled={pending !== null}
                            onClick={() => void handleTriage(status)}
                            aria-pressed={isActive}
                            className={cn(
                                'rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-all duration-200 active:scale-[0.97] disabled:opacity-60',
                                isActive
                                    ? meta.active
                                    : 'border border-ink-100 bg-white text-ink-500 hover:border-ink-200 hover:text-ink-700',
                            )}
                        >
                            {pending === status && (
                                <Loader2 size={11.5} className="mr-1 inline animate-spin" />
                            )}
                            {meta.label}
                        </button>
                    )
                })}
            </div>
        </article>
    )
}

export default function RisksTab({
    risks,
    document,
}: {
    risks: RiskListResponse
    document: DocumentOut
}) {
    const [items, setItems] = useState<RiskOut[]>(risks.items)
    const [syncError, setSyncError] = useState<string | null>(null)

    // Keep local state in sync if the parent refetches
    const [lastTotal, setLastTotal] = useState(risks.total)
    if (risks.total !== lastTotal) {
        setLastTotal(risks.total)
        setItems(risks.items)
    }

    async function updateStatus(riskId: string, status: RiskTriageStatus) {
        const previous = items
        // Optimistic update
        setItems(prev =>
            prev.map(r => (r.id === riskId ? { ...r, status } : r)),
        )
        setSyncError(null)
        try {
            const updated = await apiUpdateRiskStatus(document.id, riskId, status)
            setItems(prev =>
                prev.map(r => (r.id === riskId ? { ...r, status: updated.status } : r)),
            )
        } catch (err) {
            // Rollback
            setItems(previous)
            setSyncError(
                err instanceof Error
                    ? `Could not save triage status: ${err.message}`
                    : 'Could not save triage status',
            )
        }
    }

    const sorted = [...items].sort(
        (a, b) => severityRank(a.severity) - severityRank(b.severity),
    )

    return (
        <div className="space-y-3">
            {syncError && (
                <div
                    className="flex items-center gap-2.5 rounded-xl border border-rose-200/80 bg-rose-50 px-4 py-3 text-[13px] text-rose-700"
                    role="alert"
                >
                    <AlertTriangle size={15} className="shrink-0" />
                    {syncError}
                </div>
            )}

            {sorted.length === 0 ? (
                <div className="card flex items-center gap-3 p-5 text-[13.5px] text-ink-500">
                    <ShieldAlert size={16} className="shrink-0 text-emerald-400" />
                    No risks were flagged for this document.
                </div>
            ) : (
                sorted.map((risk, i) => (
                    <RiskCard
                        key={risk.id}
                        risk={risk}
                        documentId={document.id}
                        onStatusChange={updateStatus}
                        index={i}
                    />
                ))
            )}
        </div>
    )
}
