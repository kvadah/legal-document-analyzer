'use client'

import { useEffect, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/layout/Sidebar'
import TopBar from '@/components/layout/TopBar'
import Disclaimer from '@/components/layout/Disclaimer'
import { useAuth } from '@/context/AuthContext'
import './app-layout.css'

export default function AppLayout({ children }: { children: ReactNode }) {
    const { user, isLoading } = useAuth()
    const router = useRouter()

    useEffect(() => {
        if (!isLoading && !user) {
            router.replace('/login')
        }
    }, [user, isLoading, router])

    if (isLoading) {
        return (
            <div className="app-loading">
                <div className="app-loading-spinner" />
            </div>
        )
    }

    if (!user) return null

    return (
        <div className="app-container">
            <Sidebar />
            <div className="app-content">
                <TopBar />
                <main className="app-main">
                    {children}
                </main>
                <Disclaimer />
            </div>
        </div>
    )
}
