'use client'

import { useEffect, useMemo, useState } from 'react'
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
import { apiListDocuments, type DocumentOut } from '@/lib/api-client'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { statusMeta } from '@/lib/format'

const STATUS_COLORS: Record<string, string> = {
    Analyzed: '#10B981',
    Ingested: '#94A3B8',
    'In pipeline': '#6366F1',
    Error: '#F43F5E',
}

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

export default function ReportsPage() {
    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        async function load() {
            try {
                const data = await apiListDocuments()
                setDocuments(data.items)
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load documents')
            } finally {
                setLoading(false)
            }
        }
        void load()
    }, [])

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

    const reportCards = [
        {
            icon: ShieldAlert,
            title: 'Portfolio Risk Report',
            description:
                'A consolidated view of every flagged risk, ranked by severity, across all analysed documents.',
            accent: 'from-rose-500 to-orange-400',
            cta: 'Export risk report',
        },
        {
            icon: CalendarClock,
            title: 'Obligation Calendar',
            description:
                'Upcoming payment dates, notice periods, and renewal deadlines extracted from your contracts.',
            accent: 'from-gold-400 to-gold-600',
            cta: 'Export calendar',
        },
    ]

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

                        {/* Report cards */}
                        <div className="grid gap-5 md:grid-cols-2">
                            {reportCards.map((report, i) => (
                                <div
                                    key={report.title}
                                    className="card animate-fade-up group relative overflow-hidden p-7 transition-all duration-300 hover:-translate-y-1 hover:shadow-lift"
                                    style={{ animationDelay: `${200 + i * 100}ms` }}
                                >
                                    <div
                                        className={`pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-gradient-to-br ${report.accent} opacity-[0.08] blur-2xl transition-opacity duration-300 group-hover:opacity-[0.18]`}
                                    />
                                    <div
                                        className={`relative flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-lift ${report.accent}`}
                                    >
                                        <report.icon size={22} strokeWidth={2} />
                                    </div>
                                    <h3 className="mt-5 font-display text-[20px] font-semibold text-ink-900">
                                        {report.title}
                                    </h3>
                                    <p className="mt-2 text-[14px] leading-relaxed text-ink-500">
                                        {report.description}
                                    </p>
                                    <div className="mt-6 flex items-center justify-between">
                                        <button
                                            onClick={() => window.print()}
                                            className="btn-secondary px-4 py-2.5 text-[13px]"
                                        >
                                            <Printer size={14} />
                                            {report.cta}
                                        </button>
                                        <span className="text-[12px] text-ink-400">
                                            {documents.length} documents in scope
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </AppLayout>
    )
}
