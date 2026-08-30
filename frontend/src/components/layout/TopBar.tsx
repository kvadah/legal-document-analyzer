'use client'

import { Search, User, LogOut } from 'lucide-react'
import { useState } from 'react'

export default function TopBar() {
    const [showUserMenu, setShowUserMenu] = useState(false)

    // TODO: Get current user from auth context

    return (
        <div className="bg-white border-b border-gray-200 sticky top-0 z-40">
            <div className="flex items-center justify-between px-6 py-4">
                {/* Search shortcut */}
                <div className="flex-1 max-w-md">
                    <div className="relative">
                        <Search className="absolute left-3 top-3 text-gray-400" size={20} />
                        <input
                            type="text"
                            placeholder="Search documents... (Cmd+K)"
                            className="w-full pl-10 pr-4 py-2 rounded-lg bg-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>
                </div>

                {/* Right side controls */}
                <div className="flex items-center gap-4 ml-4">
                    {/* User menu */}
                    <div className="relative">
                        <button
                            onClick={() => setShowUserMenu(!showUserMenu)}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
                        >
                            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-bold">
                                U
                            </div>
                            <span className="text-sm font-medium">User</span>
                        </button>

                        {/* Dropdown menu */}
                        {showUserMenu && (
                            <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
                                <div className="px-4 py-3 border-b border-gray-200">
                                    <p className="text-sm font-medium">User Name</p>
                                    <p className="text-xs text-gray-500">user@example.com</p>
                                </div>
                                <button className="w-full flex items-center gap-2 px-4 py-3 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
                                    <LogOut size={16} />
                                    Logout
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
