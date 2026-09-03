'use client'

import Link from 'next/link'
import {
    ArrowRight,
    ScanSearch,
    ShieldAlert,
    FileSearch,
    CalendarClock,
    Sparkles,
    Lock,
    Server,
    EyeOff,
    CheckCircle2,
    ChevronRight,
    Quote,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { LogoWordmark } from '@/components/ui/Logo'

/* ────────────────────────────────────────────────────────────
   Decorative helpers
   ──────────────────────────────────────────────────────────── */

function Aurora({ className = '' }: { className?: string }) {
    return (
        <div className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}>
            <div className="animate-aurora-shift absolute -top-40 left-[8%] h-[480px] w-[480px] rounded-full bg-indigo-600/30 blur-[130px]" />
            <div
                className="animate-aurora-shift absolute -right-32 top-10 h-[420px] w-[420px] rounded-full bg-fuchsia-600/20 blur-[130px]"
                style={{ animationDelay: '-6s' }}
            />
            <div
                className="animate-aurora-shift absolute -left-24 top-64 h-[380px] w-[380px] rounded-full bg-gold-500/10 blur-[120px]"
                style={{ animationDelay: '-12s' }}
            />
        </div>
    )
}

/* ────────────────────────────────────────────────────────────
   Product mockup (pure CSS/SVG — no images needed)
   ──────────────────────────────────────────────────────────── */

function ScoreRing({ score }: { score: number }) {
    const r = 34
    const c = 2 * Math.PI * r
    const filled = (score / 100) * c
    return (
        <div className="relative h-24 w-24">
            <svg viewBox="0 0 84 84" className="h-24 w-24 -rotate-90">
                <circle cx="42" cy="42" r={r} fill="none" stroke="#E5E9F2" strokeWidth="8" />
                <circle
                    cx="42"
                    cy="42"
                    r={r}
                    fill="none"
                    stroke="url(#ringGrad)"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${filled} ${c - filled}`}
                />
                <defs>
                    <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor="#6366F1" />
                        <stop offset="100%" stopColor="#A855F7" />
                    </linearGradient>
                </defs>
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-display text-[26px] font-semibold leading-none text-ink-900">
                    {score}
                </span>
                <span className="mt-0.5 text-[9px] font-bold uppercase tracking-[0.14em] text-ink-400">
                    Score
                </span>
            </div>
        </div>
    )
}

function ProductMockup() {
    return (
        <div className="relative mx-auto w-full max-w-4xl animate-fade-up animation-delay-300">
            {/* Floating chips */}
            <div className="animate-float absolute -left-6 -top-8 z-20 hidden rounded-2xl border border-ink-100 bg-white/90 px-4 py-3 shadow-lift backdrop-blur md:block">
                <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-50 text-rose-500">
                        <ShieldAlert size={15} />
                    </span>
                    <div>
                        <p className="text-[11px] font-semibold text-ink-900">
                            Unlimited liability
                        </p>
                        <p className="text-[10px] text-ink-400">High risk · Clause 12.2</p>
                    </div>
                </div>
            </div>
            <div
                className="animate-float absolute -right-8 top-24 z-20 hidden rounded-2xl border border-ink-100 bg-white/90 px-4 py-3 shadow-lift backdrop-blur md:block"
                style={{ animationDelay: '-3.5s' }}
            >
                <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-500">
                        <CheckCircle2 size={15} />
                    </span>
                    <div>
                        <p className="text-[11px] font-semibold text-ink-900">
                            14 clauses extracted
                        </p>
                        <p className="text-[10px] text-ink-400">in 42 seconds</p>
                    </div>
                </div>
            </div>

            {/* Browser frame */}
            <div className="relative overflow-hidden rounded-2xl border border-ink-800/60 bg-white shadow-[0_40px_80px_-20px_rgba(7,13,24,0.45)] ring-1 ring-white/10">
                {/* Chrome bar */}
                <div className="flex items-center gap-2 border-b border-ink-100 bg-ink-50/80 px-4 py-2.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-gold-300/90" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                    <div className="mx-auto flex items-center gap-1.5 rounded-md bg-white px-3 py-1 text-[10px] font-medium text-ink-400 shadow-[0_1px_2px_rgba(12,21,38,0.06)]">
                        <Lock size={9} className="text-emerald-500" />
                        app.legaldoc.ai/contracts
                    </div>
                </div>

                {/* App body */}
                <div className="flex">
                    {/* Mini sidebar */}
                    <div className="hidden w-40 shrink-0 flex-col gap-1 bg-ink-950 p-4 sm:flex">
                        <div className="mb-3 flex items-center gap-2">
                            <span className="h-6 w-6 rounded-lg bg-gradient-to-br from-indigo-500 to-fuchsia-500" />
                            <span className="font-display text-[12px] font-semibold text-white">
                                Legal Doc AI
                            </span>
                        </div>
                        {['Contracts', 'Upload', 'Search', 'Reports'].map((item, i) => (
                            <div
                                key={item}
                                className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[11px] font-medium ${
                                    i === 0
                                        ? 'bg-gradient-to-r from-indigo-500 to-violet-600 text-white'
                                        : 'text-ink-300/50'
                                }`}
                            >
                                <span className="h-3 w-3 rounded-[4px] bg-current opacity-60" />
                                {item}
                            </div>
                        ))}
                    </div>

                    {/* Mini dashboard */}
                    <div className="min-w-0 flex-1 bg-ink-50/50 p-5">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-indigo-400">
                                    Analysis
                                </p>
                                <p className="font-display text-[15px] font-semibold text-ink-900">
                                    MasterServicesAgreement-v3.pdf
                                </p>
                            </div>
                            <span className="pill bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/15">
                                <span className="status-dot bg-emerald-500" />
                                Analyzed
                            </span>
                        </div>

                        <div className="mt-4 grid grid-cols-3 gap-3">
                            {/* Score card */}
                            <div className="col-span-1 flex items-center justify-center rounded-xl border border-ink-100 bg-white p-3">
                                <ScoreRing score={78} />
                            </div>
                            {/* Risk list */}
                            <div className="col-span-2 space-y-2 rounded-xl border border-ink-100 bg-white p-3">
                                {[
                                    { label: 'Unlimited liability exposure', w: '82%', tone: 'bg-rose-400' },
                                    { label: 'Auto-renewal clause detected', w: '64%', tone: 'bg-gold-400' },
                                    { label: 'Missing termination rights', w: '41%', tone: 'bg-amber-300' },
                                ].map(r => (
                                    <div key={r.label}>
                                        <div className="mb-1 flex items-center justify-between text-[10px]">
                                            <span className="font-medium text-ink-700">
                                                {r.label}
                                            </span>
                                            <span className="font-semibold text-ink-400">
                                                {r.w}
                                            </span>
                                        </div>
                                        <div className="h-1.5 overflow-hidden rounded-full bg-ink-100">
                                            <div
                                                className={`h-full rounded-full ${r.tone}`}
                                                style={{ width: r.w }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Clause chips */}
                        <div className="mt-3 flex flex-wrap gap-1.5">
                            {[
                                'Termination',
                                'Confidentiality',
                                'Indemnification',
                                'Governing law',
                                'Payment',
                            ].map(c => (
                                <span
                                    key={c}
                                    className="rounded-md border border-ink-100 bg-white px-2 py-1 text-[10px] font-medium text-ink-500"
                                >
                                    {c}
                                </span>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

/* ────────────────────────────────────────────────────────────
   Page sections
   ──────────────────────────────────────────────────────────── */

const NAV_LINKS = [
    { href: '#features', label: 'Features' },
    { href: '#how-it-works', label: 'How it works' },
    { href: '#security', label: 'Security' },
]

const STATS = [
    { value: '50k+', label: 'Documents analysed' },
    { value: '92%', label: 'Risk detection rate' },
    { value: '40×', label: 'Faster than manual review' },
    { value: '99.9%', label: 'Pipeline uptime' },
]

const FEATURES = [
    {
        icon: ScanSearch,
        title: 'Clause-level extraction',
        description:
            'Termination, confidentiality, indemnification and more — every clause located, classified, and quoted with page-level citations.',
        accent: 'from-indigo-500 to-violet-500',
    },
    {
        icon: ShieldAlert,
        title: 'Risk radar',
        description:
            'Unlimited liability, auto-renewals, missing governing law — risks are scored by severity with actionable recommendations.',
        accent: 'from-rose-500 to-orange-400',
    },
    {
        icon: CalendarClock,
        title: 'Obligation calendar',
        description:
            'Payment dates, notice periods, and renewals surface automatically so nothing slips through the cracks.',
        accent: 'from-gold-400 to-gold-600',
    },
    {
        icon: FileSearch,
        title: 'Hybrid search',
        description:
            'Query your entire portfolio by meaning or keyword. Ask questions in plain English, get the exact paragraph back.',
        accent: 'from-sky-500 to-cyan-400',
    },
]

const STEPS = [
    {
        number: '01',
        title: 'Upload',
        description:
            'Drop in PDFs, DOCX, or scans. OCR runs automatically, even on photographed contracts.',
    },
    {
        number: '02',
        title: 'Analyse',
        description:
            'The AI pipeline extracts clauses, entities, risks, and obligations — then scores the whole agreement.',
    },
    {
        number: '03',
        title: 'Review',
        description:
            'Work through findings with severity filters, export portfolio reports, and share with your team.',
    },
]

const SECURITY_POINTS = [
    {
        icon: Lock,
        title: 'Encrypted at rest & in transit',
        description: 'Documents are stored with server-side encryption and TLS everywhere.',
    },
    {
        icon: Server,
        title: 'Your data stays yours',
        description: 'Private object storage per organisation. No training on your contracts.',
    },
    {
        icon: EyeOff,
        title: 'Least-privilege access',
        description: 'Role-based access control with admin, reviewer, and viewer scopes.',
    },
]

export default function LandingPage() {
    const { user } = useAuth()
    const primaryCta = user ? { href: '/contracts', label: 'Go to dashboard' } : { href: '/register', label: 'Start analysing free' }

    return (
        <div className="min-h-screen bg-white">
            {/* ── Nav ─────────────────────────────────────────── */}
            <header className="fixed inset-x-0 top-0 z-50">
                <div className="glass border-b border-ink-950/5">
                    <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
                        <Link href="/">
                            <LogoWordmark />
                        </Link>
                        <nav className="hidden items-center gap-8 md:flex">
                            {NAV_LINKS.map(link => (
                                <a
                                    key={link.href}
                                    href={link.href}
                                    className="text-[13.5px] font-medium text-ink-500 transition-colors hover:text-ink-900"
                                >
                                    {link.label}
                                </a>
                            ))}
                        </nav>
                        <div className="flex items-center gap-3">
                            {!user && (
                                <Link href="/login" className="btn-ghost text-[13.5px]">
                                    Sign in
                                </Link>
                            )}
                            <Link
                                href={primaryCta.href}
                                className="btn-primary px-4 py-2 text-[13.5px]"
                            >
                                {primaryCta.label}
                                <ArrowRight size={14} />
                            </Link>
                        </div>
                    </div>
                </div>
            </header>

            {/* ── Hero ────────────────────────────────────────── */}
            <section className="relative overflow-hidden bg-ink-950 pb-24 pt-36">
                <Aurora />
                <div className="bg-grid-dark mask-fade-edges absolute inset-0" />
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-white/5 to-transparent" />

                <div className="relative mx-auto max-w-6xl px-6 text-center">
                    <div className="animate-fade-up mx-auto inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.06] px-4 py-1.5 text-[12px] font-medium text-ink-200 shadow-inner-top backdrop-blur">
                        <Sparkles size={13} className="text-gold-300" />
                        AI contract intelligence for modern legal teams
                        <span className="rounded-full bg-indigo-500/30 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-indigo-200">
                            Beta
                        </span>
                    </div>

                    <h1 className="animate-fade-up animation-delay-100 mx-auto mt-8 max-w-3xl font-display text-[44px] font-semibold leading-[1.08] tracking-tight text-white text-balance md:text-[64px]">
                        Every clause understood.{' '}
                        <span className="text-gradient-gold italic">Every risk</span> caught
                        before signature.
                    </h1>

                    <p className="animate-fade-up animation-delay-200 mx-auto mt-6 max-w-xl text-[16.5px] leading-relaxed text-ink-200/70 text-balance">
                        Legal Doc AI reads your contracts the way a partner would — extracting
                        clauses, scoring risk, and tracking obligations across your entire
                        portfolio.
                    </p>

                    <div className="animate-fade-up animation-delay-300 mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                        <Link
                            href={primaryCta.href}
                            className="btn-primary px-7 py-3.5 text-[15px]"
                        >
                            {primaryCta.label}
                            <ArrowRight size={16} />
                        </Link>
                        <a href="#how-it-works" className="btn-ghost-dark px-7 py-3.5 text-[15px]">
                            See how it works
                        </a>
                    </div>

                    <p className="animate-fade-in animation-delay-500 mt-5 text-[12px] text-ink-300/50">
                        No credit card required · Upload your first document in under a minute
                    </p>
                </div>

                <div className="relative mx-auto mt-16 max-w-6xl px-6">
                    <ProductMockup />
                </div>
            </section>

            {/* ── Stats ───────────────────────────────────────── */}
            <section className="relative border-b border-ink-100 bg-white">
                <div className="mx-auto grid max-w-6xl grid-cols-2 divide-x divide-ink-100 px-6 md:grid-cols-4">
                    {STATS.map((stat, i) => (
                        <div
                            key={stat.label}
                            className="animate-fade-up flex flex-col items-center gap-1 px-4 py-10"
                            style={{ animationDelay: `${i * 90}ms` }}
                        >
                            <p className="font-display text-[34px] font-semibold tracking-tight text-ink-900">
                                {stat.value}
                            </p>
                            <p className="text-[12.5px] font-medium text-ink-400">{stat.label}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* ── Features ────────────────────────────────────── */}
            <section id="features" className="relative bg-ink-50/40 py-24">
                <div className="bg-grid mask-fade-b pointer-events-none absolute inset-0 opacity-60" />
                <div className="relative mx-auto max-w-6xl px-6">
                    <div className="mx-auto max-w-2xl text-center">
                        <p className="animate-fade-up text-[11px] font-bold uppercase tracking-[0.22em] text-primary/70">
                            Capabilities
                        </p>
                        <h2 className="animate-fade-up animation-delay-100 mt-3 font-display text-[34px] font-semibold tracking-tight text-ink-900 md:text-[40px]">
                            A review workflow that thinks like a lawyer
                        </h2>
                        <p className="animate-fade-up animation-delay-200 mt-4 text-[15.5px] leading-relaxed text-ink-500">
                            Purpose-built pipelines for contract intelligence — not generic
                            document chat.
                        </p>
                    </div>

                    <div className="mt-14 grid gap-5 sm:grid-cols-2">
                        {FEATURES.map((feature, i) => (
                            <div
                                key={feature.title}
                                className="card animate-fade-up group relative overflow-hidden p-7 transition-all duration-300 hover:-translate-y-1 hover:shadow-lift"
                                style={{ animationDelay: `${i * 90}ms` }}
                            >
                                <div
                                    className={`pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-gradient-to-br ${feature.accent} opacity-[0.07] blur-2xl transition-opacity duration-300 group-hover:opacity-[0.16]`}
                                />
                                <div
                                    className={`relative flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-lift ${feature.accent}`}
                                >
                                    <feature.icon size={20} strokeWidth={2} />
                                </div>
                                <h3 className="mt-5 font-display text-[19px] font-semibold text-ink-900">
                                    {feature.title}
                                </h3>
                                <p className="mt-2.5 text-[14.5px] leading-relaxed text-ink-500">
                                    {feature.description}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── How it works ────────────────────────────────── */}
            <section id="how-it-works" className="relative overflow-hidden bg-ink-950 py-24">
                <Aurora className="opacity-60" />
                <div className="bg-grid-dark absolute inset-0 opacity-30" />
                <div className="relative mx-auto max-w-6xl px-6">
                    <div className="mx-auto max-w-2xl text-center">
                        <p className="animate-fade-up text-[11px] font-bold uppercase tracking-[0.22em] text-gold-300/80">
                            Workflow
                        </p>
                        <h2 className="animate-fade-up animation-delay-100 mt-3 font-display text-[34px] font-semibold tracking-tight text-white md:text-[40px]">
                            From upload to insight in three steps
                        </h2>
                    </div>

                    <div className="relative mt-16 grid gap-10 md:grid-cols-3">
                        {/* connector */}
                        <div className="pointer-events-none absolute left-[16.6%] right-[16.6%] top-8 hidden h-px bg-gradient-to-r from-indigo-500/10 via-indigo-400/50 to-indigo-500/10 md:block" />
                        {STEPS.map((step, i) => (
                            <div
                                key={step.number}
                                className="animate-fade-up relative text-center"
                                style={{ animationDelay: `${i * 140}ms` }}
                            >
                                <div className="relative z-10 mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-indigo-400/30 bg-ink-900 font-display text-[20px] font-semibold text-gold-300 shadow-[0_0_30px_-6px_rgba(99,102,241,0.5)]">
                                    {step.number}
                                </div>
                                <h3 className="mt-6 font-display text-[21px] font-semibold text-white">
                                    {step.title}
                                </h3>
                                <p className="mx-auto mt-2.5 max-w-xs text-[14px] leading-relaxed text-ink-200/60">
                                    {step.description}
                                </p>
                            </div>
                        ))}
                    </div>

                    <div className="animate-fade-up animation-delay-500 mt-14 text-center">
                        <Link href={primaryCta.href} className="btn-gold px-7 py-3.5 text-[15px]">
                            Try it on your own contract
                            <ChevronRight size={16} />
                        </Link>
                    </div>
                </div>
            </section>

            {/* ── Security ────────────────────────────────────── */}
            <section id="security" className="bg-white py-24">
                <div className="mx-auto grid max-w-6xl items-center gap-14 px-6 lg:grid-cols-2">
                    <div className="animate-fade-up">
                        <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-primary/70">
                            Trust &amp; security
                        </p>
                        <h2 className="mt-3 font-display text-[32px] font-semibold leading-tight tracking-tight text-ink-900 md:text-[38px]">
                            Built for confidential documents from day one
                        </h2>
                        <p className="mt-4 text-[15.5px] leading-relaxed text-ink-500">
                            Contracts are among the most sensitive documents your organisation
                            holds. We treat them that way — with strict isolation, encryption,
                            and access controls at every layer.
                        </p>

                        <div className="mt-8 space-y-5">
                            {SECURITY_POINTS.map((point, i) => (
                                <div
                                    key={point.title}
                                    className="animate-fade-up flex gap-4"
                                    style={{ animationDelay: `${i * 100}ms` }}
                                >
                                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
                                        <point.icon size={18} />
                                    </span>
                                    <div>
                                        <h3 className="text-[15px] font-semibold text-ink-900">
                                            {point.title}
                                        </h3>
                                        <p className="mt-0.5 text-[13.5px] leading-relaxed text-ink-500">
                                            {point.description}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Testimonial / quote card */}
                    <div className="animate-fade-up animation-delay-200 relative">
                        <div className="absolute -inset-6 -z-10 rounded-[2rem] bg-gradient-to-br from-indigo-100/60 via-transparent to-gold-100/40 blur-2xl" />
                        <figure className="card relative overflow-hidden p-8 shadow-lift">
                            <Quote
                                size={72}
                                className="absolute -right-2 -top-2 text-indigo-50"
                                strokeWidth={1}
                            />
                            <blockquote className="relative font-display text-[21px] font-medium leading-relaxed text-ink-800">
                                &ldquo;The risk radar flagged an auto-renewal clause our team had
                                missed for two renewal cycles. It paid for itself in the first
                                week.&rdquo;
                            </blockquote>
                            <figcaption className="relative mt-7 flex items-center gap-3.5">
                                <span className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-ink-700 to-ink-900 font-display text-[15px] font-semibold text-white">
                                    SR
                                </span>
                                <div>
                                    <p className="text-[14px] font-semibold text-ink-900">
                        Sarah Rahman
                                    </p>
                                    <p className="text-[12.5px] text-ink-400">
                                        General Counsel, Meridian Partners
                                    </p>
                                </div>
                            </figcaption>
                        </figure>
                    </div>
                </div>
            </section>

            {/* ── CTA ─────────────────────────────────────────── */}
            <section className="relative overflow-hidden px-6 pb-24">
                <div className="relative mx-auto max-w-5xl overflow-hidden rounded-[2rem] bg-ink-950 px-8 py-16 text-center shadow-[0_40px_80px_-24px_rgba(7,13,24,0.5)] md:py-20">
                    <Aurora />
                    <div className="bg-grid-dark mask-fade-edges absolute inset-0" />
                    <div className="relative">
                        <h2 className="animate-fade-up mx-auto max-w-2xl font-display text-[32px] font-semibold leading-tight tracking-tight text-white text-balance md:text-[42px]">
                            Stop reading contracts line by line.
                        </h2>
                        <p className="animate-fade-up animation-delay-100 mx-auto mt-4 max-w-lg text-[15.5px] leading-relaxed text-ink-200/70">
                            Upload a contract today and see a complete risk profile in seconds —
                            no obligation, no credit card.
                        </p>
                        <div className="animate-fade-up animation-delay-200 mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
                            <Link
                                href={primaryCta.href}
                                className="btn-primary px-8 py-3.5 text-[15px]"
                            >
                                {primaryCta.label}
                                <ArrowRight size={16} />
                            </Link>
                            <Link href="/login" className="btn-ghost-dark px-8 py-3.5 text-[15px]">
                                Sign in
                            </Link>
                        </div>
                    </div>
                </div>
            </section>

            {/* ── Footer ──────────────────────────────────────── */}
            <footer className="border-t border-ink-100 bg-ink-50/50">
                <div className="mx-auto max-w-6xl px-6 py-14">
                    <div className="flex flex-col justify-between gap-10 md:flex-row">
                        <div className="max-w-sm">
                            <LogoWordmark />
                            <p className="mt-4 text-[13.5px] leading-relaxed text-ink-500">
                                AI-powered contract review and analysis. Detect risks, extract
                                obligations, and understand every clause in seconds.
                            </p>
                        </div>
                        <div className="grid grid-cols-2 gap-12 sm:grid-cols-3">
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-400">
                                    Product
                                </p>
                                <ul className="mt-4 space-y-2.5 text-[13.5px] text-ink-500">
                                    <li>
                                        <a href="#features" className="transition-colors hover:text-ink-900">
                                            Features
                                        </a>
                                    </li>
                                    <li>
                                        <a href="#how-it-works" className="transition-colors hover:text-ink-900">
                                            How it works
                                        </a>
                                    </li>
                                    <li>
                                        <a href="#security" className="transition-colors hover:text-ink-900">
                                            Security
                                        </a>
                                    </li>
                                </ul>
                            </div>
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-400">
                                    Company
                                </p>
                                <ul className="mt-4 space-y-2.5 text-[13.5px] text-ink-500">
                                    <li>About</li>
                                    <li>Careers</li>
                                    <li>Contact</li>
                                </ul>
                            </div>
                            <div>
                                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-400">
                                    Legal
                                </p>
                                <ul className="mt-4 space-y-2.5 text-[13.5px] text-ink-500">
                                    <li>Privacy</li>
                                    <li>Terms</li>
                                    <li>DPA</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    <div className="mt-12 flex flex-col items-center justify-between gap-3 border-t border-ink-100 pt-6 text-[12px] text-ink-400 sm:flex-row">
                        <p>© 2026 Legal Doc AI. All rights reserved.</p>
                        <p className="flex items-center gap-1.5">
                            <ShieldAlert size={12} className="text-gold-500" />
                            AI analysis is not legal advice.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    )
}
