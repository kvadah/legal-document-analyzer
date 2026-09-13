'use client'

/**
 * Document viewer pane — renders the extracted/OCR'd text page by page with
 * page navigation, and supports jump-to-page + highlight-span driven by
 * CitationLink clicks from the analysis tabs (10-frontend-spec.md §4).
 *
 * Collaboration layer (08-feature-spec-collaboration.md §6): selecting text
 * offers a highlight popover (color + optional note) that creates an
 * annotation; saved annotations render as colored highlights in the text,
 * and a toggleable panel lists them with color/author filters and
 * click-to-navigate.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
    ChevronLeft,
    ChevronRight,
    FileText,
    Highlighter,
    Loader2,
    MessageSquareQuote,
    X,
} from 'lucide-react'
import {
    apiCreateAnnotation,
    apiDeleteAnnotation,
    apiListAnnotations,
    type AnnotationColor,
    type AnnotationOut,
    type DocumentTextResponse,
} from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/cn'

export interface JumpRequest {
    page: number
    highlightText: string | null
    nonce: number
}

const COLOR_CLASSES: Record<AnnotationColor, string> = {
    yellow: 'bg-amber-200/80 text-ink-900',
    green: 'bg-emerald-200/80 text-ink-900',
    blue: 'bg-sky-200/80 text-ink-900',
    red: 'bg-rose-200/80 text-ink-900',
    purple: 'bg-violet-200/80 text-ink-900',
}

const COLOR_DOTS: Record<AnnotationColor, string> = {
    yellow: 'bg-amber-300',
    green: 'bg-emerald-400',
    blue: 'bg-sky-400',
    red: 'bg-rose-400',
    purple: 'bg-violet-400',
}

const ALL_COLORS = Object.keys(COLOR_CLASSES) as AnnotationColor[]

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

interface TextSpan {
    start: number
    end: number
    className: string
    annotationId?: string
}

/** Merge citation needle + annotation quotes into non-overlapping spans. */
function computeSpans(
    text: string,
    annotations: AnnotationOut[],
    needle: string | null,
): TextSpan[] {
    const spans: TextSpan[] = []
    for (const annotation of annotations) {
        const range = findHighlightRange(text, annotation.highlight_text)
        if (range) {
            spans.push({
                start: range.start,
                end: range.start + range.length,
                className: COLOR_CLASSES[annotation.color],
                annotationId: annotation.id,
            })
        }
    }
    if (needle) {
        const range = findHighlightRange(text, needle)
        if (range) {
            spans.push({
                start: range.start,
                end: range.start + range.length,
                className: 'rounded bg-amber-300/90 px-0.5 text-ink-900 ring-1 ring-amber-500/40',
            })
        }
    }
    spans.sort((a, b) => a.start - b.start)
    const merged: TextSpan[] = []
    for (const span of spans) {
        if (merged.length && span.start < merged[merged.length - 1].end) continue
        merged.push(span)
    }
    return merged
}

function SpannedText({
    text,
    spans,
}: {
    text: string
    spans: TextSpan[]
}) {
    if (spans.length === 0) return <>{text}</>
    const parts: React.ReactNode[] = []
    let cursor = 0
    spans.forEach((span, i) => {
        if (span.start > cursor) {
            parts.push(<span key={`t${i}`}>{text.slice(cursor, span.start)}</span>)
        }
        parts.push(
            <mark
                key={`m${i}`}
                data-annotation-id={span.annotationId}
                className={cn('rounded px-0.5', span.className)}
            >
                {text.slice(span.start, span.end)}
            </mark>,
        )
        cursor = span.end
    })
    if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>)
    return <>{parts}</>
}

function pageAnchor(page: number) {
    return `doc-viewer-page-${page}`
}

interface SelectionState {
    quote: string
    pageNumber: number
    top: number
    left: number
}

function authorLabel(annotation: AnnotationOut): string {
    return annotation.author_name ?? annotation.author_email.split('@')[0]
}

export default function DocumentViewer({
    documentId,
    text,
    filename,
    jumpRequest,
    loading,
}: {
    documentId: string
    text: DocumentTextResponse | null
    filename: string
    jumpRequest: JumpRequest | null
    loading: boolean
}) {
    const { user } = useAuth()
    const canAnnotate = user?.role === 'admin' || user?.role === 'reviewer'

    const containerRef = useRef<HTMLDivElement>(null)
    const [currentPage, setCurrentPage] = useState(1)
    const [highlight, setHighlight] = useState<string | null>(null)

    const [annotations, setAnnotations] = useState<AnnotationOut[] | null>(null)
    const [panelOpen, setPanelOpen] = useState(false)
    const [colorFilter, setColorFilter] = useState<string>('all')
    const [authorFilter, setAuthorFilter] = useState<string>('all')
    const [selection, setSelection] = useState<SelectionState | null>(null)
    const [noteDraft, setNoteDraft] = useState('')
    const [pendingColor, setPendingColor] = useState<AnnotationColor>('yellow')
    const [saving, setSaving] = useState(false)

    const pageCount = text?.page_count ?? text?.pages.length ?? 0

    const loadAnnotations = useCallback(async () => {
        try {
            const data = await apiListAnnotations(documentId)
            setAnnotations(data.annotations)
        } catch {
            setAnnotations([])
        }
    }, [documentId])

    useEffect(() => {
        void loadAnnotations()
    }, [loadAnnotations])

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

    // ── Text selection → annotation capture ────────────────────────────────
    const handleMouseUp = useCallback(() => {
        if (!canAnnotate) return
        const active = window.getSelection()
        if (!active || active.isCollapsed || active.rangeCount === 0) {
            return
        }
        const range = active.getRangeAt(0)
        const startParent = range.startContainer.parentElement
        const blockEl = startParent?.closest('[data-block-index]') ?? null
        const pageEl = startParent?.closest('[data-page-number]') ?? null
        if (!blockEl || !pageEl) return

        // Clip the selection to the containing block so the stored quote is
        // always findable within a single block for highlight rendering.
        const clipped = document.createRange()
        clipped.selectNodeContents(blockEl)
        try {
            clipped.setStart(range.startContainer, range.startOffset)
            if (blockEl.contains(range.endContainer)) {
                clipped.setEnd(range.endContainer, range.endOffset)
            }
        } catch {
            return
        }
        const quote = clipped.toString().trim()
        if (quote.length < 2) return

        const rect = range.getBoundingClientRect()
        setSelection({
            quote,
            pageNumber: Number(pageEl.getAttribute('data-page-number')),
            top: rect.bottom + window.scrollY + 8,
            left: Math.max(12, rect.left + window.scrollX),
        })
        setNoteDraft('')
        setPendingColor('yellow')
    }, [canAnnotate])

    const closeSelection = useCallback(() => setSelection(null), [])

    useEffect(() => {
        if (!selection) return
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') closeSelection()
        }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [selection, closeSelection])

    const saveAnnotation = useCallback(async () => {
        if (!selection || saving) return
        setSaving(true)
        try {
            await apiCreateAnnotation(documentId, {
                highlight_text: selection.quote,
                content: noteDraft.trim(),
                color: pendingColor,
                page_number: selection.pageNumber,
            })
            window.getSelection()?.removeAllRanges()
            closeSelection()
            await loadAnnotations()
        } catch {
            closeSelection()
        } finally {
            setSaving(false)
        }
    }, [
        closeSelection,
        documentId,
        loadAnnotations,
        noteDraft,
        pendingColor,
        saving,
        selection,
    ])

    const removeAnnotation = useCallback(
        async (annotation: AnnotationOut) => {
            try {
                await apiDeleteAnnotation(annotation.id)
                await loadAnnotations()
            } catch {
                /* refetch keeps state honest */
            }
        },
        [loadAnnotations],
    )

    // ── Annotations panel ───────────────────────────────────────────────────
    const authors = useMemo(
        () => Array.from(new Set((annotations ?? []).map(a => a.author_email))).sort(),
        [annotations],
    )
    const visibleAnnotations = useMemo(
        () =>
            (annotations ?? []).filter(
                a =>
                    (colorFilter === 'all' || a.color === colorFilter) &&
                    (authorFilter === 'all' || a.author_email === authorFilter),
            ),
        [annotations, authorFilter, colorFilter],
    )

    const annotationsByPage = useMemo(() => {
        const map = new Map<number, AnnotationOut[]>()
        for (const a of annotations ?? []) {
            const list = map.get(a.page_number) ?? []
            list.push(a)
            map.set(a.page_number, list)
        }
        return map
    }, [annotations])

    const jumpToAnnotation = useCallback(
        (annotation: AnnotationOut) => {
            setHighlight(annotation.highlight_text)
            goToPage(annotation.page_number)
        },
        [goToPage],
    )

    const pageOptions = useMemo(
        () => Array.from({ length: pageCount }, (_, i) => i + 1),
        [pageCount],
    )

    return (
        <div className="card relative flex h-full min-h-[560px] flex-col overflow-hidden">
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

                <button
                    type="button"
                    onClick={() => setPanelOpen(!panelOpen)}
                    aria-pressed={panelOpen}
                    title="Annotations"
                    className={cn(
                        'relative flex h-8 w-8 items-center justify-center rounded-lg border transition-colors',
                        panelOpen
                            ? 'border-indigo-200 bg-indigo-50 text-indigo-600'
                            : 'border-ink-100 bg-white text-ink-400 hover:text-ink-700',
                    )}
                >
                    <Highlighter size={15} />
                    {annotations != null && annotations.length > 0 && (
                        <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-indigo-500 px-1 text-[9.5px] font-bold text-white">
                            {annotations.length}
                        </span>
                    )}
                </button>

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

            {/* Annotations panel (08 §6 — filterable by color/author) */}
            {panelOpen && (
                <div className="absolute inset-y-0 right-0 z-20 flex w-72 flex-col border-l border-ink-100 bg-white/95 shadow-lift backdrop-blur">
                    <div className="flex items-center justify-between border-b border-ink-100 px-3.5 py-2.5">
                        <p className="flex items-center gap-1.5 text-[11.5px] font-bold uppercase tracking-[0.12em] text-ink-500">
                            <MessageSquareQuote size={13} className="text-indigo-400" />
                            Annotations
                        </p>
                        <button
                            type="button"
                            onClick={() => setPanelOpen(false)}
                            aria-label="Close annotations panel"
                            className="rounded-md p-1 text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-700"
                        >
                            <X size={14} />
                        </button>
                    </div>
                    <div className="grid grid-cols-2 gap-2 border-b border-ink-50 px-3 py-2.5">
                        <select
                            value={colorFilter}
                            onChange={e => setColorFilter(e.target.value)}
                            aria-label="Filter annotations by color"
                            className="rounded-lg border border-ink-100 bg-white px-2 py-1.5 text-[11.5px] text-ink-700 focus:outline-none"
                        >
                            <option value="all">All colors</option>
                            {ALL_COLORS.map(color => (
                                <option key={color} value={color}>
                                    {color[0].toUpperCase() + color.slice(1)}
                                </option>
                            ))}
                        </select>
                        <select
                            value={authorFilter}
                            onChange={e => setAuthorFilter(e.target.value)}
                            aria-label="Filter annotations by author"
                            className="rounded-lg border border-ink-100 bg-white px-2 py-1.5 text-[11.5px] text-ink-700 focus:outline-none"
                        >
                            <option value="all">All authors</option>
                            {authors.map(email => (
                                <option key={email} value={email}>
                                    {email.split('@')[0]}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="min-h-0 flex-1 overflow-y-auto p-2">
                        {annotations === null && (
                            <div className="flex items-center justify-center gap-2 py-8 text-[12px] text-ink-400">
                                <Loader2 size={13} className="animate-spin" />
                                Loading…
                            </div>
                        )}
                        {annotations != null && annotations.length === 0 && (
                            <p className="px-2 py-8 text-center text-[12px] leading-relaxed text-ink-400">
                                {canAnnotate
                                    ? 'Select text in the document to create a highlight annotation.'
                                    : 'No annotations yet.'}
                            </p>
                        )}
                        {annotations != null && annotations.length > 0 && visibleAnnotations.length === 0 && (
                            <p className="px-2 py-8 text-center text-[12px] text-ink-400">
                                No annotations match the filters.
                            </p>
                        )}
                        <ul className="space-y-1.5">
                            {visibleAnnotations.map(annotation => (
                                <li key={annotation.id}>
                                    <div className="group rounded-lg border border-ink-100 bg-white px-2.5 py-2 transition-colors hover:border-indigo-200">
                                        <button
                                            type="button"
                                            onClick={() => jumpToAnnotation(annotation)}
                                            className="w-full text-left"
                                            title="Jump to this highlight"
                                        >
                                            <span className="flex items-center gap-1.5">
                                                <span
                                                    className={cn(
                                                        'h-2.5 w-2.5 shrink-0 rounded-full',
                                                        COLOR_DOTS[annotation.color],
                                                    )}
                                                />
                                                <span className="truncate text-[11px] font-semibold text-ink-500">
                                                    {authorLabel(annotation)} · p.
                                                    {annotation.page_number}
                                                </span>
                                            </span>
                                            <span className="mt-1 block line-clamp-2 text-[12px] leading-snug text-ink-700">
                                                “{annotation.highlight_text}”
                                            </span>
                                            {annotation.content && (
                                                <span className="mt-1 block truncate text-[11.5px] italic text-ink-400">
                                                    {annotation.content}
                                                </span>
                                            )}
                                        </button>
                                        {(annotation.user_id === user?.id ||
                                            user?.role === 'admin') && (
                                            <button
                                                type="button"
                                                onClick={() => void removeAnnotation(annotation)}
                                                aria-label="Delete annotation"
                                                className="mt-1 flex items-center gap-1 text-[10.5px] font-medium text-ink-300 opacity-0 transition-all hover:text-rose-500 group-hover:opacity-100"
                                            >
                                                <X size={10} />
                                                Remove
                                            </button>
                                        )}
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}

            {/* Pages */}
            <div
                ref={containerRef}
                onScroll={handleScroll}
                onMouseUp={handleMouseUp}
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
                        {text.pages.map(page => {
                            const pageAnnotations = annotationsByPage.get(page.page_number) ?? []
                            return (
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
                                            <div key={block.chunk_index} data-block-index={block.chunk_index}>
                                                {block.section_heading && (
                                                    <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.14em] text-indigo-400/80">
                                                        {block.section_heading}
                                                    </p>
                                                )}
                                                <p className="whitespace-pre-wrap text-[13.5px] leading-[1.75] text-ink-700">
                                                    <SpannedText
                                                        text={block.text}
                                                        spans={computeSpans(
                                                            block.text,
                                                            pageAnnotations,
                                                            highlight,
                                                        )}
                                                    />
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                </article>
                            )
                        })}
                    </div>
                )}
            </div>

            {/* Selection → annotation popover */}
            {selection && (
                <>
                    <div
                        className="fixed inset-0 z-40"
                        onClick={closeSelection}
                        aria-hidden
                    />
                    <div
                        role="dialog"
                        aria-label="Create annotation"
                        style={{ position: 'fixed', top: selection.top, left: selection.left }}
                        className="z-50 w-72 rounded-xl border border-ink-100 bg-white p-3 shadow-lift"
                    >
                        <p className="mb-2 text-[10.5px] font-bold uppercase tracking-[0.14em] text-ink-400">
                            Highlight · p.{selection.pageNumber}
                        </p>
                        <p className="mb-2.5 line-clamp-2 rounded-lg bg-ink-50 px-2 py-1.5 text-[11.5px] leading-snug text-ink-600">
                            “{selection.quote}”
                        </p>
                        <div className="mb-2.5 flex items-center gap-1.5">
                            {ALL_COLORS.map(color => (
                                <button
                                    key={color}
                                    type="button"
                                    aria-label={`Highlight color ${color}`}
                                    aria-pressed={pendingColor === color}
                                    onClick={() => setPendingColor(color)}
                                    className={cn(
                                        'flex h-6 w-6 items-center justify-center rounded-full transition-transform hover:scale-110',
                                        pendingColor === color &&
                                            'ring-2 ring-ink-800 ring-offset-2',
                                    )}
                                >
                                    <span
                                        className={cn(
                                            'h-[18px] w-[18px] rounded-full',
                                            COLOR_DOTS[color],
                                        )}
                                    />
                                </button>
                            ))}
                        </div>
                        <input
                            type="text"
                            value={noteDraft}
                            onChange={e => setNoteDraft(e.target.value)}
                            placeholder="Optional note…"
                            maxLength={500}
                            className="field mb-2.5 px-2.5 py-1.5 text-[12px]"
                        />
                        <div className="flex items-center justify-end gap-2">
                            <button
                                type="button"
                                onClick={closeSelection}
                                className="btn-ghost px-2.5 py-1.5 text-[12px]"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={() => void saveAnnotation()}
                                disabled={saving}
                                className="btn-primary px-3 py-1.5 text-[12px]"
                            >
                                {saving ? (
                                    <Loader2 size={13} className="animate-spin" />
                                ) : (
                                    <Highlighter size={13} />
                                )}
                                Save
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
