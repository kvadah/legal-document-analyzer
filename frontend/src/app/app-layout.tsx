import { ReactNode } from 'react'
import Sidebar from '@/components/layout/Sidebar'
import TopBar from '@/components/layout/TopBar'
import Disclaimer from '@/components/layout/Disclaimer'
import './app-layout.css'

export default function AppLayout({ children }: { children: ReactNode }) {
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
