'use client'

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
    ArrowLeftRight,
    FileDiff,
    Loader2,
    AlertCircle,
    Search,
    ChevronDown,
    ChevronUp,
    FileText,
    Upload,
    ExternalLink,
} from 'lucide-react'
import AppLayout from '@/app/app-layout'
import {
    apiCreateComparison,
    apiGetComparison,
    apiListDocuments,
    type ClauseChangeStatus,
    type ClauseDiffEntry,
    type ComparisonOut,
    type DocumentOut,
    type ParagraphChangeStatus,
    type ParagraphDiffEntry,
    type WordDiffOp,
} from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { clauseLabel } from '@/lib/analysis-meta'
import { docTypeMeta } from '@/lib/format'
import { cn } from '@/lib/cn'

// ── Diff rendering ───────────────────────────────────────────────────────────

const REMOVAL_SPAN = 'rounded bg-rose-100 text-rose-800'
const ADDITION_SPAN = 'rounded bg-emerald-100 text-emerald-800'

function SidePane({ ops, side }: { ops: WordDiffOp[]; side: 'a' | 'b' }) {
    return (
        <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-700">
            {ops.map((seg, i) => {
                if (side === 'a') {
                    if (seg.text_a == null) return null
                    return (
                        <span
                            key={i}
                            className={cn(seg.op !== 'equal' && REMOVAL_SPAN)}
                        >
                            {seg.text_a}{' '}
                        </span>
                    )
                }
                if (seg.text_b == null) return null
                return (
                    <span
                        key={i}
                        className={cn(seg.op !== 'equal' && ADDITION_SPAN)}
                    >
                        {seg.text_b}{' '}
                    </span>
                )
            })}
        </p>
    )
}

function UnifiedDiff({ ops }: { ops: WordDiffOp[] }) {
    return (
        <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-700">
            {ops.map((seg, i) => {
                if (seg.op === 'equal') {
                    return (
                        <span key={i}>
                            {seg.text_a}{' '}
                        </span>
                    )
                }
                if (seg.op === 'replace') {
                    return (
                        <span key={i} className="whitespace-nowrap">
                            <span className={REMOVAL_SPAN}>
                                {seg.text_a}{' '}
                            </span>
                            <span className={ADDITION_SPAN}>
                                {seg.text_b}{' '}
                            </span>
                        </span>
                    )
                }
                const removed = seg.op === 'delete'
                return (
                    <span
                        key={i}
                        className={removed ? REMOVAL_SPAN : ADDITION_SPAN}
                    >
                        {((removed ? seg.text_a : seg.text_b) ?? '') + ' '}
                    </span>
                )
            })}
        </p>
    )
}

function DiffPageLink({
    documentId,
    page,
    side,
}: {
    documentId: string
    page: number
    side: 'a' | 'b'
}) {
    return (
        <Link
            href={`/documents/${documentId}?page=${page}`}
            className={cn(
                'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold transition-colors',
                side === 'a'
                    ? 'text-rose-600 hover:bg-rose-50'
                    : 'text-emerald-700 hover:bg-emerald-50',
            )}
        >
            p. {page}
            <ExternalLink size={10} />
        </Link>
    )
}

function DiffBody({
    entry,
    documentAId,
    documentBId,
    viewMode,
}: {
    entry: ClauseDiffEntry | ParagraphDiffEntry
    documentAId: string
    documentBId: string
    viewMode: 'split' | 'unified'
}) {
    const ops = entry.word_diff ?? []
    const split = viewMode === 'split' && entry.status === 'modified' && ops.length > 0

    if (entry.status === 'added') {
        return (
            <div className="rounded-lg border border-emerald-200/70 bg-emerald-50/50 p-3.5">
                <p className="text-[13.5px] leading-relaxed text-ink-700">
                    {entry.text_b}
                </p>
                {entry.page_b != null && (
                    <div className="mt-2">
                        <DiffPageLink documentId={documentBId} page={entry.page_b} side="b" />
                    </div>
                )}
            </div>
        )
    }
    if (entry.status === 'removed') {
        return (
            <div className="rounded-lg border border-rose-200/70 bg-rose-50/50 p-3.5">
                <p className="text-[13.5px] leading-relaxed text-ink-700">
                    {entry.text_a}
                </p>
                {entry.page_a != null && (
                    <div className="mt-2">
                        <DiffPageLink documentId={documentAId} page={entry.page_a} side="a" />
                    </div>
                )}
            </div>
        )
    }

    const pageLinks = (
        <div className="mt-2 flex gap-3">
            {entry.page_a != null && (
                <DiffPageLink documentId={documentAId} page={entry.page_a} side="a" />
            )}
            {entry.page_b != null && (
                <DiffPageLink documentId={documentBId} page={entry.page_b} side="b" />
            )}
        </div>
    )

    if (split) {
        return (
            <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-ink-100 bg-white p-3.5">
                    <p className="mb-2 text-[10.5px] font-bold uppercase tracking-[0.14em] text-rose-500">
                        Original
                    </p>
                    <SidePane ops={ops} side="a" />
                </div>
                <div className="rounded-lg border border-ink-100 bg-white p-3.5">
                    <p className="mb-2 text-[10.5px] font-bold uppercase tracking-[0.14em] text-emerald-600">
                        Revised
                    </p>
                    <SidePane ops={ops} side="b" />
                </div>
            </div>
        )
    }
    return (
        <div className="rounded-lg border border-ink-100 bg-white p-3.5">
            {ops.length > 0 ? (
                <UnifiedDiff ops={ops} />
            ) : (
                <p className="text-[13.5px] leading-relaxed text-ink-500">
                    {entry.text_b ?? entry.text_a}
                </p>
            )}
            {pageLinks}
        </div>
    )
}

// ── Status meta ──────────────────────────────────────────────────────────────

const CHANGE_META: Record<ClauseChangeStatus, { label: string; pill: string }> = {
    modified: {
        label: 'Modified',
        pill: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20',
    },
    added: {
        label: 'Added',
        pill: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/15',
    },
    removed: {
        label: 'Removed',
        pill: 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/20',
    },
    unchanged: {
        label: 'Unchanged',
        pill: 'bg-ink-100 text-ink-600 ring-1 ring-inset ring-ink-500/10',
    },
}

const STATUS_RANK: Record<ClauseChangeStatus, number> = {
    modified: 0,
    added: 1,
    removed: 2,
    unchanged: 3,
}

const ALL_STATUSES: ClauseChangeStatus[] = ['modified', 'added', 'removed', 'unchanged']

function changeMeta(status: ParagraphChangeStatus | ClauseChangeStatus) {
    return CHANGE_META[status] ?? CHANGE_META.unchanged
}

// ── Result view ──────────────────────────────────────────────────────────────

function ComparisonResult({ comparison }: { comparison: ComparisonOut }) {
    const [statusFilter, setStatusFilter] = useState<Set<ClauseChangeStatus>>(
        new Set(ALL_STATUSES),
    )
    const [typeFilter, setTypeFilter] = useState<string>('all')
    const [viewMode, setViewMode] = useState<'split' | 'unified'>('split')
    const [otherOpen, setOtherOpen] = useState(false)

    const clauseTypes = useMemo(
        () =>
            Array.from(new Set(comparison.clauses.map(c => c.clause_type))).sort(),
        [comparison],
    )

    const visibleClauses = useMemo(
        () =>
            comparison.clauses
                .filter(
                    c =>
                        statusFilter.has(c.status) &&
                        (typeFilter === 'all' || c.clause_type === typeFilter),
                )
                .sort(
                    (x, y) =>
                        STATUS_RANK[x.status] - STATUS_RANK[y.status] ||
                        x.clause_type.localeCompare(y.clause_type),
                ),
        [comparison, statusFilter, typeFilter],
    )

    const toggleStatus = (status: ClauseChangeStatus) => {
        setStatusFilter(prev => {
            const next = new Set(prev)
            if (next.has(status)) next.delete(status)
            else next.add(status)
            return next
        })
    }

    return (
        <>
            {/* Summary chips + filters */}
            <div className="card flex flex-wrap items-center justify-between gap-4 px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                    {ALL_STATUSES.map(status => (
                        <button
                            key={status}
                            onClick={() => toggleStatus(status)}
                            className={cn(
                                'pill flex items-center gap-1.5 transition-opacity',
                                changeMeta(status).pill,
                                !statusFilter.has(status) && 'opacity-40',
                            )}
                        >
                            {changeMeta(status).label}
                            <span className="font-bold">
                                {comparison.counts?.[status] ?? 0}
                            </span>
                        </button>
                    ))}
                </div>
                <div className="flex items-center gap-2">
                    {clauseTypes.length > 1 && (
                        <select
                            value={typeFilter}
                            onChange={e => setTypeFilter(e.target.value)}
                            className="field px-3 py-2 text-[13px]"
                        >
                            <option value="all">All clause types</option>
                            {clauseTypes.map(type => (
                                <option key={type} value={type}>
                                    {clauseLabel(type)}
                                </option>
                            ))}
                        </select>
                    )}
                    <div className="flex overflow-hidden rounded-lg border border-ink-200">
                        {(['split', 'unified'] as const).map(mode => (
                            <button
                                key={mode}
                                onClick={() => setViewMode(mode)}
                                className={cn(
                                    'px-3 py-2 text-[12.5px] font-semibold transition-colors',
                                    viewMode === mode
                                        ? 'bg-ink-900 text-white'
                                        : 'bg-white text-ink-500 hover:bg-ink-50',
                                )}
                            >
                                {mode === 'split' ? 'Side-by-side' : 'Unified'}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Clause diff cards */}
            <div className="space-y-3">
                {visibleClauses.length === 0 ? (
                    <div className="card px-5 py-8 text-center">
                        <p className="text-[14px] text-ink-400">
                            No clauses match the current filters.
                        </p>
                    </div>
                ) : (
                    visibleClauses.map((entry, i) => (
                        <div key={`${entry.clause_type}-${i}`} className="card p-4">
                            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                                <h3 className="text-[14.5px] font-semibold text-ink-800">
                                    {clauseLabel(entry.clause_type)}
                                </h3>
                                <span className={cn('pill', changeMeta(entry.status).pill)}>
                                    {changeMeta(entry.status).label}
                                </span>
                            </div>
                            {entry.status === 'unchanged' ? (
                                <p className="rounded-lg bg-ink-50 px-3.5 py-2.5 text-[13px] leading-relaxed text-ink-500">
                                    {entry.text_b ?? entry.text_a}
                                </p>
                            ) : (
                                <DiffBody
                                    entry={entry}
                                    documentAId={comparison.document_id_a}
                                    documentBId={comparison.document_id_b}
                                    viewMode={viewMode}
                                />
                            )}
                        </div>
                    ))
                )}
            </div>

            {/* Other Changes (outside the tracked clause types) */}
            {comparison.other_changes.length > 0 && (
                <div className="card p-4">
                    <button
                        onClick={() => setOtherOpen(!otherOpen)}
                        className="flex w-full items-center justify-between gap-2 text-left"
                    >
                        <h3 className="text-[14.5px] font-semibold text-ink-800">
                            Other Changes
                            <span className="ml-2 rounded-full bg-ink-100 px-2 py-0.5 text-[11.5px] font-bold text-ink-500">
                                {comparison.other_changes.length}
                            </span>
                            <span className="ml-2 text-[12.5px] font-normal text-ink-400">
                                content outside the tracked clause types
                            </span>
                        </h3>
                        {otherOpen ? (
                            <ChevronUp size={16} className="shrink-0 text-ink-400" />
                        ) : (
                            <ChevronDown size={16} className="shrink-0 text-ink-400" />
                        )}
                    </button>
                    {otherOpen && (
                        <div className="mt-3 space-y-3">
                            {comparison.other_changes.map((entry, i) => (
                                <div
                                    key={i}
                                    className="rounded-xl border border-ink-100 bg-ink-50/40 p-3"
                                >
                                    <div className="mb-2">
                                        <span
                                            className={cn(
                                                'pill text-[11px]',
                                                changeMeta(entry.status).pill,
                                            )}
                                        >
                                            {changeMeta(entry.status).label}
                                        </span>
                                    </div>
                                    <DiffBody
                                        entry={entry}
                                        documentAId={comparison.document_id_a}
                                        documentBId={comparison.document_id_b}
                                        viewMode={viewMode}
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </>
    )
}

// ── Document picker ──────────────────────────────────────────────────────────

function DocumentPicker({
    label,
    tone,
    documents,
    selectedId,
    onSelect,
}: {
    label: string
    tone: 'a' | 'b'
    documents: DocumentOut[]
    selectedId: string | null
    onSelect: (id: string | null) => void
}) {
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState('')
    const rootRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!open) return
        const onClick = (e: MouseEvent) => {
            if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
        }
        document.addEventListener('mousedown', onClick)
        return () => document.removeEventListener('mousedown', onClick)
    }, [open])

    const selected = documents.find(d => d.id === selectedId) ?? null
    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase()
        return q ? documents.filter(d => d.filename.toLowerCase().includes(q)) : documents
    }, [documents, query])

    return (
        <div ref={rootRef} className="relative min-w-0 flex-1">
            <p className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-ink-400">
                {label}
            </p>
            {selected ? (
                <div className="flex items-center justify-between gap-3 rounded-xl border border-ink-200 bg-white px-4 py-3 shadow-soft">
                    <div className="flex min-w-0 items-center gap-3">
                        <span
                            className={cn(
                                'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold',
                                tone === 'a'
                                    ? 'bg-rose-50 text-rose-600'
                                    : 'bg-emerald-50 text-emerald-600',
                            )}
                        >
                            {tone.toUpperCase()}
                        </span>
                        <div className="min-w-0">
                            <p className="truncate text-[14px] font-semibold text-ink-800">
                                {selected.filename}
                            </p>
                            <p className="text-[12px] text-ink-400">
                                {docTypeMeta(selected.document_type).label}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={() => {
                            onSelect(null)
                            setQuery('')
                        }}
                        className="btn-ghost px-2.5 py-1.5 text-[12.5px]"
                    >
                        Change
                    </button>
                </div>
            ) : (
                <button
                    onClick={() => setOpen(!open)}
                    className="flex w-full items-center gap-2.5 rounded-xl border border-ink-200 bg-white px-4 py-3 text-left shadow-soft transition-colors hover:border-primary/40"
                >
                    <Search size={15} className="shrink-0 text-ink-300" />
                    <span className="text-[14px] text-ink-400">
                        Search analysed documents…
                    </span>
                    <ChevronDown
                        size={15}
                        className={cn(
                            'ml-auto shrink-0 text-ink-300 transition-transform',
                            open && 'rotate-180',
                        )}
                    />
                </button>
            )}

            {open && !selected && (
                <div className="absolute z-20 mt-1.5 w-full overflow-hidden rounded-xl border border-ink-200 bg-white shadow-lift">
                    <div className="border-b border-ink-100 p-2">
                        <input
                            autoFocus
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            placeholder="Filter by filename…"
                            className="w-full rounded-lg bg-ink-50 px-3 py-2 text-[13.5px] text-ink-800 outline-none placeholder:text-ink-300 focus:ring-2 focus:ring-primary/30"
                        />
                    </div>
                    <div className="max-h-64 overflow-y-auto p-1.5">
                        {filtered.length === 0 ? (
                            <p className="px-3 py-4 text-center text-[13px] text-ink-400">
                                No matching documents
                            </p>
                        ) : (
                            filtered.map(doc => (
                                <button
                                    key={doc.id}
                                    onClick={() => {
                                        onSelect(doc.id)
                                        setOpen(false)
                                    }}
                                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-indigo-50/70"
                                >
                                    <FileText size={14} className="shrink-0 text-ink-300" />
                                    <span className="truncate text-[13.5px] font-medium text-ink-700">
                                        {doc.filename}
                                    </span>
                                    <span className="ml-auto shrink-0 text-[11.5px] text-ink-400">
                                        {docTypeMeta(doc.document_type).label}
                                    </span>
                                </button>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}

// ── Page ─────────────────────────────────────────────────────────────────────

function CompareView() {
    const { user } = useAuth()
    const searchParams = useSearchParams()

    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [loadingDocs, setLoadingDocs] = useState(true)
    const [docError, setDocError] = useState<string | null>(null)
    const [docAId, setDocAId] = useState<string | null>(searchParams.get('a'))
    const [docBId, setDocBId] = useState<string | null>(searchParams.get('b'))
    const [comparison, setComparison] = useState<ComparisonOut | null>(null)
    const [comparing, setComparing] = useState(false)
    const [compareError, setCompareError] = useState<string | null>(null)

    const canTrigger = user?.role === 'admin' || user?.role === 'reviewer'

    useEffect(() => {
        async function load() {
            try {
                const data = await apiListDocuments()
                setDocuments(data.items.filter(d => d.status === 'analysis_ready'))
            } catch (err) {
                setDocError(
                    err instanceof Error ? err.message : 'Failed to load documents',
                )
            } finally {
                setLoadingDocs(false)
            }
        }
        void load()
    }, [])

    // Poll the async comparison job until it completes (or fails).
    const busy =
        comparison?.status === 'pending' || comparison?.status === 'processing'
    useEffect(() => {
        if (!comparison || !busy) return
        const id = setInterval(async () => {
            try {
                setComparison(await apiGetComparison(comparison.id))
            } catch {
                // transient poll failure — keep polling
            }
        }, 2000)
        return () => clearInterval(id)
    }, [comparison, busy])

    const selectDoc = useCallback((side: 'a' | 'b', id: string | null) => {
        if (side === 'a') setDocAId(id)
        else setDocBId(id)
        // Selection no longer matches the shown result — reset it.
        setComparison(null)
        setCompareError(null)
    }, [])

    const startComparison = useCallback(async () => {
        if (!docAId || !docBId) return
        setComparing(true)
        setCompareError(null)
        setComparison(null)
        try {
            const created = await apiCreateComparison(docAId, docBId)
            setComparison(await apiGetComparison(created.comparison_id))
        } catch (err) {
            setCompareError(
                err instanceof Error ? err.message : 'Failed to start comparison',
            )
        } finally {
            setComparing(false)
        }
    }, [docAId, docBId])

    const swap = useCallback(() => {
        setDocAId(docBId)
        setDocBId(docAId)
        setComparison(null)
        setCompareError(null)
    }, [docAId, docBId])

    if (loadingDocs) {
        return (
            <AppLayout>
                <div className="flex items-center justify-center py-24">
                    <Loader2 size={22} className="animate-spin text-primary" />
                </div>
            </AppLayout>
        )
    }

    if (docError) {
        return (
            <AppLayout>
                <PageHeader
                    eyebrow="Workspace"
                    title="Compare documents"
                    description="Side-by-side clause-level diff between two document versions."
                />
                <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-4">
                    <AlertCircle size={18} className="shrink-0 text-rose-500" />
                    <p className="text-[14px] text-rose-700">{docError}</p>
                </div>
            </AppLayout>
        )
    }

    if (documents.length < 2) {
        return (
            <AppLayout>
                <PageHeader
                    eyebrow="Workspace"
                    title="Compare documents"
                    description="Side-by-side clause-level diff between two document versions."
                />
                <EmptyState
                    icon={FileDiff}
                    title="Need two analysed documents"
                    description="Comparison works on any two documents that have completed AI analysis. Upload at least two documents and let the pipeline finish."
                    action={
                        <Link href="/upload" className="btn-primary px-5 py-2.5">
                            <Upload size={15} />
                            Upload documents
                        </Link>
                    }
                />
            </AppLayout>
        )
    }

    return (
        <AppLayout>
            <div className="space-y-6">
                <PageHeader
                    eyebrow="Workspace"
                    title="Compare documents"
                    description="Clause-level diff between two documents — added, removed and modified provisions with word-level highlights."
                />

                {/* Picker row */}
                <div className="card p-5">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
                        <DocumentPicker
                            label="Document A (original)"
                            tone="a"
                            documents={documents}
                            selectedId={docAId}
                            onSelect={id => selectDoc('a', id)}
                        />
                        <button
                            onClick={swap}
                            disabled={!docAId && !docBId}
                            title="Swap documents"
                            aria-label="Swap documents"
                            className="btn-secondary mx-auto shrink-0 px-3 py-2.5"
                        >
                            <ArrowLeftRight size={15} />
                        </button>
                        <DocumentPicker
                            label="Document B (revised)"
                            tone="b"
                            documents={documents}
                            selectedId={docBId}
                            onSelect={id => selectDoc('b', id)}
                        />
                        <button
                            onClick={() => void startComparison()}
                            disabled={
                                !docAId ||
                                !docBId ||
                                docAId === docBId ||
                                comparing ||
                                busy ||
                                !canTrigger
                            }
                            className="btn-primary shrink-0 px-5 py-3 text-[14px]"
                        >
                            {comparing || busy ? (
                                <>
                                    <Loader2 size={15} className="animate-spin" />
                                    Comparing…
                                </>
                            ) : (
                                <>
                                    <FileDiff size={15} />
                                    Compare
                                </>
                            )}
                        </button>
                    </div>
                    {!canTrigger && (
                        <p className="mt-3 text-[12.5px] text-ink-400">
                            Your role ({user?.role ?? 'viewer'}) is read-only — a
                            reviewer or admin can trigger comparisons.
                        </p>
                    )}
                    {docAId && docAId === docBId && (
                        <p className="mt-3 text-[12.5px] text-rose-600">
                            Pick two different documents to compare.
                        </p>
                    )}
                </div>

                {compareError && (
                    <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-4">
                        <AlertCircle size={18} className="shrink-0 text-rose-500" />
                        <p className="text-[14px] text-rose-700">{compareError}</p>
                    </div>
                )}

                {/* In-flight state */}
                {comparison && busy && (
                    <div className="card flex items-center gap-3 px-5 py-4">
                        <Loader2 size={17} className="animate-spin text-primary" />
                        <p className="text-[14px] text-ink-600">
                            Comparing{' '}
                            <span className="font-semibold text-ink-800">
                                {comparison.document_a.filename}
                            </span>{' '}
                            against{' '}
                            <span className="font-semibold text-ink-800">
                                {comparison.document_b.filename}
                            </span>{' '}
                            — aligning clauses and computing the diff…
                        </p>
                    </div>
                )}

                {/* Error state */}
                {comparison?.status === 'error' && (
                    <div className="card flex items-center gap-3 border-rose-200 bg-rose-50/60 px-5 py-4">
                        <AlertCircle size={18} className="shrink-0 text-rose-500" />
                        <p className="text-[14px] text-rose-700">
                            {comparison.error ?? 'The comparison job failed.'}
                        </p>
                    </div>
                )}

                {/* Result */}
                {comparison?.status === 'completed' && comparison.counts && (
                    <ComparisonResult comparison={comparison} />
                )}
            </div>
        </AppLayout>
    )
}

export default function ComparePage() {
    // useSearchParams requires a Suspense boundary during prerendering
    return (
        <Suspense fallback={null}>
            <CompareView />
        </Suspense>
    )
}
