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
