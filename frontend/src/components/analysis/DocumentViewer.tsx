'use client'

/**
 * Document viewer pane — renders the extracted/OCR'd text page by page with
 * page navigation, and supports jump-to-page + highlight-span driven by
 * CitationLink clicks from the analysis tabs (10-frontend-spec.md §4).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
    ChevronLeft,
    ChevronRight,
    FileText,
    Highlighter,
    Loader2,
    X,
} from 'lucide-react'
import type { DocumentTextResponse } from '@/lib/api-client'
import { cn } from '@/lib/cn'

export interface JumpRequest {
    page: number
    highlightText: string | null
    nonce: number
}

interface HighlightRange {
    start: number
    length: number
}

function findHighlightRange(text: string, needle: string): HighlightRange | null {
    const candidates = [needle, needle.slice(0, 120), needle.slice(0, 60)]
    const lower = text.toLowerCase()
    for (const candidate of candidates) {
        if (!candidate) continue
        const idx = lower.indexOf(candidate.toLowerCase())
        if (idx !== -1) return { start: idx, length: candidate.length }
    }
    return null
}

function HighlightedText({ text, needle }: { text: string; needle: string | null }) {
    if (!needle) return <>{text}</>
    const range = findHighlightRange(text, needle)
    if (!range) return <>{text}</>
    return (
        <>
            {text.slice(0, range.start)}
            <mark className="rounded bg-amber-200/90 px-0.5 text-ink-900">
                {text.slice(range.start, range.start + range.length)}
            </mark>
            {text.slice(range.start + range.length)}
        </>
    )
}

function pageAnchor(page: number) {
    return `doc-viewer-page-${page}`
}

export default function DocumentViewer({
    text,
    filename,
    jumpRequest,
    loading,
}: {
    text: DocumentTextResponse | null
    filename: string
    jumpRequest: JumpRequest | null
    loading: boolean
}) {
    const containerRef = useRef<HTMLDivElement>(null)
    const [currentPage, setCurrentPage] = useState(1)
    const [highlight, setHighlight] = useState<string | null>(null)

    const pageCount = text?.page_count ?? text?.pages.length ?? 0

    const goToPage = useCallback(
        (page: number) => {
            const container = containerRef.current
            if (!container || pageCount === 0) return
            const target = Math.min(Math.max(1, page), pageCount)
            setCurrentPage(target)
            const el = container.querySelector<HTMLElement>(
                `[data-page-number="${target}"]`,
            )
            if (el) {
                container.scrollTo({ top: el.offsetTop - 12, behavior: 'smooth' })
            }
        },
        [pageCount],
    )

    // React to citation jumps from the analysis pane
    useEffect(() => {
        if (!jumpRequest) return
        setHighlight(jumpRequest.highlightText)
        goToPage(jumpRequest.page)
    }, [jumpRequest, goToPage])

    // Scroll-spy: keep the page indicator in sync while scrolling
    const handleScroll = useCallback(() => {
        const container = containerRef.current
        if (!container) return
        const marker = container.scrollTop + 96
        let current = 1
        container.querySelectorAll<HTMLElement>('[data-page-number]').forEach(el => {
            if (el.offsetTop <= marker) current = Number(el.dataset.pageNumber)
        })
        setCurrentPage(current)
    }, [])

    const pageOptions = useMemo(
        () => Array.from({ length: pageCount }, (_, i) => i + 1),
        [pageCount],
    )

    return (
        <div className="card flex h-full min-h-[560px] flex-col overflow-hidden">
            {/* Toolbar */}
            <div className="flex flex-wrap items-center gap-2 border-b border-ink-100 bg-white/90 px-4 py-2.5 backdrop-blur">
                <p className="mr-auto flex min-w-0 items-center gap-2 text-[12.5px] font-semibold text-ink-600">
                    <FileText size={14} className="shrink-0 text-indigo-400" />
                    <span className="truncate">{filename}</span>
                </p>

                {highlight && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 ring-1 ring-inset ring-amber-600/20">
                        <Highlighter size={11} />
                        Highlighted
                        <button
                            type="button"
                            aria-label="Clear highlight"
                            onClick={() => setHighlight(null)}
                            className="ml-0.5 rounded-full p-0.5 transition-colors hover:bg-amber-100"
                        >
                            <X size={10.5} />
                        </button>
                    </span>
                )}

                <div className="flex items-center gap-1">
                    <button
                        type="button"
                        aria-label="Previous page"
                        disabled={currentPage <= 1 || pageCount === 0}
                        onClick={() => goToPage(currentPage - 1)}
                        className="btn-ghost h-8 w-8 rounded-lg border border-ink-100 p-0"
                    >
                        <ChevronLeft size={15} />
                    </button>
                    <select
                        aria-label="Go to page"
                        value={currentPage}
                        disabled={pageCount === 0}
                        onChange={e => goToPage(Number(e.target.value))}
                        className="h-8 rounded-lg border border-ink-100 bg-white px-2 text-[12.5px] font-semibold text-ink-700 shadow-[0_1px_2px_rgba(12,21,38,0.04)] focus:outline-none"
                    >
                        {pageOptions.map(n => (
                            <option key={n} value={n}>
                                Page {n}
                            </option>
                        ))}
                    </select>
                    <span className="text-[12px] font-medium text-ink-400">
                        / {pageCount || '—'}
                    </span>
                    <button
                        type="button"
                        aria-label="Next page"
                        disabled={currentPage >= pageCount || pageCount === 0}
                        onClick={() => goToPage(currentPage + 1)}
                        className="btn-ghost h-8 w-8 rounded-lg border border-ink-100 p-0"
                    >
                        <ChevronRight size={15} />
                    </button>
                </div>
            </div>

            {/* Pages */}
            <div
                ref={containerRef}
                onScroll={handleScroll}
                className="relative flex-1 overflow-y-auto bg-ink-50/70 p-4"
            >
                {loading && (
                    <div className="mx-auto max-w-[640px] space-y-4">
                        {[0, 1].map(i => (
                            <div key={i} className="rounded-xl bg-white p-8 shadow-soft">
                                <div className="skeleton mb-4 h-3.5 w-1/4" />
                                <div className="space-y-2.5">
                                    <div className="skeleton h-3 w-full" />
                                    <div className="skeleton h-3 w-11/12" />
                                    <div className="skeleton h-3 w-4/5" />
                                    <div className="skeleton h-3 w-full" />
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {!loading && (!text || text.pages.length === 0) && (
                    <div className="flex h-full flex-col items-center justify-center gap-3 py-16 text-center">
                        <Loader2 size={22} className="animate-spin text-indigo-300" />
                        <p className="text-[13.5px] text-ink-400">
                            Document text will appear here once parsing completes.
                        </p>
                    </div>
                )}

                {!loading && text && text.pages.length > 0 && (
                    <div className="mx-auto max-w-[640px] space-y-5">
                        {text.pages.map(page => (
                            <article
                                key={page.page_number}
                                id={pageAnchor(page.page_number)}
                                data-page-number={page.page_number}
                                className={cn(
                                    'relative rounded-xl bg-white px-7 py-8 shadow-soft ring-1 ring-ink-100/60 transition-shadow',
                                    currentPage === page.page_number &&
                                        'ring-indigo-200',
                                )}
                            >
                                <header className="mb-4 flex items-center justify-between">
                                    <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-300">
                                        Page {page.page_number}
                                        {pageCount > 0 &&
                                            ` of ${pageCount}`}
                                    </span>
                                    <span className="h-px flex-1 ml-4 bg-gradient-to-r from-ink-100 to-transparent" />
                                </header>
                                <div className="space-y-4">
                                    {page.blocks.map(block => (
                                        <div key={block.chunk_index}>
                                            {block.section_heading && (
                                                <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.14em] text-indigo-400/80">
                                                    {block.section_heading}
                                                </p>
                                            )}
                                            <p className="whitespace-pre-wrap text-[13.5px] leading-[1.75] text-ink-700">
                                                <HighlightedText
                                                    text={block.text}
                                                    needle={highlight}
                                                />
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </article>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
