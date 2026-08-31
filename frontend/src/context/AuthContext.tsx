'use client'

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from 'react'

export interface AuthUser {
    id: string
    email: string
    role: 'admin' | 'reviewer' | 'viewer'
    orgId: string
    orgName: string
}

interface AuthContextValue {
    user: AuthUser | null
    isLoading: boolean
    login: (email: string, password: string) => Promise<void>
    logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1'

// In-memory access token store (not localStorage — avoids XSS token theft)
let _accessToken: string | null = null

export function getAccessToken(): string | null {
    return _accessToken
}

function setAccessToken(token: string | null) {
    _accessToken = token
}

// ── Typed fetch that auto-attaches the Bearer token ──────────────────────────

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(init.headers as Record<string, string> ?? {}),
    }
    if (_accessToken) {
        headers['Authorization'] = `Bearer ${_accessToken}`
    }
    const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        credentials: 'include', // send httpOnly refresh-token cookie
        headers,
    })

    // Silently refresh on 401 and retry once
    if (res.status === 401 && _accessToken) {
        const refreshed = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            credentials: 'include',
        })
        if (refreshed.ok) {
            const data = await refreshed.json()
            setAccessToken(data.access_token)
            headers['Authorization'] = `Bearer ${_accessToken}`
            return fetch(`${API_BASE}${path}`, { ...init, credentials: 'include', headers })
        }
        // Refresh failed — caller will see the 401
        setAccessToken(null)
    }
    return res
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<AuthUser | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    // On mount, try a silent token refresh to restore session
    useEffect(() => {
        async function restoreSession() {
            try {
                const res = await fetch(`${API_BASE}/auth/refresh`, {
                    method: 'POST',
                    credentials: 'include',
                })
                if (res.ok) {
                    const data = await res.json()
                    setAccessToken(data.access_token)
                    setUser({
                        id: data.user.id,
                        email: data.user.email,
                        role: data.user.role as AuthUser['role'],
                        orgId: data.user.org_id,
                        orgName: data.user.org_name,
                    })
                }
            } catch {
                // No active session — that's fine
            } finally {
                setIsLoading(false)
            }
        }
        restoreSession()
    }, [])

    const login = useCallback(async (email: string, password: string) => {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        })
        if (!res.ok) {
            const err = await res.json().catch(() => ({}))
            throw new Error(err?.detail?.message ?? 'Login failed')
        }
        const data = await res.json()
        setAccessToken(data.access_token)
        setUser({
            id: data.user.id,
            email: data.user.email,
            role: data.user.role as AuthUser['role'],
            orgId: data.user.org_id,
            orgName: data.user.org_name,
        })
    }, [])

    const logout = useCallback(async () => {
        try {
            await fetch(`${API_BASE}/auth/logout`, {
                method: 'POST',
                credentials: 'include',
            })
        } finally {
            setAccessToken(null)
            setUser(null)
        }
    }, [])

    return (
        <AuthContext.Provider value={{ user, isLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    )
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
    const ctx = useContext(AuthContext)
    if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
    return ctx
}
