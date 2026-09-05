'use client'

/**
 * Export action for the Analysis view (10-frontend-spec.md §4): format
 * picker (PDF / Word / JSON) that downloads the document's analysis report.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Download, FileJson, FileText, Loader2 } from 'lucide-react'
import {
    apiExportDocument,
    downloadBlob,
    type ExportFormat,
} from '@/lib/api-client'
import { cn } from '@/lib/cn'

const FORMATS: { id: ExportFormat; label: string; hint: string; icon: typeof FileText }[] = [
    { id: 'pdf', label: 'PDF', hint: 'Printable report', icon: FileText },
    { id: 'docx', label: 'Word', hint: 'Editable document', icon: FileText },
    { id: 'json', label: 'JSON', hint: 'Raw structured data', icon: FileJson },
]

export default function ExportMenu({ documentId }: { documentId: string }) {
    const [open, setOpen] = useState(false)
    const [downloading, setDownloading] = useState<ExportFormat | null>(null)
    const [done, setDone] = useState<ExportFormat | null>(null)
    const [error, setError] = useState<string | null>(null)
    const rootRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        function onDocClick(e: MouseEvent) {
            if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
        }
        if (open) document.addEventListener('mousedown', onDocClick)
        return () => document.removeEventListener('mousedown', onDocClick)
    }, [open])

    const download = useCallback(
        async (format: ExportFormat) => {
            setDownloading(format)
            setError(null)
            try {
                const { blob, filename } = await apiExportDocument(documentId, format)
                downloadBlob(blob, filename)
                setDone(format)
                setTimeout(() => setDone(null), 2500)
                setOpen(false)
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Export failed')
            } finally {
                setDownloading(null)
            }
        },
        [documentId],
    )

    return (
        <div ref={rootRef} className="relative">
            <button
                type="button"
                onClick={() => setOpen(v => !v)}
                aria-haspopup="menu"
                aria-expanded={open}
                disabled={downloading !== null}
                className="btn-secondary px-3.5 py-2 text-[12.5px]"
            >
                {downloading ? (
                    <Loader2 size={14} className="animate-spin" />
                ) : done ? (
                    <Check size={14} className="text-emerald-600" />
                ) : (
                    <Download size={14} />
                )}
                {downloading ? 'Preparing…' : done ? 'Downloaded' : 'Export'}
                <ChevronDown
                    size={13}
                    className={cn('transition-transform duration-200', open && 'rotate-180')}
                />
            </button>

            {error && (
                <p className="absolute right-0 top-full z-20 mt-1.5 w-56 rounded-lg bg-rose-50 px-3 py-2 text-[12px] text-rose-700 ring-1 ring-rose-200">
                    {error}
                </p>
            )}

            {open && (
                <div
                    role="menu"
                    className="animate-scale-in absolute right-0 top-full z-20 mt-1.5 w-52 overflow-hidden rounded-xl border border-ink-100 bg-white shadow-lift"
                >
                    <p className="border-b border-ink-50 bg-ink-50/60 px-4 py-2 text-[10.5px] font-bold uppercase tracking-[0.14em] text-ink-400">
                        Export analysis
                    </p>
                    {FORMATS.map(format => {
                        const Icon = format.icon
                        return (
                            <button
                                key={format.id}
                                role="menuitem"
                                type="button"
                                onClick={() => void download(format.id)}
                                disabled={downloading !== null}
                                className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-indigo-50/50 disabled:opacity-60"
                            >
                                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-500">
                                    {downloading === format.id ? (
                                        <Loader2 size={13} className="animate-spin" />
                                    ) : (
                                        <Icon size={13} />
                                    )}
                                </span>
                                <span className="min-w-0 flex-1">
                                    <span className="block text-[13px] font-semibold text-ink-800">
                                        {format.label}
                                    </span>
                                    <span className="block text-[11px] text-ink-400">
                                        {format.hint}
                                    </span>
                                </span>
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
