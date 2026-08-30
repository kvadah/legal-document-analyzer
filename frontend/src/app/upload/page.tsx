import AppLayout from '@/app/app-layout'

export default function UploadPage() {
    return (
        <AppLayout>
            <div className="space-y-6">
                <div>
                    <h1 className="text-3xl font-bold">Upload Documents</h1>
                    <p className="text-gray-600 mt-1">
                        Drag and drop your contracts for AI analysis
                    </p>
                </div>

                <div className="bg-white rounded-lg border-2 border-dashed border-gray-300 p-12">
                    <div className="text-center">
                        <svg
                            className="w-16 h-16 mx-auto text-gray-400 mb-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                            />
                        </svg>
                        <h3 className="text-lg font-semibold text-gray-900">
                            Drop files here or click to upload
                        </h3>
                        <p className="text-gray-600 mt-2">
                            Supports PDF, DOCX, and other document formats (max 50MB)
                        </p>
                        <button className="inline-block mt-6 px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                            Select Files
                        </button>
                    </div>
                </div>
            </div>
        </AppLayout>
    )
}
