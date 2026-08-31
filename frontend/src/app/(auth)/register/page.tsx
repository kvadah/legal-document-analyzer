'use client'

import { useState, type FormEvent } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { apiRegister } from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'

export default function RegisterPage() {
    const { login } = useAuth()
    const router = useRouter()

    const [orgName, setOrgName] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)

    async function handleSubmit(e: FormEvent) {
        e.preventDefault()
        setError(null)
        setLoading(true)
        try {
            await apiRegister(orgName, email, password)
            // After register, log in to get tokens into auth context
            await login(email, password)
            router.push('/contracts')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Registration failed')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="auth-card">
            <div className="auth-brand">
                <h1>Legal Doc AI</h1>
                <p>Contract analysis, powered by AI</p>
            </div>

            <form onSubmit={handleSubmit} className="auth-form">
                <h2>Create your organisation</h2>

                {error && (
                    <div className="auth-error" role="alert">
                        {error}
                    </div>
                )}

                <div className="form-group">
                    <label htmlFor="org-name">Organisation name</label>
                    <input
                        id="org-name"
                        type="text"
                        required
                        minLength={2}
                        value={orgName}
                        onChange={e => setOrgName(e.target.value)}
                        placeholder="Acme Legal"
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="email">Your email</label>
                    <input
                        id="email"
                        type="email"
                        autoComplete="email"
                        required
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        placeholder="you@acme.com"
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="password">Password</label>
                    <input
                        id="password"
                        type="password"
                        autoComplete="new-password"
                        required
                        minLength={8}
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="Min. 8 characters"
                    />
                </div>

                <button
                    type="submit"
                    className="btn-primary btn-full"
                    disabled={loading}
                >
                    {loading ? 'Creating account…' : 'Create account'}
                </button>

                <p className="auth-alt-action">
                    Already have an account?{' '}
                    <Link href="/login">Sign in</Link>
                </p>
            </form>
        </div>
    )
}
