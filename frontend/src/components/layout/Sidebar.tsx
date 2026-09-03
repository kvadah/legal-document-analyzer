'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import {
    FileText,
    Upload,
    Search,
    BarChart3,
    Settings,
    Menu,
    X,
    ShieldCheck,
    Plus,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { LogoMark } from '@/components/ui/Logo'
import { cn } from '@/lib/cn'

const NAV_SECTIONS = [
    {
        title: 'Workspace',
        items: [
            { href: '/contracts', label: 'Contracts', icon: FileText },
            { href: '/upload', label: 'Upload', icon: Upload },
            { href: '/search', label: 'Search', icon: Search },
        ],
    },
    {
        title: 'Insights',
        items: [
            { href: '/reports', label: 'Reports', icon: BarChart3 },
            { href: '/admin', label: 'Administration', icon: Settings, adminOnly: true },
        ],
    },
]

export default function Sidebar() {
    const [isOpen, setIsOpen] = useState(false)
    const pathname = usePathname()
    const { user } = useAuth()
    const isAdmin = user?.role === 'admin'

    // Close the mobile drawer whenever the route changes
    useEffect(() => {
        setIsOpen(false)
    }, [pathname])

    return (
        <>
            {/* Mobile toggle */}
            <button
                id="sidebar-toggle-btn"
                aria-label="Toggle navigation"
                onClick={() => setIsOpen(!isOpen)}
                className="fixed left-4 top-4 z-50 flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-ink-900/80 text-white backdrop-blur transition-colors hover:bg-ink-800 lg:hidden"
            >
                {isOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* Mobile overlay */}
            {isOpen && (
                <div
                    className="fixed inset-0 z-30 bg-ink-950/60 backdrop-blur-sm lg:hidden"
                    onClick={() => setIsOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside
                className={cn(
                    'fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col bg-ink-950 transition-transform duration-300 ease-out lg:translate-x-0',
                    isOpen ? 'translate-x-0' : '-translate-x-full',
                )}
            >
                {/* Ambient decoration */}
                <div className="pointer-events-none absolute inset-0 overflow-hidden">
                    <div className="absolute -top-24 left-1/2 h-64 w-[130%] -translate-x-1/2 rounded-full bg-indigo-600/25 blur-[90px]" />
                    <div className="bg-grid-dark absolute inset-0 opacity-40" />
                </div>

                {/* Brand */}
                <div className="relative flex items-center gap-3 px-6 pb-5 pt-6">
                    <LogoMark size={36} />
                    <div className="leading-none">
                        <p className="font-display text-[16px] font-semibold tracking-tight text-white">
                            Legal Doc <span className="text-gradient">AI</span>
                        </p>
                        <p className="mt-1 text-[9.5px] font-bold uppercase tracking-[0.24em] text-ink-300/50">
                            Contract Intelligence
                        </p>
                    </div>
                </div>

                {/* Org context card */}
                <div className="relative mx-4 mb-5 rounded-xl border border-white/[0.07] bg-white/[0.04] p-3.5 shadow-inner-top">
                    <div className="flex items-center gap-2.5">
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-gold-300/90 to-gold-500/90 text-[11px] font-bold text-ink-950">
                            {(user?.orgName ?? 'ORG').slice(0, 2).toUpperCase()}
                        </span>
                        <div className="min-w-0">
                            <p className="truncate text-[13px] font-semibold text-white">
                                {user?.orgName ?? 'Your organisation'}
                            </p>
                            <p className="text-[11px] capitalize text-ink-300/60">
                                {user?.role ?? 'member'} workspace
                            </p>
                        </div>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="relative flex-1 overflow-y-auto px-4 pb-4">
                    {NAV_SECTIONS.map(section => (
                        <div key={section.title} className="mb-6">
                            <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-300/40">
                                {section.title}
                            </p>
                            <ul className="space-y-1">
                                {section.items.map(item => {
                                    if (item.adminOnly && !isAdmin) return null
                                    const Icon = item.icon
                                    const isActive =
                                        pathname === item.href ||
                                        pathname.startsWith(item.href + '/')
                                    return (
                                        <li key={item.href}>
                                            <Link
                                                href={item.href}
                                                className={cn(
                                                    'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13.5px] font-medium transition-all duration-200',
                                                    isActive
                                                        ? 'bg-gradient-to-r from-indigo-500/90 to-violet-600/90 text-white shadow-[0_8px_24px_-8px_rgba(99,102,241,0.7)]'
                                                        : 'text-ink-200/70 hover:bg-white/[0.06] hover:text-white',
                                                )}
                                            >
                                                {isActive && (
                                                    <span className="absolute -left-4 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-gold-300 to-gold-500" />
                                                )}
                                                <Icon
                                                    size={17}
                                                    strokeWidth={2}
                                                    className={cn(
                                                        'transition-transform duration-200',
                                                        !isActive &&
                                                            'group-hover:scale-110',
                                                    )}
                                                />
                                                {item.label}
                                            </Link>
                                        </li>
                                    )
                                })}
                            </ul>
                        </div>
                    ))}
                </nav>

                {/* Bottom: status + upload CTA */}
                <div className="relative px-4 pb-5">
                    <Link
                        href="/upload"
                        className="group flex items-center gap-3 rounded-xl border border-indigo-400/20 bg-gradient-to-r from-indigo-500/15 to-violet-500/10 px-4 py-3 transition-all duration-200 hover:border-indigo-400/40 hover:from-indigo-500/25"
                    >
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-indigo-200 transition-transform duration-200 group-hover:scale-110">
                            <Plus size={16} strokeWidth={2.5} />
                        </span>
                        <span className="text-[13px] font-semibold text-indigo-100">
                            New analysis
                        </span>
                    </Link>
                    <div className="mt-4 flex items-center justify-between px-1 text-[10.5px] text-ink-300/40">
                        <span className="flex items-center gap-1.5">
                            <ShieldCheck size={12} />
                            SOC 2 ready
                        </span>
                        <span>v0.1.0</span>
                    </div>
                </div>

                {/* Edge divider */}
                <div className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-white/[0.08] to-transparent" />
            </aside>
        </>
    )
}
