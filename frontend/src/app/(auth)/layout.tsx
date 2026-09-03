import type { ReactNode } from 'react'
import Link from 'next/link'
import { ArrowLeft, ShieldAlert } from 'lucide-react'
import { LogoWordmark } from '@/components/ui/Logo'

const PANEL_POINTS = [
    'Clause extraction with page-level citations',
    'Risk scoring across your whole portfolio',
    'Obligation and deadline tracking',
]

export default function AuthLayout({ children }: { children: ReactNode }) {
    return (
        <div className="flex min-h-screen bg-white">
            {/* ── Left showcase panel ─────────────────────────── */}
            <div className="relative hidden w-[46%] flex-col justify-between overflow-hidden bg-ink-950 p-12 lg:flex xl:p-16">
                {/* Ambient decoration */}
                <div className="pointer-events-none absolute inset-0">
                    <div className="animate-aurora-shift absolute -left-32 -top-24 h-[420px] w-[420px] rounded-full bg-indigo-600/30 blur-[130px]" />
                    <div
                        className="animate-aurora-shift absolute -bottom-32 -right-24 h-[380px] w-[380px] rounded-full bg-fuchsia-600/20 blur-[120px]"
                        style={{ animationDelay: '-8s' }}
                    />
                    <div className="bg-grid-dark absolute inset-0 opacity-40" />
                </div>

                <div className="relative">
                    <Link href="/" className="inline-block">
                        <LogoWordmark dark />
                    </Link>
                </div>

                <div className="relative">
                    <p className="text-[11px] font-bold uppercase tracking-[0.24em] text-gold-300/80">
                        Why teams choose us
                    </p>
                    <h2 className="mt-5 max-w-md font-display text-[38px] font-semibold leading-[1.15] tracking-tight text-white text-balance">
                        Contract review at the speed of{' '}
                        <span className="text-gradient-gold italic">thought</span>.
                    </h2>
                    <ul className="mt-9 space-y-4">
                        {PANEL_POINTS.map((point, i) => (
                            <li
                                key={point}
                                className="animate-slide-in-left flex items-center gap-3.5 text-[14.5px] text-ink-200/80"
                                style={{ animationDelay: `${200 + i * 120}ms` }}
                            >
                                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/20 text-[11px] font-bold text-indigo-300 ring-1 ring-inset ring-indigo-400/30">
                                    {i + 1}
                                </span>
                                {point}
                            </li>
                        ))}
                    </ul>
                </div>

                <div className="relative flex items-center gap-2 text-[11.5px] text-ink-300/50">
                    <ShieldAlert size={13} className="text-gold-400/80" />
                    AI analysis is not legal advice.
                </div>
            </div>

            {/* ── Right form panel ────────────────────────────── */}
            <div className="relative flex flex-1 flex-col bg-ink-50/40">
                <div className="bg-grid mask-fade-b pointer-events-none absolute inset-0 opacity-60" />
                <div className="relative flex items-center justify-between p-6 lg:justify-end">
                    <Link
                        href="/"
                        className="btn-ghost px-3 py-2 text-[13px] lg:hidden"
                        aria-label="Back to home"
                    >
                        <ArrowLeft size={15} />
                        Home
                    </Link>
                    <Link href="/" className="btn-ghost hidden px-3 py-2 text-[13px] lg:inline-flex">
                        <ArrowLeft size={15} />
                        Back to site
                    </Link>
                </div>
                <div className="relative flex flex-1 items-center justify-center px-6 pb-16">
                    <div className="w-full max-w-[400px]">{children}</div>
                </div>
            </div>
        </div>
    )
}
