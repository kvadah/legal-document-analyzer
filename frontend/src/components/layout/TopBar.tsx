'use client'

import { Search, LogOut } from 'lucide-react'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'

const ROLE_LABELS: Record<string, string> = {
    admin: 'Admin',
    reviewer: 'Reviewer',
    viewer: 'Viewer',
}

export default function TopBar() {
    const { user, logout } = useAuth()
    const router = useRouter()
    const [showUserMenu, setShowUserMenu] = useState(false)

    async function handleLogout() {
        await logout()
        router.push('/login')
    }

    const initials = user?.email?.slice(0, 2).toUpperCase() ?? '?' 

    return (
        <div className="bg-white border-b border-gray-200 sticky top-0 z-40">
            <div className="flex items-center justify-between px-6 py-4">
                {/* Search shortcut */}
                <div className="flex-1 max-w-md">
                    <div className="relative">
                        <Search className="absolute left-3 top-3 text-gray-400" size={20} />
                        <input
                            type="text"
                            placeholder="Search documents… (Cmd+K)"
                            className="w-full pl-10 pr-4 py-2 rounded-lg bg-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>
                </div>

                {/* Right side controls */}
                <div className="flex items-center gap-4 ml-4">
                    <div className="relative">
                        <button
                            id="topbar-user-menu-btn"
                            onClick={() => setShowUserMenu(!showUserMenu)}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
                        >
                            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-bold">
                                {initials}
                            </div>
                            <div className="text-left hidden sm:block">
                                <p className="text-sm font-medium leading-tight">{user?.email ?? ''}</p>
                                <p className="text-xs text-gray-500 leading-tight">
                                    {ROLE_LABELS[user?.role ?? ''] ?? user?.role}
                                </p>
                            </div>
                        </button>

                        {showUserMenu && (
                            <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden z-50">
                                <div className="px-4 py-3 border-b border-gray-200">
                                    <p className="text-sm font-medium truncate">{user?.email}</p>
                                    <p className="text-xs text-gray-500">{user?.orgName}</p>
                                </div>
                                <button
                                    id="topbar-logout-btn"
                                    onClick={handleLogout}
                                    className="w-full flex items-center gap-2 px-4 py-3 text-sm text-red-600 hover:bg-red-50 transition-colors"
                                >
                                    <LogOut size={16} />
                                    Sign out
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
