'use client'

import { Search, LogOut, Building2, ChevronDown, UserRound, Bell } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/cn'

const ROLE_LABELS: Record<string, string> = {
    admin: 'Administrator',
    reviewer: 'Reviewer',
    viewer: 'Viewer',
}

const ROLE_BADGE: Record<string, string> = {
    admin: 'bg-gold-100 text-gold-700 ring-gold-500/20',
    reviewer: 'bg-indigo-50 text-indigo-700 ring-indigo-500/20',
    viewer: 'bg-ink-100 text-ink-600 ring-ink-500/15',
}

export default function TopBar() {
    const { user, logout } = useAuth()
    const router = useRouter()
    const [showUserMenu, setShowUserMenu] = useState(false)
    const menuRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        function onClickOutside(e: MouseEvent) {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setShowUserMenu(false)
            }
        }
        function onEscape(e: KeyboardEvent) {
            if (e.key === 'Escape') setShowUserMenu(false)
        }
        document.addEventListener('mousedown', onClickOutside)
        document.addEventListener('keydown', onEscape)
        return () => {
            document.removeEventListener('mousedown', onClickOutside)
            document.removeEventListener('keydown', onEscape)
        }
    }, [])

    async function handleLogout() {
        await logout()
        router.push('/login')
    }

    const name = user?.email?.split('@')[0] ?? ''
    const displayName = name.charAt(0).toUpperCase() + name.slice(1)
    const initials = user?.email?.slice(0, 2).toUpperCase() ?? '?'

    return (
        <header className="glass sticky top-0 z-30 border-b border-ink-100">
            <div className="flex items-center justify-between gap-4 px-6 py-3 lg:px-8">
                {/* Search shortcut */}
                <Link
                    href="/search"
                    className="group hidden max-w-md flex-1 items-center gap-3 rounded-xl border border-ink-100 bg-white/80 px-3.5 py-2 text-sm text-ink-400 shadow-[0_1px_2px_rgba(12,21,38,0.04)] transition-all duration-200 hover:border-ink-200 hover:shadow-soft sm:flex"
                >
                    <Search size={16} className="transition-colors group-hover:text-primary" />
                    <span className="flex-1">Search documents…</span>
                    <span className="kbd">⌘K</span>
                </Link>

                <div className="flex-1 sm:hidden" />

                {/* Right side controls */}
                <div className="flex items-center gap-2">
                    <Link
                        href="/reports"
                        aria-label="Notifications"
                        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-ink-400 transition-colors hover:bg-ink-100/70 hover:text-ink-700"
                    >
                        <Bell size={18} />
                        <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-gold-400 ring-2 ring-white" />
                    </Link>

                    <div className="mx-1 h-6 w-px bg-ink-100" />

                    <div className="relative" ref={menuRef}>
                        <button
                            id="topbar-user-menu-btn"
                            onClick={() => setShowUserMenu(!showUserMenu)}
                            className={cn(
                                'flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition-colors',
                                showUserMenu ? 'bg-ink-100/80' : 'hover:bg-ink-100/70',
                            )}
                        >
                            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-[12px] font-bold text-white ring-2 ring-white">
                                {initials}
                            </span>
                            <span className="hidden text-left leading-tight sm:block">
                                <span className="block max-w-[160px] truncate text-[13px] font-semibold text-ink-800">
                                    {displayName}
                                </span>
                                <span className="block text-[11px] text-ink-400">
                                    {ROLE_LABELS[user?.role ?? ''] ?? user?.role}
                                </span>
                            </span>
                            <ChevronDown
                                size={14}
                                className={cn(
                                    'text-ink-300 transition-transform duration-200',
                                    showUserMenu && 'rotate-180',
                                )}
                            />
                        </button>

                        {showUserMenu && (
                            <div className="animate-scale-in absolute right-0 mt-2.5 w-64 overflow-hidden rounded-xl border border-ink-100 bg-white shadow-lift">
                                <div className="border-b border-ink-50 bg-gradient-to-br from-indigo-50/60 to-white px-4 py-3.5">
                                    <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-ink-400">
                                        <UserRound size={12} /> Account
                                    </p>
                                    <p className="mt-1.5 truncate text-[13.5px] font-semibold text-ink-900">
                                        {user?.email}
                                    </p>
                                    <div className="mt-2 flex items-center gap-2">
                                        <span
                                            className={cn(
                                                'pill',
                                                ROLE_BADGE[user?.role ?? 'viewer'],
                                            )}
                                        >
                                            {ROLE_LABELS[user?.role ?? ''] ?? user?.role}
                                        </span>
                                        <span className="flex items-center gap-1 text-[11.5px] text-ink-400">
                                            <Building2 size={11} />
                                            {user?.orgName}
                                        </span>
                                    </div>
                                </div>
                                <div className="p-1.5">
                                    <button
                                        id="topbar-logout-btn"
                                        onClick={handleLogout}
                                        className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-[13px] font-medium text-rose-600 transition-colors hover:bg-rose-50"
                                    >
                                        <LogOut size={15} />
                                        Sign out
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </header>
    )
}
