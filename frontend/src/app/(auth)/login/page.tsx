'use client'

import { useState, type FormEvent } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Mail, Lock, Eye, EyeOff, ArrowRight, AlertCircle, Loader2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

export default function LoginPage() {
    const { login } = useAuth()
    const router = useRouter()

    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)

    async function handleSubmit(e: FormEvent) {
        e.preventDefault()
        setError(null)
        setLoading(true)
        try {
            await login(email, password)
            router.push('/contracts')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Login failed')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="animate-fade-up">
            <h1 className="font-display text-[30px] font-semibold tracking-tight text-ink-900">
                Welcome back
            </h1>
            <p className="mt-2 text-[14.5px] text-ink-500">
                Sign in to your contract workspace.
            </p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-5">
                {error && (
                    <div
                        className="animate-scale-in flex items-start gap-2.5 rounded-xl border border-rose-200/80 bg-rose-50 px-4 py-3 text-[13.5px] text-rose-700"
                        role="alert"
                    >
                        <AlertCircle size={16} className="mt-0.5 shrink-0" />
                        {error}
                    </div>
                )}

                <div>
                    <label htmlFor="email" className="field-label">
                        Email address
                    </label>
                    <div className="relative">
                        <Mail
                            size={16}
                            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-300"
                        />
                        <input
                            id="email"
                            type="email"
                            autoComplete="email"
                            required
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder="you@example.com"
                            className="field pl-10"
                        />
                    </div>
                </div>

                <div>
                    <div className="flex items-center justify-between">
                        <label htmlFor="password" className="field-label">
                            Password
                        </label>
                    </div>
                    <div className="relative">
                        <Lock
                            size={16}
                            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-300"
                        />
                        <input
                            id="password"
                            type={showPassword ? 'text' : 'password'}
                            autoComplete="current-password"
                            required
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="Your password"
                            className="field pl-10 pr-11"
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            aria-label={showPassword ? 'Hide password' : 'Show password'}
                            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-ink-300 transition-colors hover:bg-ink-100 hover:text-ink-500"
                        >
                            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                    </div>
                </div>

                <button
                    type="submit"
                    className="btn-primary w-full py-3 text-[14.5px]"
                    disabled={loading}
                >
                    {loading ? (
                        <>
                            <Loader2 size={17} className="animate-spin" />
                            Signing in…
                        </>
                    ) : (
                        <>
                            Sign in
                            <ArrowRight size={16} />
                        </>
                    )}
                </button>
            </form>

            <p className="mt-7 text-center text-[13.5px] text-ink-500">
                New organisation?{' '}
                <Link
                    href="/register"
                    className="font-semibold text-indigo-600 transition-colors hover:text-indigo-500 hover:underline"
                >
                    Create an account
                </Link>
            </p>
        </div>
    )
}
