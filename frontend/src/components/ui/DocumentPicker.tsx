'use client'

/**
 * Reusable document pickers (Phase 7).
 * - DocumentSelect: single-select dropdown with filename filter.
 * - DocumentMultiSelect: checkbox list with filename filter.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, FileText, Search, X } from 'lucide-react'
import { DocumentOut } from '@/lib/api-client'
import { docTypeMeta } from '@/lib/format'
import { cn } from '@/lib/cn'

function useClickOutside(onOutside: () => void) {
    const ref = useRef<HTMLDivElement>(null)
    useEffect(() => {
        const onClick = (e: MouseEvent) => {
            if (!ref.current?.contains(e.target as Node)) onOutside()
        }
        document.addEventListener('mousedown', onClick)
        return () => document.removeEventListener('mousedown', onClick)
    }, [onOutside])
    return ref
}

function useFilteredDocuments(documents: DocumentOut[], query: string) {
    return useMemo(() => {
        const q = query.trim().toLowerCase()
        return q ? documents.filter(d => d.filename.toLowerCase().includes(q)) : documents
    }, [documents, query])
}

export function DocumentSelect({
    documents,
    selectedId,
    onSelect,
    placeholder = 'Search documents…',
}: {
    documents: DocumentOut[]
    selectedId: string | null
    onSelect: (id: string | null) => void
    placeholder?: string
}) {
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState('')
    const ref = useClickOutside(() => setOpen(false))

    const selected = documents.find(d => d.id === selectedId) ?? null
    const filtered = useFilteredDocuments(documents, query)

    return (
        <div ref={ref} className="relative">
            <button
                type="button"
                onClick={() => setOpen(!open)}
                className="flex w-full items-center gap-2.5 rounded-xl border border-ink-200 bg-white px-4 py-3 text-left shadow-soft transition-colors hover:border-primary/40"
            >
                <Search size={15} className="shrink-0 text-ink-300" />
                {selected ? (
                    <span className="min-w-0 truncate text-[14px] font-medium text-ink-800">
                        {selected.filename}
                    </span>
                ) : (
                    <span className="text-[14px] text-ink-400">{placeholder}</span>
                )}
                <ChevronDown
                    size={15}
                    className={cn(
                        'ml-auto shrink-0 text-ink-300 transition-transform',
                        open && 'rotate-180',
                    )}
                />
            </button>

            {open && (
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
                                    type="button"
                                    onClick={() => {
                                        onSelect(doc.id)
                                        setOpen(false)
                                        setQuery('')
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

export function DocumentMultiSelect({
    documents,
    selectedIds,
    onToggle,
}: {
    documents: DocumentOut[]
    selectedIds: string[]
    onToggle: (id: string) => void
}) {
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState('')
    const ref = useClickOutside(() => setOpen(false))

    const filtered = useFilteredDocuments(documents, query)
    const selectedCount = selectedIds.length

    return (
        <div ref={ref} className="relative">
            <button
                type="button"
                onClick={() => setOpen(!open)}
                className="flex w-full items-center gap-2.5 rounded-xl border border-ink-200 bg-white px-4 py-2.5 text-left shadow-soft transition-colors hover:border-primary/40"
            >
                <span className="text-[13.5px] font-medium text-ink-700">
                    {selectedCount === 0
                        ? 'All documents'
                        : `${selectedCount} document${selectedCount === 1 ? '' : 's'} selected`}
                </span>
                {selectedCount > 0 && (
                    <button
                        type="button"
                        onClick={e => {
                            e.stopPropagation()
                            for (const id of selectedIds) onToggle(id)
                        }}
                        className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] font-medium text-ink-400 transition-colors hover:bg-ink-50 hover:text-ink-700"
                    >
                        <X size={11} /> Clear
                    </button>
                )}
                <ChevronDown
                    size={15}
                    className={cn(
                        'ml-auto shrink-0 text-ink-300 transition-transform',
                        open && 'rotate-180',
                    )}
                />
            </button>

            {open && (
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
                            filtered.map(doc => {
                                const checked = selectedIds.includes(doc.id)
                                return (
                                    <button
                                        key={doc.id}
                                        type="button"
                                        onClick={() => onToggle(doc.id)}
                                        className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-indigo-50/70"
                                    >
                                        <span
                                            className={cn(
                                                'flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors',
                                                checked
                                                    ? 'border-primary bg-primary text-white'
                                                    : 'border-ink-300 bg-white',
                                            )}
                                        >
                                            {checked && <Check size={11} strokeWidth={3} />}
                                        </span>
                                        <span className="truncate text-[13.5px] font-medium text-ink-700">
                                            {doc.filename}
                                        </span>
                                        <span className="ml-auto shrink-0 text-[11.5px] text-ink-400">
                                            {docTypeMeta(doc.document_type).label}
                                        </span>
                                    </button>
                                )
                            })
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
