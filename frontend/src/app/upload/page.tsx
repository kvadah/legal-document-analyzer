'use client'

import { useCallback, useRef, useState } from 'react'
import {
    UploadCloud,
    FileText,
    Loader2,
    AlertCircle,
    Copy,
    FileWarning,
    CheckCircle2,
    Sparkles,
} from 'lucide-react'
import AppLayout from '@/app/app-layout'
import { apiUploadDocuments, type UploadDocumentResult } from '@/lib/api-client'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { cn } from '@/lib/cn'

const ACCEPTED = ['.pdf', '.doc', '.docx', '.txt', '.rtf']
const PIPELINE_HINTS = [
    { icon: FileText, label: 'OCR + parsing' },
    { icon: Sparkles, label: 'AI analysis' },
    { icon: CheckCircle2, label: 'Risk report' },
]

export default function UploadPage() {
    const inputRef = useRef<HTMLInputElement>(null)
    const [uploads, setUploads] = useState<UploadDocumentResult[]>([])
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)
    const [isDragging, setIsDragging] = useState(false)

    const handleFiles = useCallback(async (fileList: FileList | File[] | null) => {
        const files = fileList ? Array.from(fileList) : []
        if (!files.length) return
        setError(null)
        setLoading(true)
        try {
            const results = await apiUploadDocuments(files)
            setUploads(prev => [...results.documents, ...prev])
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed')
        } finally {
            setLoading(false)
        }
    }, [])

    return (
        <AppLayout>
            <div className="mx-auto max-w-3xl space-y-6">
                <PageHeader
                    eyebrow="Ingestion"
                    title="Upload documents"
                    description="Drop contracts in and let the pipeline handle OCR, parsing, embeddings, and AI analysis."
                />

                {/* Dropzone */}
                <div
                    role="button"
                    tabIndex={0}
                    aria-label="Upload files"
                    onClick={() => !loading && inputRef.current?.click()}
                    onKeyDown={e => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            if (!loading) inputRef.current?.click()
                        }
                    }}
                    onDragOver={e => {
                        e.preventDefault()
                        setIsDragging(true)
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={e => {
                        e.preventDefault()
                        setIsDragging(false)
                        void handleFiles(e.dataTransfer.files)
                    }}
                    className={cn(
                        'group animate-fade-up relative cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-300',
                        isDragging
                            ? 'scale-[1.01] border-indigo-400 bg-indigo-50/60 shadow-glow'
                            : 'border-ink-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/30',
                        loading && 'pointer-events-none opacity-70',
                    )}
                >
                    <div className="bg-grid mask-fade-b pointer-events-none absolute inset-0 opacity-50" />
                    <div className="relative">
                        <div
                            className={cn(
                                'mx-auto flex h-20 w-20 items-center justify-center rounded-2xl transition-all duration-300',
                                isDragging
                                    ? 'bg-gradient-to-b from-indigo-500 to-violet-600 text-white shadow-glow'
                                    : 'bg-gradient-to-b from-ink-50 to-ink-100 text-ink-400 group-hover:from-indigo-50 group-hover:to-violet-100 group-hover:text-indigo-500',
                            )}
                        >
                            {loading ? (
                                <Loader2 size={30} className="animate-spin" />
                            ) : (
                                <UploadCloud
                                    size={30}
                                    strokeWidth={1.7}
                                    className="group-hover:-translate-y-0.5 transition-transform duration-300"
                                />
                            )}
                        </div>

                        <h3 className="mt-6 font-display text-[20px] font-semibold text-ink-900">
                            {loading
                                ? 'Uploading & queueing analysis…'
                                : isDragging
                                  ? 'Release to upload'
                                  : 'Drop files here, or click to browse'}
                        </h3>
                        <p className="mt-2 text-[13.5px] text-ink-500">
                            PDF, DOCX, TXT and RTF — up to 50&nbsp;MB each, multiple files welcome.
                        </p>

                        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
                            {PIPELINE_HINTS.map((hint, i) => (
                                <span key={hint.label} className="flex items-center gap-2">
                                    {i > 0 && <span className="text-ink-200">→</span>}
                                    <span className="inline-flex items-center gap-1.5 rounded-full border border-ink-100 bg-white px-3 py-1 text-[11.5px] font-medium text-ink-500">
                                        <hint.icon size={12} className="text-indigo-400" />
                                        {hint.label}
                                    </span>
                                </span>
                            ))}
                        </div>

                        <input
                            ref={inputRef}
                            type="file"
                            multiple
                            accept={ACCEPTED.join(',')}
                            className="hidden"
                            onChange={e => {
                                void handleFiles(e.target.files)
                                e.target.value = ''
                            }}
                        />
                    </div>
                </div>

                {error && (
                    <div
                        className="animate-scale-in flex items-start gap-3 rounded-xl border border-rose-200/80 bg-rose-50 px-5 py-4 text-[13.5px] text-rose-700"
                        role="alert"
                    >
                        <AlertCircle size={17} className="mt-0.5 shrink-0" />
                        {error}
                    </div>
                )}

                {/* Recent uploads */}
                {uploads.length > 0 && (
                    <div className="card animate-fade-up overflow-hidden">
                        <div className="flex items-center justify-between border-b border-ink-100 bg-ink-50/50 px-6 py-4">
                            <h2 className="text-[14px] font-bold uppercase tracking-[0.1em] text-ink-500">
                                Recent uploads
                            </h2>
                            <span className="pill bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-500/15">
                                {uploads.length} file{uploads.length !== 1 ? 's' : ''}
                            </span>
                        </div>
                        <ul className="divide-y divide-ink-50">
                            {uploads.map(upload => (
                                <li
                                    key={`${upload.document_id}-${upload.filename}`}
                                    className="flex items-center gap-4 px-6 py-4"
                                >
                                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-500 ring-1 ring-inset ring-indigo-100">
                                        <FileText size={17} />
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <p className="truncate text-[14px] font-semibold text-ink-900">
                                            {upload.filename}
                                        </p>
                                        {upload.possible_duplicate_of ? (
                                            <p className="mt-0.5 flex items-center gap-1.5 text-[12px] text-gold-700">
                                                <Copy size={11} />
                                                Possible duplicate of an existing document
                                            </p>
                                        ) : (
                                            <p className="mt-0.5 flex items-center gap-1.5 text-[12px] text-ink-400">
                                                <FileWarning size={11} className="opacity-0" />
                                                Queued for processing
                                            </p>
                                        )}
                                    </div>
                                    <StatusBadge status={upload.status} />
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </AppLayout>
    )
}
