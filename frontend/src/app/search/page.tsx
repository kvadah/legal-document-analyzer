'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
    Search as SearchIcon,
    Loader2,
    AlertCircle,
    FileText,
    Sparkles,
    X,
    KeyRound,
} from 'lucide-react'
import AppLayout from '@/app/app-layout'
import { apiListDocuments, type DocumentOut } from '@/lib/api-client'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { docTypeMeta, formatBytes, timeAgo } from '@/lib/format'
import { cn } from '@/lib/cn'

function Highlight({ text, query }: { text: string; query: string }) {
    if (!query) return <>{text}</>
    const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))
    return (
        <>
            {parts.map((part, i) =>
                part.toLowerCase() === query.toLowerCase() ? (
                    <mark
                        key={i}
                        className="rounded bg-gold-100 px-0.5 font-semibold text-gold-800"
                    >
                        {part}
                    </mark>
                ) : (
                    <span key={i}>{part}</span>
                ),
            )}
        </>
    )
}

type Mode = 'keyword' | 'semantic'

export default function SearchPage() {
    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [query, setQuery] = useState('')
    const [mode, setMode] = useState<Mode>('keyword')
    const inputRef = useRef<HTMLInputElement>(null)

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

    useEffect(() => {
        function onKey(e: KeyboardEvent) {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault()
                inputRef.current?.focus()
            }
        }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [])

    const results = useMemo(() => {
        const q = query.trim().toLowerCase()
        if (!q) return []
        return documents.filter(
            doc =>
                doc.filename.toLowerCase().includes(q) ||
                doc.document_type.toLowerCase().includes(q) ||
                doc.status.replace(/_/g, ' ').includes(q),
        )
    }, [documents, query])

    return (
        <AppLayout>
            <div className="mx-auto max-w-3xl space-y-6">
                <PageHeader
                    eyebrow="Discovery"
                    title="Search"
                    description="Find documents across your portfolio by name, type, or status."
                />

                {/* Search bar */}
                <div className="animate-fade-up relative">
                    <div className="pointer-events-none absolute -inset-1 rounded-2xl bg-gradient-to-r from-indigo-500/15 via-violet-500/15 to-fuchsia-500/15 blur-lg" />
                    <div className="card relative flex items-center gap-3 px-5 py-4">
                        <SearchIcon size={19} className="shrink-0 text-ink-300" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            placeholder="Try “agreement”, “nda”, or “error”…"
                            className="min-w-0 flex-1 bg-transparent text-[16px] text-ink-900 placeholder:text-ink-300 focus:outline-none"
                            autoFocus
                        />
                        {query ? (
                            <button
                                onClick={() => setQuery('')}
                                aria-label="Clear search"
                                className="rounded-md p-1 text-ink-300 transition-colors hover:bg-ink-100 hover:text-ink-600"
                            >
                                <X size={16} />
                            </button>
                        ) : (
                            <span className="kbd hidden sm:inline">⌘K</span>
                        )}
                    </div>

                    {/* Mode toggle */}
                    <div className="mt-4 flex items-center gap-2">
                        <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-ink-400">
                            Mode
                        </span>
                        {(
                            [
                                { id: 'keyword', icon: KeyRound, label: 'Keyword', hint: 'Instant' },
                                {
                                    id: 'semantic',
                                    icon: Sparkles,
                                    label: 'Semantic',
                                    hint: 'Coming soon',
                                },
                            ] as const
                        ).map(m => (
                            <button
                                key={m.id}
                                onClick={() => m.id === 'keyword' && setMode(m.id)}
                                disabled={m.id === 'semantic'}
                                title={m.id === 'semantic' ? 'Semantic search arrives with the embeddings pipeline' : undefined}
                                className={cn(
                                    'group inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-[12.5px] font-semibold transition-all duration-200',
                                    mode === m.id
                                        ? 'border-primary/30 bg-indigo-50 text-indigo-700 shadow-[0_2px_10px_-2px_rgba(99,102,241,0.3)]'
                                        : m.id === 'semantic'
                                          ? 'cursor-not-allowed border-ink-100 bg-ink-50 text-ink-300'
                                          : 'border-ink-100 bg-white text-ink-500 hover:border-ink-200 hover:text-ink-700',
                                )}
                            >
                                <m.icon size={12.5} />
                                {m.label}
                                {m.id === 'semantic' && (
                                    <span className="rounded-full bg-ink-100 px-1.5 py-px text-[9px] font-bold uppercase tracking-wider text-ink-400">
                                        {m.hint}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* States */}
                {loading && (
                    <div className="flex items-center justify-center gap-3 py-16 text-[14px] text-ink-400">
                        <Loader2 size={18} className="animate-spin" />
                        Loading your portfolio…
                    </div>
                )}

                {error && (
                    <div className="flex items-center gap-3 rounded-xl border border-rose-200/80 bg-rose-50 px-5 py-4 text-[13.5px] text-rose-700">
                        <AlertCircle size={17} className="shrink-0" />
                        {error}
                    </div>
                )}

                {!loading && !error && !query && (
                    <EmptyState
                        icon={SearchIcon}
                        title="Search your entire portfolio"
                        description="Start typing above to filter documents by filename, type, or status. Press ⌘K from anywhere to jump back here."
                    />
                )}

                {!loading && !error && query && results.length === 0 && (
                    <EmptyState
                        icon={FileText}
                        title={`No matches for “${query}”`}
                        description="Check the spelling or try a broader term — for example the document type or a status like “analyzed”."
                    />
                )}

                {/* Results */}
                {results.length > 0 && (
                    <div className="space-y-3">
                        <p className="animate-fade-in px-1 text-[12.5px] font-medium text-ink-400">
                            {results.length} result{results.length !== 1 ? 's' : ''}
                        </p>
                        <ul className="space-y-3">
                            {results.map((doc, i) => {
                                const type = docTypeMeta(doc.document_type)
                                return (
                                    <li
                                        key={doc.id}
                                        className="card animate-fade-up group flex items-center gap-4 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift"
                                        style={{ animationDelay: `${Math.min(i, 6) * 50}ms` }}
                                    >
                                        <span
                                            className={cn(
                                                'flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold ring-1 ring-inset',
                                                type.tile,
                                            )}
                                        >
                                            {type.glyph}
                                        </span>
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate text-[14.5px] font-semibold text-ink-900">
                                                <Highlight text={doc.filename} query={query.trim()} />
                                            </p>
                                            <p className="mt-0.5 text-[12px] text-ink-400">
                                                {type.label} · {formatBytes(doc.file_size_bytes)} ·{' '}
                                                {timeAgo(doc.created_at)}
                                            </p>
                                        </div>
                                        <StatusBadge status={doc.status} />
                                    </li>
                                )
                            })}
                        </ul>
                    </div>
                )}
            </div>
        </AppLayout>
    )
}
