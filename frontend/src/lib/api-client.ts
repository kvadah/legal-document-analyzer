/**
 * Typed API client for the Legal Document Analyzer backend.
 * All requests attach the in-memory access token and include credentials
 * (so the httpOnly refresh-token cookie is sent automatically).
 */
import { apiFetch } from '@/context/AuthContext'

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface AuthUserOut {
    id: string
    email: string
    role: string
    org_id: string
    org_name: string
}

export interface AuthResponse {
    access_token: string
    token_type: string
    user: AuthUserOut
}

export async function apiRegister(
    orgName: string,
    email: string,
    password: string,
): Promise<AuthResponse> {
    const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1'}/auth/register`,
        {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ org_name: orgName, email, password }),
        },
    )
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail?.message ?? 'Registration failed')
    }
    return res.json()
}

// ── Documents ───────────────────────────────────────────────────────────────

export interface DocumentOut {
    id: string
    filename: string
    file_type: string
    file_size_bytes: number
    document_type: string
    status: string
    status_detail?: string | null
    page_count?: number | null
    language?: string | null
    file_hash?: string | null
    possible_duplicate_of?: string | null
    created_at: string
    updated_at: string
}

export interface DocumentListResponse {
    items: DocumentOut[]
    total: number
    limit: number
    offset: number
}

export interface UploadDocumentResult {
    document_id: string
    filename: string
    status: string
    possible_duplicate_of?: string | null
}

export interface UploadResponse {
    documents: UploadDocumentResult[]
}

export async function apiListDocuments(): Promise<DocumentListResponse> {
    return apiGet<DocumentListResponse>('/documents')
}

export async function apiGetDocument(documentId: string): Promise<DocumentOut> {
    return apiGet<DocumentOut>(`/documents/${documentId}`)
}

export async function apiUploadDocuments(files: File[]): Promise<UploadResponse> {
    const formData = new FormData()
    for (const file of files) {
        formData.append('files', file)
    }
    const res = await apiFetch('/documents/upload', {
        method: 'POST',
        body: formData,
    })
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail?.message ?? 'Upload failed')
    }
    return res.json()
}

// ── Generic helpers ───────────────────────────────────────────────────────────

/** Error carrying the backend error code (e.g. `analysis_not_ready`). */
export class ApiError extends Error {
    code: string

    constructor(message: string, code = 'error') {
        super(message)
        this.code = code
    }
}

async function _toApiError(res: Response, fallback: string): Promise<ApiError> {
    const err = await res.json().catch(() => null)
    return new ApiError(
        err?.detail?.message ?? err?.detail ?? fallback,
        err?.detail?.code ?? 'error',
    )
}

export async function apiGet<T>(path: string): Promise<T> {
    const res = await apiFetch(path)
    if (!res.ok) {
        throw await _toApiError(res, `GET ${path} failed`)
    }
    return res.json()
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
    const res = await apiFetch(path, {
        method: 'POST',
        body: JSON.stringify(body),
    })
    if (!res.ok) {
        throw await _toApiError(res, `POST ${path} failed`)
    }
    return res.json()
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
    const res = await apiFetch(path, {
        method: 'PATCH',
        body: JSON.stringify(body),
    })
    if (!res.ok) {
        throw await _toApiError(res, `PATCH ${path} failed`)
    }
    return res.json()
}

// ── Document text (viewer source) ────────────────────────────────────────────

export interface PageBlock {
    chunk_index: number
    text: string
    section_heading?: string | null
}

export interface DocumentPage {
    page_number: number
    blocks: PageBlock[]
}

export interface DocumentTextResponse {
    document_id: string
    page_count: number
    pages: DocumentPage[]
}

export async function apiGetDocumentText(
    documentId: string,
): Promise<DocumentTextResponse> {
    return apiGet<DocumentTextResponse>(`/documents/${documentId}/text`)
}

// ── Analysis ─────────────────────────────────────────────────────────────────

export interface PartyOut {
    name: string
    role?: string | null
}

export interface SummaryOut {
    document_id: string
    parties: PartyOut[]
    purpose?: string | null
    duration?: string | null
    termination_conditions?: string | null
    key_risks?: string | null
    financial_terms?: string | null
    governing_law?: string | null
    effective_date?: string | null
    expiration_date?: string | null
    contract_value?: number | null
    contract_currency?: string | null
}

export interface ClauseOut {
    id: string
    clause_type: string
    extracted_text: string
    summary?: string | null
    page_number: number
    paragraph_index?: number | null
    confidence_score?: number | null
    source_chunk_ids?: string[] | null
    created_at: string
}

export interface ClauseListResponse {
    items: ClauseOut[]
    not_found: string[]
    total: number
}

export type RiskTriageStatus = 'flagged' | 'acknowledged' | 'dismissed'

export interface RiskOut {
    id: string
    risk_type: string
    severity: string
    description: string
    recommendation?: string | null
    page_number?: number | null
    confidence_score?: number | null
    status: RiskTriageStatus
    clause_id?: string | null
    created_at: string
}

export interface RiskListResponse {
    items: RiskOut[]
    total: number
}

export interface EntityOut {
    id: string
    entity_type: string
    value: string
    raw_text: string
    page_number: number
    confidence_score?: number | null
    created_at: string
}

export interface EntityGroup {
    entity_type: string
    items: EntityOut[]
}

export interface EntityListResponse {
    groups: EntityGroup[]
    total: number
}

export interface ObligationOut {
    id: string
    obligated_party: string
    description: string
    deadline_date?: string | null
    deadline_type: string
    status: string
    page_number: number
    created_at: string
}

export interface ObligationListResponse {
    items: ObligationOut[]
    total: number
}

export interface RiskDeduction {
    risk_id: string
    risk_type: string
    severity: string
    deduction: number
}

export interface ScoreOut {
    document_id: string
    contract_score?: number | null
    ai_confidence_score?: number | null
    scores_version: number
    breakdown: RiskDeduction[]
    total_deduction: number
}

export async function apiGetSummary(documentId: string): Promise<SummaryOut> {
    return apiGet<SummaryOut>(`/documents/${documentId}/summary`)
}

export async function apiGetClauses(
    documentId: string,
): Promise<ClauseListResponse> {
    return apiGet<ClauseListResponse>(`/documents/${documentId}/clauses`)
}

export async function apiGetRisks(documentId: string): Promise<RiskListResponse> {
    return apiGet<RiskListResponse>(`/documents/${documentId}/risks`)
}

export async function apiUpdateRiskStatus(
    documentId: string,
    riskId: string,
    status: RiskTriageStatus,
): Promise<RiskOut> {
    return apiPatch<RiskOut>(`/documents/${documentId}/risks/${riskId}`, { status })
}

export async function apiGetEntities(
    documentId: string,
): Promise<EntityListResponse> {
    return apiGet<EntityListResponse>(`/documents/${documentId}/entities`)
}

export async function apiGetObligations(
    documentId: string,
): Promise<ObligationListResponse> {
    return apiGet<ObligationListResponse>(`/documents/${documentId}/obligations`)
}

export async function apiGetScore(documentId: string): Promise<ScoreOut> {
    return apiGet<ScoreOut>(`/documents/${documentId}/score`)
}

// ── Search ───────────────────────────────────────────────────────────────────

export type SearchMode = 'keyword' | 'semantic' | 'hybrid'

export interface SearchFilters {
    document_type?: string | null
    date_from?: string | null
    date_to?: string | null
    document_ids?: string[] | null
}

export interface SearchRequest {
    query: string
    mode: SearchMode
    filters?: SearchFilters
    limit?: number
    offset?: number
}

export interface ResultDocument {
    id: string
    filename: string
    document_type: string
    status: string
    page_count?: number | null
    contract_score?: number | null
    created_at: string
}

export interface SearchSnippet {
    chunk_id: string
    text: string
    page_number: number
    section_heading?: string | null
    score: number
    source: 'keyword' | 'semantic' | 'both'
}

export interface SearchResultGroup {
    document: ResultDocument
    snippets: SearchSnippet[]
}

export interface SearchResponse {
    query: string
    mode: SearchMode
    groups: SearchResultGroup[]
    total_documents: number
    total_snippets: number
}

export async function apiSearch(request: SearchRequest): Promise<SearchResponse> {
    return apiPost<SearchResponse>('/search', {
        query: request.query,
        mode: request.mode,
        filters: request.filters ?? {},
        limit: request.limit ?? 20,
        offset: request.offset ?? 0,
    })
}

// ── RAG Q&A (SSE) ────────────────────────────────────────────────────────────

export interface AskCitation {
    index: number
    chunk_id: string
    page_number: number
    quote: string
}

export interface AskHandlers {
    onCitations?: (citations: AskCitation[]) => void
    onDelta?: (text: string) => void
    onDone?: (result: { conversation_id: string; found_in_document: boolean; answer: string }) => void
    onError?: (message: string) => void
}

/** Union of payloads the Q&A SSE stream can send (fields present per event). */
interface AskSsePayload {
    citations?: AskCitation[]
    text?: string
    conversation_id?: string
    found_in_document?: boolean
    answer?: string
    message?: string
}

/**
 * Stream a grounded answer for a question about one document.
 *
 * Uses fetch + ReadableStream instead of EventSource because the access
 * token lives in memory and must be attached as an Authorization header.
 */
export async function apiAskStream(
    documentId: string,
    question: string,
    conversationId: string | null,
    handlers: AskHandlers,
): Promise<void> {
    const body: Record<string, unknown> = { question }
    if (conversationId) body.conversation_id = conversationId

    const res = await apiFetch(`/documents/${documentId}/ask`, {
        method: 'POST',
        body: JSON.stringify(body),
    })
    if (!res.ok) {
        const err = await res.json().catch(() => null)
        handlers.onError?.(err?.detail?.message ?? 'Question failed')
        return
    }
    if (!res.body) {
        handlers.onError?.('Streaming is not supported in this browser')
        return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const dispatch = (block: string) => {
        let eventName = ''
        const dataLines: string[] = []
        for (const line of block.split('\n')) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim()
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
        }
        if (!eventName || dataLines.length === 0) return
        let data: AskSsePayload
        try {
            data = JSON.parse(dataLines.join('\n')) as AskSsePayload
        } catch {
            return
        }
        if (eventName === 'citations') handlers.onCitations?.(data.citations ?? [])
        else if (eventName === 'delta') handlers.onDelta?.(data.text ?? '')
        else if (eventName === 'done')
            handlers.onDone?.({
                conversation_id: data.conversation_id ?? '',
                found_in_document: data.found_in_document ?? false,
                answer: data.answer ?? '',
            })
        else if (eventName === 'error') handlers.onError?.(data.message ?? 'Question failed')
    }

    for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let separator = buffer.indexOf('\n\n')
        while (separator !== -1) {
            dispatch(buffer.slice(0, separator))
            buffer = buffer.slice(separator + 2)
            separator = buffer.indexOf('\n\n')
        }
    }
    if (buffer.trim()) dispatch(buffer)
}

// ── Export ───────────────────────────────────────────────────────────────────

export type ExportFormat = 'pdf' | 'docx' | 'json'

export async function apiExportDocument(
    documentId: string,
    format: ExportFormat,
): Promise<{ blob: Blob; filename: string }> {
    const res = await apiFetch(`/documents/${documentId}/export?format=${format}`)
    if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.detail?.message ?? 'Export failed')
    }
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') ?? ''
    const match = disposition.match(/filename="?([^";]+)"?/)
    return { blob, filename: match?.[1] ?? `analysis.${format}` }
}

export function downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
}
