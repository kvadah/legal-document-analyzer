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

export async function apiGet<T>(path: string): Promise<T> {
    const res = await apiFetch(path)
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail?.message ?? `GET ${path} failed`)
    }
    return res.json()
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
    const res = await apiFetch(path, {
        method: 'POST',
        body: JSON.stringify(body),
    })
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail?.message ?? `POST ${path} failed`)
    }
    return res.json()
}
