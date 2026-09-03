'use client'

import { useEffect, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/layout/Sidebar'
import TopBar from '@/components/layout/TopBar'
import Disclaimer from '@/components/layout/Disclaimer'
import { useAuth } from '@/context/AuthContext'
import { LogoMark } from '@/components/ui/Logo'
import './app-layout.css'

function Splash() {
    return (
        <div className="bg-ink-950 relative flex min-h-screen items-center justify-center overflow-hidden">
            <div className="pointer-events-none absolute inset-0">
                <div className="bg-grid-dark absolute inset-0 opacity-40" />
                <div className="absolute left-1/2 top-1/2 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-600/20 blur-[120px]" />
            </div>
            <div className="relative flex flex-col items-center gap-6">
                <div className="animate-pulse-ring rounded-3xl">
                    <LogoMark size={56} />
                </div>
                <div className="flex items-center gap-1.5">
                    {[0, 1, 2].map(i => (
                        <span
                            key={i}
                            className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400"
                            style={{ animationDelay: `${i * 150}ms` }}
                        />
                    ))}
                </div>
            </div>
        </div>
    )
}

export default function AppLayout({ children }: { children: ReactNode }) {
    const { user, isLoading } = useAuth()
    const router = useRouter()

    useEffect(() => {
        if (!isLoading && !user) {
            router.replace('/login')
        }
    }, [user, isLoading, router])

    if (isLoading) {
        return <Splash />
    }

    if (!user) return null

    return (
        <div className="relative flex min-h-screen bg-background">
            <div className="bg-grid pointer-events-none fixed inset-0 opacity-50" />
            <Sidebar />
            <div className="app-content relative flex min-w-0 flex-col">
                <TopBar />
                <main className="app-main">{children}</main>
                <Disclaimer />
            </div>
        </div>
    )
}
