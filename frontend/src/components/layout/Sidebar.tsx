'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import {
    FileText,
    Upload,
    Search,
    BarChart3,
    Settings,
    Menu,
    X,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

const NAV_ITEMS = [
    { href: '/contracts', label: 'Contracts', icon: FileText },
    { href: '/upload', label: 'Upload', icon: Upload },
    { href: '/search', label: 'Search', icon: Search },
    { href: '/reports', label: 'Reports', icon: BarChart3 },
    { href: '/admin', label: 'Administration', icon: Settings, adminOnly: true },
]

export default function Sidebar() {
    const [isOpen, setIsOpen] = useState(true)
    const pathname = usePathname()
    const { user } = useAuth()
    const isAdmin = user?.role === 'admin'

    return (
        <>
            {/* Mobile toggle */}
            <button
                id="sidebar-toggle-btn"
                onClick={() => setIsOpen(!isOpen)}
                className="md:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-gray-100 hover:bg-gray-200"
            >
                {isOpen ? <X size={24} /> : <Menu size={24} />}
            </button>

            {/* Sidebar */}
            <aside
                className={`fixed left-0 top-0 h-screen bg-gray-900 text-white transition-all duration-300 ${isOpen ? 'w-64' : 'w-0 overflow-hidden'
                    } md:w-64 md:relative z-40`}
            >
                <nav className="h-full flex flex-col">
                    {/* Logo/Brand */}
                    <div className="p-6 border-b border-gray-800">
                        <h1 className="text-xl font-bold">Legal Doc AI</h1>
                        <p className="text-xs text-gray-400 mt-1">
                            {user?.orgName ?? 'Contract Analysis'}
                        </p>
                    </div>

                    {/* Navigation Items */}
                    <ul className="flex-1 overflow-y-auto py-6 space-y-2 px-3">
                        {NAV_ITEMS.map((item) => {
                            if (item.adminOnly && !isAdmin) return null

                            const Icon = item.icon
                            const isActive = pathname === item.href

                            return (
                                <li key={item.href}>
                                    <Link
                                        href={item.href}
                                        className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${isActive
                                            ? 'bg-blue-600 text-white'
                                            : 'text-gray-300 hover:bg-gray-800'
                                            }`}
                                    >
                                        <Icon size={20} />
                                        <span className="font-medium">{item.label}</span>
                                    </Link>
                                </li>
                            )
                        })}
                    </ul>

                    {/* Footer */}
                    <div className="border-t border-gray-800 p-4 text-xs text-gray-400">
                        <p>v0.1.0</p>
                    </div>
                </nav>
            </aside>

            {/* Mobile overlay */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black bg-opacity-50 md:hidden z-30"
                    onClick={() => setIsOpen(false)}
                />
            )}
        </>
    )
}
