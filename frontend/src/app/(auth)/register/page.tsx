'use client'

import { useMemo, useState, type FormEvent } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
    Building2,
    Mail,
    Lock,
    Eye,
    EyeOff,
    ArrowRight,
    AlertCircle,
    Loader2,
    Check,
} from 'lucide-react'
import { apiRegister } from '@/lib/api-client'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/cn'

function PasswordStrength({ password }: { password: string }) {
    const checks = useMemo(
        () => [
            { label: '8+ characters', ok: password.length >= 8 },
            { label: 'Uppercase letter', ok: /[A-Z]/.test(password) },
            { label: 'Number', ok: /\d/.test(password) },
        ],
        [password],
    )
    const passed = checks.filter(c => c.ok).length
    if (!password) return null

    return (
        <div className="mt-2.5">
            <div className="flex gap-1.5">
                {checks.map((check, i) => (
                    <span
                        key={check.label}
                        className={cn(
                            'h-1 flex-1 rounded-full transition-colors duration-300',
                            i < passed
                                ? passed === checks.length
                                    ? 'bg-emerald-400'
                                    : 'bg-gold-400'
                                : 'bg-ink-100',
                        )}
                    />
                ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                {checks.map(check => (
                    <span
                        key={check.label}
                        className={cn(
                            'flex items-center gap-1 text-[11.5px] transition-colors',
                            check.ok ? 'text-emerald-600' : 'text-ink-400',
                        )}
                    >
                        <span
                            className={cn(
                                'flex h-3.5 w-3.5 items-center justify-center rounded-full',
                                check.ok ? 'bg-emerald-100' : 'bg-ink-100',
                            )}
                        >
                            {check.ok && <Check size={9} strokeWidth={3.5} />}
                        </span>
                        {check.label}
                    </span>
                ))}
            </div>
        </div>
    )
}

export default function RegisterPage() {
    const { login } = useAuth()
    const router = useRouter()

    const [orgName, setOrgName] = useState('')
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
            await apiRegister(orgName, email, password)
            await login(email, password)
            router.push('/contracts')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Registration failed')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="animate-fade-up">
            <h1 className="font-display text-[30px] font-semibold tracking-tight text-ink-900">
                Create your workspace
            </h1>
            <p className="mt-2 text-[14.5px] text-ink-500">
                Start analysing contracts in under a minute.
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
                    <label htmlFor="org-name" className="field-label">
                        Organisation name
                    </label>
                    <div className="relative">
                        <Building2
                            size={16}
                            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-300"
                        />
                        <input
                            id="org-name"
                            type="text"
                            required
                            minLength={2}
                            value={orgName}
                            onChange={e => setOrgName(e.target.value)}
                            placeholder="Acme Legal"
                            className="field pl-10"
                        />
                    </div>
                </div>

                <div>
                    <label htmlFor="email" className="field-label">
                        Work email
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
                            placeholder="you@acme.com"
                            className="field pl-10"
                        />
                    </div>
                </div>

                <div>
                    <label htmlFor="password" className="field-label">
                        Password
                    </label>
                    <div className="relative">
                        <Lock
                            size={16}
                            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-300"
                        />
                        <input
                            id="password"
                            type={showPassword ? 'text' : 'password'}
                            autoComplete="new-password"
                            required
                            minLength={8}
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="Choose a strong password"
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
                    <PasswordStrength password={password} />
                </div>

                <button
                    type="submit"
                    className="btn-primary w-full py-3 text-[14.5px]"
                    disabled={loading}
                >
                    {loading ? (
                        <>
                            <Loader2 size={17} className="animate-spin" />
                            Creating account…
                        </>
                    ) : (
                        <>
                            Create account
                            <ArrowRight size={16} />
                        </>
                    )}
                </button>
            </form>

            <p className="mt-7 text-center text-[13.5px] text-ink-500">
                Already have an account?{' '}
                <Link
                    href="/login"
                    className="font-semibold text-indigo-600 transition-colors hover:text-indigo-500 hover:underline"
                >
                    Sign in
                </Link>
            </p>
        </div>
    )
}
