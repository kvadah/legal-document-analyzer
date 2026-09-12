'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
    UploadCloud,
    FileText,
    Loader2,
    AlertCircle,
    Copy,
    FileWarning,
    CheckCircle2,
    Sparkles,
    GitBranch,
    ChevronDown,
} from 'lucide-react'
import AppLayout from '@/app/app-layout'
import {
    apiListDocuments,
    apiUploadDocuments,
    apiUploadDocumentVersion,
    type DocumentOut,
    type UploadDocumentResult,
} from '@/lib/api-client'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { DocumentSelect } from '@/components/ui/DocumentPicker'
import { useAuth } from '@/context/AuthContext'
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

    // Version-aware upload (08 §4) — reviewer/admin only (08 §8)
    const { user } = useAuth()
    const canVersion = user?.role === 'admin' || user?.role === 'reviewer'
    const [versionMode, setVersionMode] = useState(false)
    const [versionTarget, setVersionTarget] = useState<string | null>(null)
    const [changeNote, setChangeNote] = useState('')
    const [documents, setDocuments] = useState<DocumentOut[]>([])

    useEffect(() => {
        if (!versionMode) return
        let cancelled = false
        apiListDocuments()
            .then(res => {
                if (!cancelled) setDocuments(res.items)
            })
            .catch(() => {
                /* picker stays empty; upload itself will surface errors */
            })
        return () => {
            cancelled = true
        }
    }, [versionMode])

    const handleFiles = useCallback(
        async (fileList: FileList | File[] | null) => {
            const files = fileList ? Array.from(fileList) : []
            if (!files.length) return
            setError(null)
            setLoading(true)
            try {
                if (versionMode) {
                    if (!versionTarget) {
                        setError('Pick the document this file is a new version of.')
                        return
                    }
                    const result = await apiUploadDocumentVersion(
                        versionTarget,
                        files[0],
                        changeNote.trim() || undefined,
                    )
                    setUploads(prev => [result, ...prev])
                } else {
                    const results = await apiUploadDocuments(files)
                    setUploads(prev => [...results.documents, ...prev])
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Upload failed')
            } finally {
                setLoading(false)
            }
        },
        [versionMode, versionTarget, changeNote],
    )

    return (
        <AppLayout>
            <div className="mx-auto max-w-3xl space-y-6">
                <PageHeader
                    eyebrow="Ingestion"
                    title="Upload documents"
                    description="Drop contracts in and let the pipeline handle OCR, parsing, embeddings, and AI analysis."
                />

                {/* Version-aware upload toggle (08 §4) */}
                {canVersion && (
                    <div className="card overflow-hidden">
                        <button
                            type="button"
                            onClick={() => setVersionMode(!versionMode)}
                            className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-ink-50/60"
                            aria-expanded={versionMode}
                        >
                            <span
                                className={cn(
                                    'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors',
                                    versionMode
                                        ? 'bg-indigo-600 text-white'
                                        : 'bg-indigo-50 text-indigo-500 ring-1 ring-inset ring-indigo-100',
                                )}
                            >
                                <GitBranch size={16} />
                            </span>
                            <div className="min-w-0 flex-1">
                                <p className="text-[14px] font-semibold text-ink-900">
                                    Link as a new version
                                </p>
                                <p className="mt-0.5 text-[12.5px] text-ink-400">
                                    {versionMode
                                        ? 'Single file — uploaded as the next version of the selected document.'
                                        : 'Uploading a revised contract? Link it to the existing document to build a version history.'}
                                </p>
                            </div>
                            <ChevronDown
                                size={16}
                                className={cn(
                                    'shrink-0 text-ink-300 transition-transform',
                                    versionMode && 'rotate-180',
                                )}
                            />
                        </button>

                        {versionMode && (
                            <div className="animate-fade-up space-y-3 border-t border-ink-100 bg-ink-50/40 px-5 py-4">
                                <div>
                                    <p className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-ink-400">
                                        New version of
                                    </p>
                                    <DocumentSelect
                                        documents={documents}
                                        selectedId={versionTarget}
                                        onSelect={setVersionTarget}
                                        placeholder="Search existing documents…"
                                    />
                                </div>
                                <div>
                                    <p className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-ink-400">
                                        Change note <span className="normal-case tracking-normal">(optional)</span>
                                    </p>
                                    <input
                                        type="text"
                                        value={changeNote}
                                        onChange={e => setChangeNote(e.target.value)}
                                        maxLength={500}
                                        placeholder="e.g. Reduced payment fee, shorter payment window"
                                        className="field w-full"
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                )}

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
                            {versionMode
                                ? 'One file — it becomes the next version of the selected document.'
                                : 'PDF, DOCX, TXT and RTF — up to 50\u00A0MB each, multiple files welcome.'}
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
                            multiple={!versionMode}
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
                                            <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[12px] text-gold-700">
                                                <Copy size={11} />
                                                Possible duplicate of an existing document
                                                {canVersion && (
                                                    <>
                                                        {' —'}
                                                        <button
                                                            type="button"
                                                            className="font-semibold underline underline-offset-2 hover:text-gold-800"
                                                            onClick={() => {
                                                                setVersionMode(true)
                                                                setVersionTarget(
                                                                    upload.possible_duplicate_of ?? null,
                                                                )
                                                            }}
                                                        >
                                                            link it as a new version instead
                                                        </button>
                                                    </>
                                                )}
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
