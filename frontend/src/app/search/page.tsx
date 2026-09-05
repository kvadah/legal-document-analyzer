'use client'

/**
 * Search page (10-frontend-spec.md §5) — keyword / semantic / hybrid search
 * over the org's chunk corpus, results grouped by document with snippet
 * highlights, deep-links into the Analysis view at the matched page, and a
 * "ask a question instead" heuristic route into document Q&A.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import {
    Search as SearchIcon,
    Loader2,
    AlertCircle,
    FileText,
    Sparkles,
    X,
    KeyRound,
    Layers,
    MessageCircleQuestion,
    FileWarning,
} from 'lucide-react'
import AppLayout from '@/app/app-layout'
import {
    apiSearch,
    type SearchMode,
    type SearchResponse,
} from '@/lib/api-client'
import { PageHeader } from '@/components/ui/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { docTypeMeta, statusMeta, timeAgo } from '@/lib/format'
import { cn } from '@/lib/cn'

const MODES: { id: SearchMode; icon: typeof KeyRound; label: string; hint: string }[] = [
    { id: 'hybrid', icon: Layers, label: 'Hybrid', hint: 'Best general results' },
    { id: 'keyword', icon: KeyRound, label: 'Keyword', hint: 'Exact terms & phrases' },
    { id: 'semantic', icon: Sparkles, label: 'Semantic', hint: 'Conceptual matches' },
]

const QUESTION_STARTERS = /^(what|which|who|whom|whose|when|where|why|how|is|are|does|do|did|can|could|should|shall|will|would)\b/i

function looksLikeQuestion(query: string): boolean {
    const trimmed = query.trim()
    return trimmed.endsWith('?') || QUESTION_STARTERS.test(trimmed)
}

function Highlight({ text, query }: { text: string; query: string }) {
    const terms = useMemo(
        () =>
            query
                .match(/"([^"]+)"|\S+/g)
                ?.map(t => t.replace(/^"|"$/g, ''))
                .filter(t => t.length > 2) ?? [],
        [query],
    )
    if (terms.length === 0) return <>{text}</>
    const pattern = new RegExp(
        `(${terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
        'gi',
    )
    const parts = text.split(pattern)
    return (
        <>
            {parts.map((part, i) =>
                i % 2 === 1 ? (
                    <mark key={i} className="rounded bg-gold-100 px-0.5 font-semibold text-gold-800">
                        {part}
                    </mark>
                ) : (
                    <span key={i}>{part}</span>
                ),
            )}
        </>
    )
}

function SourceBadge({ source }: { source: string }) {
    const meta =
        source === 'both'
            ? { label: 'Keyword + Semantic', cls: 'bg-violet-50 text-violet-700 ring-violet-600/15' }
            : source === 'keyword'
              ? { label: 'Keyword', cls: 'bg-sky-50 text-sky-700 ring-sky-600/15' }
              : { label: 'Semantic', cls: 'bg-indigo-50 text-indigo-700 ring-indigo-600/15' }
    return <span className={cn('pill ring-1 ring-inset', meta.cls)}>{meta.label}</span>
}

export default function SearchPage() {
    const [query, setQuery] = useState('')
    const [mode, setMode] = useState<SearchMode>('hybrid')
    const [results, setResults] = useState<SearchResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [searched, setSearched] = useState(false)
    const inputRef = useRef<HTMLInputElement>(null)
    const abortRef = useRef<number | null>(null)

    const runSearch = useCallback(async () => {
        const q = query.trim()
        if (!q) {
            setResults(null)
            setSearched(false)
            return
        }
        const ticket = Date.now()
        abortRef.current = ticket
        setLoading(true)
        setError(null)
        try {
            const data = await apiSearch({ query: q, mode })
            if (abortRef.current !== ticket) return
            setResults(data)
        } catch (err) {
            if (abortRef.current !== ticket) return
            setError(err instanceof Error ? err.message : 'Search failed')
            setResults(null)
        } finally {
            if (abortRef.current === ticket) setLoading(false)
            setSearched(true)
        }
    }, [query, mode])

    // Debounced auto-search
    useEffect(() => {
        if (!query.trim()) {
            setResults(null)
            setSearched(false)
            setError(null)
            return
        }
        const id = setTimeout(() => void runSearch(), 350)
        return () => clearTimeout(id)
    }, [query, runSearch])

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

    const questionHint = useMemo(
        () => looksLikeQuestion(query) && results?.groups.length === 1,
        [query, results],
    )
    const hintDoc = questionHint ? results!.groups[0].document : null

    return (
        <AppLayout>
            <div className="mx-auto max-w-3xl space-y-6">
                <PageHeader
                    eyebrow="Discovery"
                    title="Search"
                    description="Search across every ingested document — by exact term or by meaning."
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
                            onKeyDown={e => e.key === 'Enter' && void runSearch()}
                            placeholder="Try “termination notice”, “liability cap”, or “weak liability protection”…"
                            className="min-w-0 flex-1 bg-transparent text-[16px] text-ink-900 placeholder:text-ink-300 focus:outline-none"
                            autoFocus
                        />
                        {loading ? (
                            <Loader2 size={16} className="animate-spin text-indigo-400" />
                        ) : query ? (
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
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                        <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-ink-400">
                            Mode
                        </span>
                        {MODES.map(m => (
                            <button
                                key={m.id}
                                onClick={() => setMode(m.id)}
                                title={m.hint}
                                className={cn(
                                    'inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-[12.5px] font-semibold transition-all duration-200',
                                    mode === m.id
                                        ? 'border-primary/30 bg-indigo-50 text-indigo-700 shadow-[0_2px_10px_-2px_rgba(99,102,241,0.3)]'
                                        : 'border-ink-100 bg-white text-ink-500 hover:border-ink-200 hover:text-ink-700',
                                )}
                            >
                                <m.icon size={12.5} />
                                {m.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Question heuristic */}
                {questionHint && hintDoc && (
                    <Link
                        href={`/documents/${hintDoc.id}?tab=qa&q=${encodeURIComponent(query.trim())}`}
                        className="group flex animate-scale-in items-center gap-3 rounded-xl border border-indigo-200/70 bg-indigo-50/70 px-5 py-3.5 text-[13.5px] text-indigo-800 transition-colors hover:bg-indigo-50"
                    >
                        <MessageCircleQuestion size={16} className="shrink-0 text-indigo-500" />
                        <span className="min-w-0 flex-1">
                            That looks like a question — ask it against{' '}
                            <span className="font-semibold">{hintDoc.filename}</span>{' '}
                            for a cited answer instead.
                        </span>
                        <span className="font-semibold text-indigo-600 transition-transform group-hover:translate-x-0.5">
                            Ask →
                        </span>
                    </Link>
                )}

                {/* Error */}
                {error && (
                    <div className="flex items-center gap-3 rounded-xl border border-rose-200/80 bg-rose-50 px-5 py-4 text-[13.5px] text-rose-700">
                        <AlertCircle size={17} className="shrink-0" />
                        {error}
                        <button
                            onClick={() => void runSearch()}
                            className="ml-auto font-semibold underline-offset-2 hover:underline"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {/* Empty states */}
                {!loading && !error && !query && (
                    <EmptyState
                        icon={SearchIcon}
                        title="Search your entire portfolio"
                        description="Keyword finds exact terms, Semantic finds concepts, Hybrid blends both. Press ⌘K from anywhere to jump back here."
                    />
                )}

                {!loading && !error && query && searched && results && results.groups.length === 0 && (
                    <EmptyState
                        icon={FileWarning}
                        title={`No matches for “${query.trim()}”`}
                        description={
                            mode === 'keyword'
                                ? 'Keyword mode needs exact terms — try Hybrid or Semantic for conceptual matches.'
                                : 'Try different wording, or switch modes — some phrasings only match one way.'
                        }
                    />
                )}

                {/* Loading skeletons */}
                {loading && (
                    <div className="space-y-3">
                        {[0, 1].map(i => (
                            <div key={i} className="card p-4">
                                <div className="skeleton h-4 w-1/3" />
                                <div className="mt-3 space-y-2">
                                    <div className="skeleton h-3 w-full" />
                                    <div className="skeleton h-3 w-4/5" />
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Results */}
                {!loading && results && results.groups.length > 0 && (
                    <div className="space-y-4">
                        <p className="animate-fade-in px-1 text-[12.5px] font-medium text-ink-400">
                            {results.total_documents} document{results.total_documents !== 1 ? 's' : ''}
                            {' · '}
                            {results.total_snippets} matching passage{results.total_snippets !== 1 ? 's' : ''}
                            {' · '}
                            <span className="capitalize">{results.mode}</span>
                        </p>
                        <ul className="space-y-3">
                            {results.groups.map((group, gi) => {
                                const type = docTypeMeta(group.document.document_type)
                                return (
                                    <li
                                        key={group.document.id}
                                        className="card animate-fade-up overflow-hidden"
                                        style={{ animationDelay: `${Math.min(gi, 6) * 50}ms` }}
                                    >
                                        <div className="flex items-center gap-3.5 border-b border-ink-50 bg-ink-50/40 px-4 py-3">
                                            <span
                                                className={cn(
                                                    'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[9.5px] font-bold ring-1 ring-inset',
                                                    type.tile,
                                                )}
                                            >
                                                {type.glyph}
                                            </span>
                                            <div className="min-w-0 flex-1">
                                                <Link
                                                    href={`/documents/${group.document.id}`}
                                                    className="truncate text-[14px] font-semibold text-ink-900 transition-colors hover:text-indigo-700"
                                                >
                                                    {group.document.filename}
                                                </Link>
                                                <p className="mt-0.5 text-[11.5px] text-ink-400">
                                                    {type.label} · {statusMeta(group.document.status).label} · {timeAgo(group.document.created_at)}
                                                </p>
                                            </div>
                                            {group.document.contract_score != null && (
                                                <span className="pill bg-white px-2.5 py-1 text-[11px] text-ink-600 ring-1 ring-inset ring-ink-200">
                                                    Score
                                                    <span className="font-display text-[13px] font-bold text-ink-800">
                                                        {group.document.contract_score}
                                                    </span>
                                                </span>
                                            )}
                                        </div>
                                        <ul className="divide-y divide-ink-50">
                                            {group.snippets.map(snippet => (
                                                <li key={snippet.chunk_id} className="group px-4 py-3">
                                                    <div className="mb-1.5 flex items-center gap-2">
                                                        <SourceBadge source={snippet.source} />
                                                        {snippet.section_heading && (
                                                            <span className="truncate text-[11px] font-semibold uppercase tracking-wider text-ink-300">
                                                                {snippet.section_heading}
                                                            </span>
                                                        )}
                                                        <span className="ml-auto flex items-center gap-1.5">
                                                            {snippet.source !== 'semantic' && (
                                                                <FileText size={12} className="text-ink-300" />
                                                            )}
                                                            <span className="text-[11px] font-semibold text-ink-400">
                                                                p. {snippet.page_number}
                                                            </span>
                                                        </span>
                                                    </div>
                                                    <Link
                                                        href={`/documents/${group.document.id}?page=${snippet.page_number}`}
                                                        className="block rounded-lg px-1 py-0.5 text-[13px] leading-relaxed text-ink-600 transition-colors hover:bg-indigo-50/40 hover:text-ink-800"
                                                        title="Open in the document viewer"
                                                    >
                                                        <Highlight text={snippet.text} query={results.query} />
                                                    </Link>
                                                </li>
                                            ))}
                                        </ul>
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
