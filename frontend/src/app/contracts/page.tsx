'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
    FileStack,
    FileCheck2,
    Loader,
    ShieldAlert,
    Plus,
    Search,
    RefreshCw,
    AlertCircle,
    UploadCloud,
    ChevronRight,
} from 'lucide-react'
import AppLayout from '@/app/app-layout'
import { apiListDocuments, type DocumentOut } from '@/lib/api-client'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatCard } from '@/components/ui/StatCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { docTypeMeta, formatBytes, statusMeta, timeAgo } from '@/lib/format'
import { cn } from '@/lib/cn'

function TableSkeleton() {
    return (
        <div className="card overflow-hidden">
            <div className="space-y-4 p-5">
                {[0, 1, 2, 3, 4].map(i => (
                    <div key={i} className="flex items-center gap-4">
                        <div className="skeleton h-10 w-10 rounded-lg" />
                        <div className="flex-1 space-y-2">
                            <div className="skeleton h-3.5 w-1/3" />
                            <div className="skeleton h-3 w-1/5" />
                        </div>
                        <div className="skeleton h-6 w-20 rounded-full" />
                        <div className="skeleton hidden h-3 w-16 md:block" />
                    </div>
                ))}
            </div>
        </div>
    )
}

export default function ContractsPage() {
    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [query, setQuery] = useState('')
    const [typeFilter, setTypeFilter] = useState('all')
    const [refreshing, setRefreshing] = useState(false)

    const load = useCallback(async (silent = false) => {
        if (!silent) setRefreshing(true)
        try {
            const data = await apiListDocuments()
            setDocuments(data.items)
            setError(null)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load documents')
        } finally {
            setLoading(false)
            setRefreshing(false)
        }
    }, [])

    useEffect(() => {
        void load()
    }, [load])

    // Poll while any document is mid-pipeline so statuses stay live
    const hasBusy = documents.some(d => statusMeta(d.status).busy)
    useEffect(() => {
        if (!hasBusy) return
        const id = setInterval(() => void load(true), 8000)
        return () => clearInterval(id)
    }, [hasBusy, load])

    const typeOptions = useMemo(() => {
        const types = new Set(documents.map(d => d.document_type))
        return Array.from(types)
    }, [documents])

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase()
        return documents.filter(doc => {
            if (typeFilter !== 'all' && doc.document_type !== typeFilter) return false
            if (!q) return true
            return (
                doc.filename.toLowerCase().includes(q) ||
                doc.document_type.toLowerCase().includes(q) ||
                doc.status.toLowerCase().includes(q)
            )
        })
    }, [documents, query, typeFilter])

    const stats = useMemo(
        () => ({
            total: documents.length,
            analyzed: documents.filter(d => d.status === 'analysis_ready').length,
            processing: documents.filter(d => statusMeta(d.status).busy).length,
            errored: documents.filter(d => d.status === 'error').length,
        }),
        [documents],
    )

    return (
        <AppLayout>
            <div className="space-y-6">
                <PageHeader
                    eyebrow="Portfolio"
                    title="Contracts"
                    description="Every document, its pipeline status, and analysis results — in one view."
                    actions={
                        <>
                            <button
                                onClick={() => void load()}
                                className="btn-secondary px-3.5 py-2.5"
                                aria-label="Refresh"
                                disabled={refreshing}
                            >
                                <RefreshCw
                                    size={15}
                                    className={cn(refreshing && 'animate-spin')}
                                />
                                Refresh
                            </button>
                            <Link href="/upload" className="btn-primary px-4 py-2.5">
                                <Plus size={16} />
                                Upload document
                            </Link>
                        </>
                    }
                />

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
                    <StatCard
                        icon={FileStack}
                        label="Total documents"
                        value={stats.total}
                        hint="across your organisation"
                        iconClass="bg-ink-100 text-ink-600 ring-ink-200"
                    />
                    <StatCard
                        icon={FileCheck2}
                        label="Analyzed"
                        value={stats.analyzed}
                        hint="full AI analysis complete"
                        iconClass="bg-emerald-50 text-emerald-600 ring-emerald-100"
                        className="animation-delay-100"
                    />
                    <StatCard
                        icon={Loader}
                        label="In pipeline"
                        value={stats.processing}
                        hint={stats.processing > 0 ? 'updating live' : 'nothing queued'}
                        iconClass="bg-indigo-50 text-indigo-600 ring-indigo-100"
                        className="animation-delay-200"
                    />
                    <StatCard
                        icon={ShieldAlert}
                        label="Errors"
                        value={stats.errored}
                        hint={stats.errored > 0 ? 'need attention' : 'all clear'}
                        iconClass="bg-rose-50 text-rose-600 ring-rose-100"
                        className="animation-delay-300"
                    />
                </div>

                {/* Error banner */}
                {error && (
                    <div className="animate-scale-in flex items-center gap-3 rounded-xl border border-rose-200/80 bg-rose-50 px-5 py-4 text-[13.5px] text-rose-700">
                        <AlertCircle size={17} className="shrink-0" />
                        {error}
                        <button
                            onClick={() => void load()}
                            className="ml-auto font-semibold underline-offset-2 hover:underline"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {/* Loading skeleton */}
                {loading && <TableSkeleton />}

                {/* Empty state */}
                {!loading && !error && documents.length === 0 && (
                    <EmptyState
                        icon={UploadCloud}
                        title="Your portfolio is empty"
                        description="Upload your first contract to unlock clause extraction, risk scoring, and obligation tracking."
                        action={
                            <Link href="/upload" className="btn-primary px-6 py-3">
                                <Plus size={16} />
                                Upload your first document
                            </Link>
                        }
                    />
                )}

                {/* Table */}
                {!loading && documents.length > 0 && (
                    <div className="animate-fade-up animation-delay-200 space-y-4">
                        {/* Filter toolbar */}
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                            <div className="relative flex-1 sm:max-w-xs">
                                <Search
                                    size={15}
                                    className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-300"
                                />
                                <input
                                    type="text"
                                    value={query}
                                    onChange={e => setQuery(e.target.value)}
                                    placeholder="Filter by name, type, or status…"
                                    className="field py-2 pl-10 text-sm"
                                />
                            </div>
                            <div className="relative">
                                <select
                                    value={typeFilter}
                                    onChange={e => setTypeFilter(e.target.value)}
                                    className="field appearance-none py-2 pl-4 pr-10 text-sm"
                                    aria-label="Filter by document type"
                                >
                                    <option value="all">All types</option>
                                    {typeOptions.map(type => (
                                        <option key={type} value={type}>
                                            {docTypeMeta(type).label}
                                        </option>
                                    ))}
                                </select>
                                <ChevronRight
                                    size={14}
                                    className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 rotate-90 text-ink-300"
                                />
                            </div>
                            <p className="text-[12.5px] text-ink-400 sm:ml-auto">
                                {filtered.length} of {documents.length} documents
                            </p>
                        </div>

                        {/* Rows */}
                        <div className="card overflow-hidden">
                            <div className="hidden grid-cols-[minmax(0,2.6fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-4 border-b border-ink-100 bg-ink-50/60 px-6 py-3 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-400 md:grid">
                                <span>Document</span>
                                <span>Type</span>
                                <span>Status</span>
                                <span className="text-right">Uploaded</span>
                            </div>
                            <ul className="divide-y divide-ink-50">
                                {filtered.map(doc => {
                                    const type = docTypeMeta(doc.document_type)
                                    return (
                                        <li
                                            key={doc.id}
                                            className="group grid cursor-default grid-cols-1 gap-3 px-6 py-4 transition-colors hover:bg-indigo-50/30 md:grid-cols-[minmax(0,2.6fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-center md:gap-4"
                                        >
                                            {/* Document */}
                                            <div className="flex min-w-0 items-center gap-3.5">
                                                <span
                                                    className={cn(
                                                        'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold ring-1 ring-inset',
                                                        type.tile,
                                                    )}
                                                >
                                                    {type.glyph}
                                                </span>
                                                <div className="min-w-0">
                                                    <p className="truncate text-[14px] font-semibold text-ink-900">
                                                        {doc.filename}
                                                    </p>
                                                    <p className="mt-0.5 text-[12px] text-ink-400">
                                                        {formatBytes(doc.file_size_bytes)}
                                                        {doc.page_count
                                                            ? ` · ${doc.page_count} pages`
                                                            : ''}
                                                    </p>
                                                </div>
                                            </div>
                                            {/* Type */}
                                            <div className="flex items-center md:block">
                                                <span className="text-[11px] font-bold uppercase tracking-wider text-ink-300 md:hidden">
                                                    Type
                                                </span>
                                                <span className="text-[13px] font-medium text-ink-600">
                                                    {type.label}
                                                </span>
                                            </div>
                                            {/* Status */}
                                            <div className="flex items-center md:block">
                                                <span className="mr-2 text-[11px] font-bold uppercase tracking-wider text-ink-300 md:hidden">
                                                    Status
                                                </span>
                                                <StatusBadge status={doc.status} />
                                            </div>
                                            {/* Uploaded */}
                                            <div className="flex items-center justify-between md:justify-end">
                                                <span className="text-[11px] font-bold uppercase tracking-wider text-ink-300 md:hidden">
                                                    Uploaded
                                                </span>
                                                <span
                                                    className="whitespace-nowrap text-[12.5px] text-ink-400"
                                                    title={new Date(doc.created_at).toLocaleString()}
                                                >
                                                    {timeAgo(doc.created_at)}
                                                </span>
                                            </div>
                                        </li>
                                    )
                                })}
                                {filtered.length === 0 && (
                                    <li className="px-6 py-12 text-center text-[13.5px] text-ink-400">
                                                        No documents match{' '}
                                                        <span className="font-semibold text-ink-600">
                                                            {query || typeFilter}
                                                        </span>
                                                        . Try a different search.
                                    </li>
                                )}
                            </ul>
                        </div>
                    </div>
                )}
            </div>
        </AppLayout>
    )
}
