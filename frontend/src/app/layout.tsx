import type { Metadata } from 'next'
import { ReactNode } from 'react'
import './globals.css'

export const metadata: Metadata = {
    title: 'Legal Document Analyzer',
    description: 'AI-powered contract review and analysis platform',
}

export default function RootLayout({
    children,
}: {
    children: ReactNode
}) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    )
}
