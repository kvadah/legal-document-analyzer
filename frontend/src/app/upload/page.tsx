'use client'

import { useCallback, useRef, useState } from 'react'
import AppLayout from '@/app/app-layout'
import { apiUploadDocuments, type UploadDocumentResult } from '@/lib/api-client'

const STATUS_LABELS: Record<string, string> = {
    uploaded: 'Queued',
    ocr_processing: 'Running OCR…',
    ocr_complete: 'OCR complete',
    parsing: 'Parsing…',
    chunking: 'Chunking…',
    embedding: 'Generating embeddings…',
    metadata_extraction: 'Extracting metadata…',
    ingestion_ready: 'Ready',
    error: 'Error',
}

export default function UploadPage() {
    const inputRef = useRef<HTMLInputElement>(null)
    const [uploads, setUploads] = useState<UploadDocumentResult[]>([])
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)

    const handleFiles = useCallback(async (fileList: FileList | null) => {
        if (!fileList?.length) return
        setError(null)
        setLoading(true)
        try {
            const results = await apiUploadDocuments(Array.from(fileList))
            setUploads(prev => [...results.documents, ...prev])
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed')
        } finally {
            setLoading(false)
        }
    }, [])

    return (
        <AppLayout>
            <div className="space-y-6">
                <div>
                    <h1 className="text-3xl font-bold">Upload Documents</h1>
                    <p className="text-gray-600 mt-1">
                        Drag and drop your contracts for AI analysis
                    </p>
                </div>

                <div
                    className="bg-white rounded-lg border-2 border-dashed border-gray-300 p-12"
                    onDragOver={e => e.preventDefault()}
                    onDrop={e => {
                        e.preventDefault()
                        void handleFiles(e.dataTransfer.files)
                    }}
                >
                    <div className="text-center">
                        <h3 className="text-lg font-semibold text-gray-900">
                            Drop files here or click to upload
                        </h3>
                        <p className="text-gray-600 mt-2">
                            Supports PDF, DOCX, and other document formats (max 50MB)
                        </p>
                        <input
                            ref={inputRef}
                            type="file"
                            multiple
                            accept=".pdf,.doc,.docx,.txt,.rtf"
                            className="hidden"
                            onChange={e => void handleFiles(e.target.files)}
                        />
                        <button
                            type="button"
                            className="inline-block mt-6 px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
                            disabled={loading}
                            onClick={() => inputRef.current?.click()}
                        >
                            {loading ? 'Uploading…' : 'Select Files'}
                        </button>
                    </div>
                </div>

                {error && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700">
                        {error}
                    </div>
                )}

                {uploads.length > 0 && (
                    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <h2 className="font-semibold">Recent uploads</h2>
                        </div>
                        <ul className="divide-y divide-gray-200">
                            {uploads.map(upload => (
                                <li key={`${upload.document_id}-${upload.filename}`} className="px-6 py-4 flex items-center justify-between">
                                    <div>
                                        <p className="font-medium">{upload.filename}</p>
                                        {upload.possible_duplicate_of && (
                                            <p className="text-sm text-amber-600">
                                                Possible duplicate of an existing document
                                            </p>
                                        )}
                                    </div>
                                    <span className="text-sm text-gray-600">
                                        {STATUS_LABELS[upload.status] ?? upload.status}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </AppLayout>
    )
}
