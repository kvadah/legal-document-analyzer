'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import {
    Loader2,
    AlertCircle,
    ShieldAlert,
    CalendarClock,
    Printer,
    ArrowRight,
    TrendingUp,
    PieChart as PieIcon,
    Download,
    CheckCircle2,
    XCircle,
    FileDown,
} from 'lucide-react'
import {
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
} from 'recharts'
import AppLayout from '@/app/app-layout'
import { useAuth } from '@/context/AuthContext'
import {
    apiCreateReport,
    apiDownloadReport,
    apiListDocuments,
    apiListReports,
    downloadBlob,
    type DocumentOut,
    type ReportFormat,
    type ReportOut,
    type ReportType,
} from '@/lib/api-client'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { DocumentMultiSelect } from '@/components/ui/DocumentPicker'
import { statusMeta } from '@/lib/format'

const STATUS_COLORS: Record<string, string> = {
    Analyzed: '#10B981',
    Ingested: '#94A3B8',
    'In pipeline': '#6366F1',
    Error: '#F43F5E',
}

const REPORT_FORMATS: ReportFormat[] = ['json', 'xlsx', 'pdf', 'docx']

const REPORT_TYPES: {
    type: ReportType
    icon: typeof ShieldAlert
    title: string
    description: string
    accent: string
}[] = [
    {
        type: 'portfolio_risk',
        icon: ShieldAlert,
        title: 'Portfolio Risk Report',
        description:
            'A consolidated view of every flagged risk, ranked by severity, across the analysed documents — with contract score distribution and critical-risk focus list.',
        accent: 'from-rose-500 to-orange-400',
    },
    {
        type: 'obligation_calendar',
        icon: CalendarClock,
        title: 'Obligation Calendar',
        description:
            'Every payment date, notice period, and renewal deadline across the portfolio, bucketed into overdue, due soon, and upcoming for compliance tracking.',
        accent: 'from-gold-400 to-gold-600',
    },
]

function groupByDay(docs: DocumentOut[]) {
    const byDay = new Map<string, number>()
    for (const doc of docs) {
        const day = new Date(doc.created_at).toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
        })
        byDay.set(day, (byDay.get(day) ?? 0) + 1)
    }
    return Array.from(byDay.entries())
        .slice(-14)
        .map(([day, count]) => ({ day, count }))
}

function ChartTooltip({
    active,
    payload,
    label,
}: {
    active?: boolean
    payload?: { name?: string; value?: number | string }[]
    label?: string
}) {
    if (!active || !payload?.length) return null
    return (
        <div className="rounded-lg border border-ink-100 bg-white px-3.5 py-2.5 shadow-lift">
            {label && (
                <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-ink-400">
                    {label}
                </p>
            )}
            {payload.map((entry, i) => (
                <p key={i} className="text-[13px] font-semibold text-ink-800">
                    {entry.name === 'count' ? 'Documents' : entry.name}:{' '}
                    <span className="text-indigo-600">{entry.value}</span>
                </p>
            ))}
        </div>
    )
}

function reportStatusBadge(status: ReportOut['status']) {
    if (status === 'completed')
        return (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11.5px] font-semibold text-emerald-700">
                <CheckCircle2 size={12} /> Completed
            </span>
        )
    if (status === 'error')
        return (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-[11.5px] font-semibold text-rose-700">
                <XCircle size={12} /> Error
            </span>
        )
    return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-1 text-[11.5px] font-semibold text-indigo-700">
            <Loader2 size={12} className="animate-spin" />
            {status === 'processing' ? 'Processing' : 'Pending'}
        </span>
    )
}

function formatDate(iso: string | null) {
    if (!iso) return '—'
    return new Date(iso).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    })
}

export default function ReportsPage() {
    const { user } = useAuth()
    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    // Report generation + list state
    const [scopeIds, setScopeIds] = useState<string[]>([])
    const [formats, setFormats] = useState<Record<ReportType, ReportFormat>>({
        portfolio_risk: 'xlsx',
        obligation_calendar: 'xlsx',
    })
    const [generating, setGenerating] = useState<ReportType | null>(null)
    const [generateError, setGenerateError] = useState<string | null>(null)
    const [reports, setReports] = useState<ReportOut[] | null>(null)
    const [reportsError, setReportsError] = useState<string | null>(null)
    const [downloading, setDownloading] = useState<string | null>(null)

    const canGenerate = user?.role === 'admin' || user?.role === 'reviewer'
    const mountedRef = useRef(true)

    const refreshReports = useCallback(async () => {
        try {
            const data = await apiListReports()
            if (mountedRef.current) {
                setReports(data.reports)
                setReportsError(null)
            }
        } catch (err) {
            if (mountedRef.current)
                setReportsError(
                    err instanceof Error ? err.message : 'Failed to load reports',
                )
        }
    }, [])

    useEffect(() => {
        mountedRef.current = true
        async function load() {
            try {
                const data = await apiListDocuments()
                if (mountedRef.current) setDocuments(data.items)
            } catch (err) {
                if (mountedRef.current)
                    setError(
                        err instanceof Error ? err.message : 'Failed to load documents',
                    )
            } finally {
                if (mountedRef.current) setLoading(false)
            }
        }
        void load()
        void refreshReports()
        return () => {
            mountedRef.current = false
        }
    }, [refreshReports])

    // Poll while any report is in flight.
    const hasPending = (reports ?? []).some(
        r => r.status === 'pending' || r.status === 'processing',
    )
    useEffect(() => {
        if (!hasPending) return
        const timer = setTimeout(() => void refreshReports(), 2500)
        return () => clearTimeout(timer)
    }, [hasPending, refreshReports, reports])

    const analyzedDocs = useMemo(
        () => documents.filter(doc => doc.status === 'analysis_ready'),
        [documents],
    )

    const statusData = useMemo(() => {
        const buckets: Record<string, number> = {
            Analyzed: 0,
            Ingested: 0,
            'In pipeline': 0,
            Error: 0,
        }
        for (const doc of documents) {
            const meta = statusMeta(doc.status)
            if (doc.status === 'error') buckets.Error++
            else if (doc.status === 'analysis_ready') buckets.Analyzed++
            else if (meta.busy) buckets['In pipeline']++
            else buckets.Ingested++
        }
        return Object.entries(buckets)
            .filter(([, count]) => count > 0)
            .map(([name, value]) => ({ name, value }))
    }, [documents])

    const timeline = useMemo(() => groupByDay(documents), [documents])

    async function handleGenerate(type: ReportType) {
        setGenerating(type)
        setGenerateError(null)
        try {
            await apiCreateReport(type, formats[type], scopeIds)
            await refreshReports()
        } catch (err) {
            setGenerateError(
                err instanceof Error ? err.message : 'Report generation failed',
            )
        } finally {
            setGenerating(null)
        }
    }

    async function handleDownload(report: ReportOut) {
        setDownloading(report.report_id)
        try {
            const { blob, filename } = await apiDownloadReport(report.report_id)
            downloadBlob(blob, filename)
        } catch (err) {
            setReportsError(
                err instanceof Error ? err.message : 'Report download failed',
            )
        } finally {
            setDownloading(null)
        }
    }

    const scopeLabel =
        scopeIds.length === 0
            ? `${analyzedDocs.length} analysed document${analyzedDocs.length === 1 ? '' : 's'}`
            : `${scopeIds.length} selected document${scopeIds.length === 1 ? '' : 's'}`

    return (
        <AppLayout>
            <div className="space-y-6">
                <PageHeader
                    eyebrow="Insights"
                    title="Reports"
                    description="Portfolio-wide analytics, risk summaries, and exportable reports."
                    actions={
                        <button
                            onClick={() => window.print()}
                            className="btn-secondary px-4 py-2.5"
                        >
                            <Printer size={15} />
                            Print / PDF
                        </button>
                    }
                />

                {loading && (
                    <div className="flex items-center justify-center gap-3 py-20 text-[14px] text-ink-400">
                        <Loader2 size={18} className="animate-spin" />
                        Crunching portfolio numbers…
                    </div>
                )}

                {error && (
                    <div className="flex items-center gap-3 rounded-xl border border-rose-200/80 bg-rose-50 px-5 py-4 text-[13.5px] text-rose-700">
                        <AlertCircle size={17} className="shrink-0" />
                        {error}
                    </div>
                )}

                {!loading && !error && documents.length === 0 && (
                    <EmptyState
                        icon={PieIcon}
                        title="Nothing to report yet"
                        description="Once you upload contracts, this page turns into a live dashboard of risk, ingestion, and obligation trends."
                        action={
                            <Link href="/upload" className="btn-primary px-6 py-3">
                                Upload documents
                                <ArrowRight size={15} />
                            </Link>
                        }
                    />
                )}

                {!loading && !error && documents.length > 0 && (
                    <>
                        {/* Charts row */}
                        <div className="grid gap-5 lg:grid-cols-5">
                            {/* Donut */}
                            <div className="card animate-fade-up p-6 lg:col-span-2">
                                <div className="flex items-center gap-2">
                                    <PieIcon size={15} className="text-indigo-500" />
                                    <h2 className="text-[13px] font-bold uppercase tracking-[0.12em] text-ink-500">
                                        Pipeline status
                                    </h2>
                                </div>
                                <div className="mt-2 h-[220px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={statusData}
                                                dataKey="value"
                                                nameKey="name"
                                                innerRadius={58}
                                                outerRadius={84}
                                                paddingAngle={3}
                                                strokeWidth={0}
                                            >
                                                {statusData.map(entry => (
                                                    <Cell
                                                        key={entry.name}
                                                        fill={STATUS_COLORS[entry.name]}
                                                    />
                                                ))}
                                            </Pie>
                                            <Tooltip content={<ChartTooltip />} />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                                <ul className="mt-1 flex flex-wrap justify-center gap-x-4 gap-y-1.5">
                                    {statusData.map(entry => (
                                        <li
                                            key={entry.name}
                                            className="flex items-center gap-1.5 text-[12px] text-ink-500"
                                        >
                                            <span
                                                className="h-2 w-2 rounded-full"
                                                style={{
                                                    background: STATUS_COLORS[entry.name],
                                                }}
                                            />
                                            {entry.name}
                                            <span className="font-semibold text-ink-800">
                                                {entry.value}
                                            </span>
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            {/* Timeline */}
                            <div className="card animate-fade-up animation-delay-100 p-6 lg:col-span-3">
                                <div className="flex items-center gap-2">
                                    <TrendingUp size={15} className="text-indigo-500" />
                                    <h2 className="text-[13px] font-bold uppercase tracking-[0.12em] text-ink-500">
                                        Ingestion activity
                                    </h2>
                                </div>
                                <div className="mt-2 h-[252px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart
                                            data={timeline}
                                            margin={{ top: 12, right: 8, left: -18, bottom: 0 }}
                                        >
                                            <defs>
                                                <linearGradient
                                                    id="timelineFill"
                                                    x1="0"
                                                    y1="0"
                                                    x2="0"
                                                    y2="1"
                                                >
                                                    <stop
                                                        offset="0%"
                                                        stopColor="#6366F1"
                                                        stopOpacity={0.28}
                                                    />
                                                    <stop
                                                        offset="100%"
                                                        stopColor="#6366F1"
                                                        stopOpacity={0.02}
                                                    />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid
                                                strokeDasharray="3 6"
                                                stroke="#E2E8F0"
                                                vertical={false}
                                            />
                                            <XAxis
                                                dataKey="day"
                                                tickLine={false}
                                                axisLine={false}
                                                tick={{ fontSize: 11, fill: '#94A3B8' }}
                                            />
                                            <YAxis
                                                allowDecimals={false}
                                                tickLine={false}
                                                axisLine={false}
                                                tick={{ fontSize: 11, fill: '#94A3B8' }}
                                            />
                                            <Tooltip content={<ChartTooltip />} />
                                            <Area
                                                type="monotone"
                                                dataKey="count"
                                                stroke="#6366F1"
                                                strokeWidth={2.5}
                                                fill="url(#timelineFill)"
                                                activeDot={{
                                                    r: 4,
                                                    fill: '#6366F1',
                                                    stroke: '#fff',
                                                    strokeWidth: 2,
                                                }}
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        {/* Report generation */}
                        <div className="card animate-fade-up p-6">
                            <div className="flex flex-wrap items-center justify-between gap-4">
                                <div>
                                    <h2 className="font-display text-[18px] font-semibold text-ink-900">
                                        Generate a report
                                    </h2>
                                    <p className="mt-1 text-[13.5px] text-ink-500">
                                        Reports are generated as a background job and
                                        appear below when ready.
                                    </p>
                                </div>
                                <div className="w-full max-w-[320px]">
                                    <label className="mb-1.5 block text-[11.5px] font-bold uppercase tracking-wider text-ink-400">
                                        Scope — {scopeLabel}
                                    </label>
                                    <DocumentMultiSelect
                                        documents={analyzedDocs}
                                        selectedIds={scopeIds}
                                        onToggle={id =>
                                            setScopeIds(prev =>
                                                prev.includes(id)
                                                    ? prev.filter(x => x !== id)
                                                    : [...prev, id],
                                            )
                                        }
                                    />
                                </div>
                            </div>

                            {generateError && (
                                <div className="mt-4 flex items-center gap-3 rounded-xl border border-rose-200/80 bg-rose-50 px-4 py-3 text-[13px] text-rose-700">
                                    <AlertCircle size={15} className="shrink-0" />
                                    {generateError}
                                </div>
                            )}

                            <div className="mt-5 grid gap-5 md:grid-cols-2">
                                {REPORT_TYPES.map(report => (
                                    <div
                                        key={report.type}
                                        className="group relative overflow-hidden rounded-2xl border border-ink-100 p-6 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lift"
                                    >
                                        <div
                                            className={`pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-gradient-to-br ${report.accent} opacity-[0.08] blur-2xl transition-opacity duration-300 group-hover:opacity-[0.18]`}
                                        />
                                        <div
                                            className={`relative flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-lift ${report.accent}`}
                                        >
                                            <report.icon size={20} strokeWidth={2} />
                                        </div>
                                        <h3 className="mt-4 font-display text-[18px] font-semibold text-ink-900">
                                            {report.title}
                                        </h3>
                                        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-500">
                                            {report.description}
                                        </p>
                                        <div className="mt-5 flex flex-wrap items-center gap-3">
                                            <select
                                                value={formats[report.type]}
                                                onChange={e =>
                                                    setFormats(prev => ({
                                                        ...prev,
                                                        [report.type]: e.target
                                                            .value as ReportFormat,
                                                    }))
                                                }
                                                disabled={!canGenerate}
                                                className="rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-[13px] font-medium text-ink-700 shadow-soft transition-colors hover:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
                                                aria-label={`Export format for ${report.title}`}
                                            >
                                                {REPORT_FORMATS.map(fmt => (
                                                    <option key={fmt} value={fmt}>
                                                        {fmt.toUpperCase()}
                                                        {fmt === 'xlsx' ? ' (Excel)' : ''}
                                                    </option>
                                                ))}
                                            </select>
                                            <button
                                                onClick={() => handleGenerate(report.type)}
                                                disabled={
                                                    !canGenerate ||
                                                    generating === report.type ||
                                                    analyzedDocs.length === 0
                                                }
                                                className="btn-primary px-4 py-2.5 text-[13px] disabled:cursor-not-allowed disabled:opacity-50"
                                            >
                                                {generating === report.type ? (
                                                    <>
                                                        <Loader2
                                                            size={14}
                                                            className="animate-spin"
                                                        />
                                                        Generating…
                                                    </>
                                                ) : (
                                                    <>
                                                        <FileDown size={14} />
                                                        Generate
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                        {!canGenerate && (
                                            <p className="mt-3 text-[12px] text-ink-400">
                                                Your role can view reports but not generate
                                                them — ask a reviewer or admin.
                                            </p>
                                        )}
                                        {canGenerate && analyzedDocs.length === 0 && (
                                            <p className="mt-3 text-[12px] text-ink-400">
                                                No analysed documents yet — reports need
                                                completed analysis to aggregate.
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Past reports */}
                        <div className="card animate-fade-up p-6">
                            <div className="flex items-center justify-between">
                                <h2 className="font-display text-[18px] font-semibold text-ink-900">
                                    Generated reports
                                </h2>
                                {reports && reports.length > 0 && (
                                    <span className="text-[12px] text-ink-400">
                                        {reports.length} total
                                    </span>
                                )}
                            </div>

                            {reportsError && (
                                <div className="mt-4 flex items-center gap-3 rounded-xl border border-rose-200/80 bg-rose-50 px-4 py-3 text-[13px] text-rose-700">
                                    <AlertCircle size={15} className="shrink-0" />
                                    {reportsError}
                                </div>
                            )}

                            {reports === null && !reportsError && (
                                <div className="flex items-center justify-center gap-3 py-10 text-[13px] text-ink-400">
                                    <Loader2 size={15} className="animate-spin" />
                                    Loading reports…
                                </div>
                            )}

                            {reports !== null && reports.length === 0 && (
                                <div className="py-10 text-center text-[13px] text-ink-400">
                                    No reports generated yet — pick a report type above to
                                    create the first one.
                                </div>
                            )}

                            {reports !== null && reports.length > 0 && (
                                <div className="mt-4 overflow-x-auto">
                                    <table className="w-full min-w-[640px] text-left">
                                        <thead>
                                            <tr className="border-b border-ink-100 text-[11px] font-bold uppercase tracking-wider text-ink-400">
                                                <th className="pb-2.5 pr-4">Report</th>
                                                <th className="pb-2.5 pr-4">Format</th>
                                                <th className="pb-2.5 pr-4">Status</th>
                                                <th className="pb-2.5 pr-4">Created</th>
                                                <th className="pb-2.5 text-right">Action</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {reports.map(report => (
                                                <tr
                                                    key={report.report_id}
                                                    className="border-b border-ink-50 last:border-0"
                                                >
                                                    <td className="py-3 pr-4">
                                                        <span className="text-[13.5px] font-semibold text-ink-800">
                                                            {report.report_type ===
                                                            'portfolio_risk'
                                                                ? 'Portfolio Risk'
                                                                : 'Obligation Calendar'}
                                                        </span>
                                                        <span className="ml-2 text-[11.5px] text-ink-400">
                                                            {report.document_ids
                                                                ? `${report.document_ids.length} doc${report.document_ids.length === 1 ? '' : 's'}`
                                                                : 'all docs'}
                                                        </span>
                                                        {report.error && (
                                                            <p className="mt-1 max-w-[360px] truncate text-[11.5px] text-rose-600">
                                                                {report.error}
                                                            </p>
                                                        )}
                                                    </td>
                                                    <td className="py-3 pr-4 text-[12px] font-semibold uppercase text-ink-500">
                                                        {report.export_format}
                                                    </td>
                                                    <td className="py-3 pr-4">
                                                        {reportStatusBadge(report.status)}
                                                    </td>
                                                    <td className="py-3 pr-4 text-[12.5px] text-ink-500">
                                                        {formatDate(report.created_at)}
                                                    </td>
                                                    <td className="py-3 text-right">
                                                        {report.status === 'completed' ? (
                                                            <button
                                                                onClick={() =>
                                                                    handleDownload(report)
                                                                }
                                                                disabled={
                                                                    downloading ===
                                                                    report.report_id
                                                                }
                                                                className="btn-secondary px-3.5 py-2 text-[12.5px]"
                                                            >
                                                                {downloading ===
                                                                report.report_id ? (
                                                                    <Loader2
                                                                        size={13}
                                                                        className="animate-spin"
                                                                    />
                                                                ) : (
                                                                    <Download size={13} />
                                                                )}
                                                                Download
                                                            </button>
                                                        ) : (
                                                            <span className="text-[12px] text-ink-300">
                                                                —
                                                            </span>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>
        </AppLayout>
    )
}
