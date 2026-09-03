import type { Metadata } from 'next'
import { type ReactNode } from 'react'
import { AuthProvider } from '@/context/AuthContext'
import './globals.css'

export const metadata: Metadata = {
    title: {
        default: 'Legal Doc AI — Contract intelligence, refined',
        template: '%s · Legal Doc AI',
    },
    description:
        'AI-powered contract review and analysis. Detect risks, extract obligations, and understand every clause in seconds.',
    icons: { icon: '/icon.svg' },
}

export default function RootLayout({ children }: { children: ReactNode }) {
    return (
        <html lang="en">
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link
                    rel="preconnect"
                    href="https://fonts.gstatic.com"
                    crossOrigin="anonymous"
                />
                {/* eslint-disable-next-line @next/next/no-page-custom-font */}
                <link
                    href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body>
                <AuthProvider>{children}</AuthProvider>
            </body>
        </html>
    )
}
