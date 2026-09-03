/**
 * Shared formatting helpers and status/type metadata for documents.
 */

export function formatBytes(bytes: number): string {
    if (!bytes || bytes <= 0) return '—'
    const units = ['B', 'KB', 'MB', 'GB']
    let value = bytes
    let unit = 0
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024
        unit++
    }
    return `${value >= 100 || unit === 0 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`
}

export function timeAgo(iso: string): string {
    const then = new Date(iso).getTime()
    if (Number.isNaN(then)) return ''
    const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000))
    if (seconds < 60) return 'just now'
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    if (days < 30) return `${days}d ago`
    return new Date(iso).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    })
}

export type StatusTone = 'success' | 'processing' | 'error' | 'neutral'

export interface StatusMeta {
    label: string
    tone: StatusTone
    /** true when the document is still moving through the pipeline */
    busy: boolean
}

const STATUS_MAP: Record<string, StatusMeta> = {
    uploaded: { label: 'Queued', tone: 'processing', busy: true },
    ocr_processing: { label: 'Running OCR', tone: 'processing', busy: true },
    ocr_complete: { label: 'OCR complete', tone: 'processing', busy: true },
    parsing: { label: 'Parsing', tone: 'processing', busy: true },
    chunking: { label: 'Chunking', tone: 'processing', busy: true },
    embedding: { label: 'Embedding', tone: 'processing', busy: true },
    metadata_extraction: { label: 'Extracting metadata', tone: 'processing', busy: true },
    ingestion_ready: { label: 'Ingested', tone: 'neutral', busy: false },
    ai_pipeline_processing: { label: 'AI analysis', tone: 'processing', busy: true },
    analysis_ready: { label: 'Analyzed', tone: 'success', busy: false },
    error: { label: 'Error', tone: 'error', busy: false },
}

export function statusMeta(status: string): StatusMeta {
    return STATUS_MAP[status] ?? { label: status.replace(/_/g, ' '), tone: 'neutral', busy: false }
}

export interface DocTypeMeta {
    label: string
    /** short glyph used inside the file-type tile */
    glyph: string
    tile: string
}

const DOC_TYPES: Record<string, DocTypeMeta> = {
    contract: { label: 'Contract', glyph: 'CT', tile: 'bg-indigo-50 text-indigo-600 ring-indigo-100' },
    nda: { label: 'NDA', glyph: 'NDA', tile: 'bg-violet-50 text-violet-600 ring-violet-100' },
    employment_agreement: { label: 'Employment', glyph: 'EA', tile: 'bg-emerald-50 text-emerald-600 ring-emerald-100' },
    lease: { label: 'Lease', glyph: 'LSE', tile: 'bg-amber-50 text-amber-600 ring-amber-100' },
    procurement: { label: 'Procurement', glyph: 'PRC', tile: 'bg-sky-50 text-sky-600 ring-sky-100' },
    insurance: { label: 'Insurance', glyph: 'INS', tile: 'bg-rose-50 text-rose-600 ring-rose-100' },
    government_form: { label: 'Gov. form', glyph: 'GOV', tile: 'bg-cyan-50 text-cyan-600 ring-cyan-100' },
    policy: { label: 'Policy', glyph: 'POL', tile: 'bg-teal-50 text-teal-600 ring-teal-100' },
    tos: { label: 'Terms of service', glyph: 'TOS', tile: 'bg-fuchsia-50 text-fuchsia-600 ring-fuchsia-100' },
    other: { label: 'Document', glyph: 'DOC', tile: 'bg-ink-100 text-ink-500 ring-ink-200' },
}

export function docTypeMeta(type: string): DocTypeMeta {
    return DOC_TYPES[type] ?? { ...DOC_TYPES.other, label: type.replace(/_/g, ' ') }
}
