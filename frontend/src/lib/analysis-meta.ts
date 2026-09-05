/**
 * Shared labels, ordering and formatting for AI analysis output.
 * Single source of truth so raw enum values never leak into the UI.
 */

function titleCase(value: string): string {
    return value
        .replace(/_/g, ' ')
        .replace(/\b\w/g, ch => ch.toUpperCase())
}

// ── Clause types ─────────────────────────────────────────────────────────────

export const CLAUSE_LABELS: Record<string, string> = {
    termination: 'Termination',
    confidentiality: 'Confidentiality',
    indemnification: 'Indemnification',
    liability: 'Liability',
    arbitration: 'Arbitration',
    payment: 'Payment',
    ip: 'Intellectual Property',
    jurisdiction: 'Jurisdiction',
    renewal: 'Renewal',
    force_majeure: 'Force Majeure',
}

export function clauseLabel(type: string): string {
    return CLAUSE_LABELS[type] ?? titleCase(type)
}

// ── Risk types ───────────────────────────────────────────────────────────────

export const RISK_LABELS: Record<string, string> = {
    unlimited_liability: 'Unlimited liability',
    missing_nda: 'Missing NDA clause',
    missing_termination: 'Missing termination clause',
    ambiguous_language: 'Ambiguous language',
    no_governing_law: 'No governing law',
    auto_renewal: 'Automatic renewal',
    high_penalty: 'High penalty',
    other: 'Other risk',
}

export function riskLabel(type: string): string {
    return RISK_LABELS[type] ?? titleCase(type)
}

// ── Severity ─────────────────────────────────────────────────────────────────

export const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'] as const

export interface SeverityMeta {
    label: string
    badge: string
    dot: string
    bar: string
}

const SEVERITY_META: Record<string, SeverityMeta> = {
    critical: {
        label: 'Critical',
        badge: 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/20',
        dot: 'bg-rose-500',
        bar: 'bg-rose-500',
    },
    high: {
        label: 'High',
        badge: 'bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/20',
        dot: 'bg-orange-500',
        bar: 'bg-orange-500',
    },
    medium: {
        label: 'Medium',
        badge: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20',
        dot: 'bg-amber-500',
        bar: 'bg-amber-400',
    },
    low: {
        label: 'Low',
        badge: 'bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-600/20',
        dot: 'bg-sky-500',
        bar: 'bg-sky-400',
    },
}

export function severityMeta(severity: string): SeverityMeta {
    return SEVERITY_META[severity] ?? SEVERITY_META.low
}

export function severityRank(severity: string): number {
    const idx = SEVERITY_ORDER.indexOf(severity as (typeof SEVERITY_ORDER)[number])
    return idx === -1 ? SEVERITY_ORDER.length : idx
}

// ── Risk triage status ───────────────────────────────────────────────────────

export const RISK_TRIAGE_META: Record<
    string,
    { label: string; active: string }
> = {
    flagged: {
        label: 'Flagged',
        active: 'bg-rose-600 text-white shadow-[0_6px_16px_-6px_rgba(225,29,72,0.6)]',
    },
    acknowledged: {
        label: 'Acknowledged',
        active: 'bg-emerald-600 text-white shadow-[0_6px_16px_-6px_rgba(5,150,105,0.6)]',
    },
    dismissed: {
        label: 'Dismissed',
        active: 'bg-ink-500 text-white shadow-soft',
    },
}

// ── Entities ─────────────────────────────────────────────────────────────────

export const ENTITY_LABELS: Record<string, string> = {
    company: 'Companies',
    person: 'People',
    money: 'Amounts',
    date: 'Dates',
    address: 'Addresses',
    law_reference: 'Law references',
}

export function entityGroupLabel(type: string): string {
    return ENTITY_LABELS[type] ?? titleCase(type)
}

// ── Obligations ──────────────────────────────────────────────────────────────

export const DEADLINE_LABELS: Record<string, string> = {
    effective_date: 'Effective date',
    payment_date: 'Payment date',
    renewal_date: 'Renewal date',
    notice_period: 'Notice period',
    expiration_date: 'Expiration date',
    other: 'Other deadline',
}

export function deadlineLabel(type: string): string {
    return DEADLINE_LABELS[type] ?? titleCase(type)
}

export const OBLIGATION_STATUS_META: Record<
    string,
    { label: string; badge: string }
> = {
    upcoming: {
        label: 'Upcoming',
        badge: 'bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-600/15',
    },
    due_soon: {
        label: 'Due soon',
        badge: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20',
    },
    overdue: {
        label: 'Overdue',
        badge: 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/20',
    },
    completed: {
        label: 'Completed',
        badge: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/15',
    },
}

export function obligationStatusMeta(status: string) {
    return OBLIGATION_STATUS_META[status] ?? { label: titleCase(status), badge: 'bg-ink-100 text-ink-600 ring-1 ring-inset ring-ink-500/10' }
}

// ── Formatting ───────────────────────────────────────────────────────────────

export function formatConfidence(value: number | null | undefined): string {
    if (value == null) return '—'
    return `${Math.round(value * 100)}%`
}

export function formatMoney(
    value: number | null | undefined,
    currency?: string | null,
): string {
    if (value == null) return '—'
    try {
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency: currency ?? 'USD',
            maximumFractionDigits: 2,
        }).format(value)
    } catch {
        return `${currency ?? ''} ${value.toLocaleString()}`
    }
}

export function formatDate(iso: string | null | undefined): string {
    if (!iso) return '—'
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return '—'
    return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    })
}
