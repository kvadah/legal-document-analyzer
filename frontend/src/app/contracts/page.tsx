'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import AppLayout from '@/app/app-layout'
import { apiListDocuments, type DocumentOut } from '@/lib/api-client'

const STATUS_STYLES: Record<string, string> = {
    ingestion_ready: 'bg-green-100 text-green-800',
    analysis_ready: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
}

function formatStatus(status: string): string {
    return status.replace(/_/g, ' ')
}

export default function ContractsPage() {
    const [documents, setDocuments] = useState<DocumentOut[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        async function load() {
            try {
                const data = await apiListDocuments()
                setDocuments(data.items)
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load documents')
            } finally {
                setLoading(false)
            }
        }
        void load()
    }, [])

    return (
        <AppLayout>
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold">Contracts</h1>
                        <p className="text-gray-600 mt-1">
                            View and manage your contract documents
                        </p>
                    </div>
                    <Link
                        href="/upload"
                        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        Upload Document
                    </Link>
                </div>

                {loading && (
                    <div className="bg-white rounded-lg border border-gray-200 p-8 text-center text-gray-500">
                        Loading documents…
                    </div>
                )}

                {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700">
                        {error}
                    </div>
                )}

                {!loading && !error && documents.length === 0 && (
                    <div className="bg-white rounded-lg border border-gray-200 p-8">
                        <div className="text-center">
                            <h3 className="text-lg font-semibold text-gray-900">No documents yet</h3>
                            <p className="text-gray-600 mt-2">
                                Upload your first document to get started with analysis
                            </p>
                            <Link
                                href="/upload"
                                className="inline-block mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                            >
                                Upload Document
                            </Link>
                        </div>
                    </div>
                )}

                {!loading && documents.length > 0 && (
                    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Filename</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Pages</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                                {documents.map(doc => (
                                    <tr key={doc.id}>
                                        <td className="px-6 py-4 text-sm font-medium text-gray-900">{doc.filename}</td>
                                        <td className="px-6 py-4 text-sm text-gray-600">{doc.document_type}</td>
                                        <td className="px-6 py-4 text-sm">
                                            <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${STATUS_STYLES[doc.status] ?? 'bg-gray-100 text-gray-800'}`}>
                                                {formatStatus(doc.status)}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-600">{doc.page_count ?? '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </AppLayout>
    )
}
