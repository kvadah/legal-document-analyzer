import AppLayout from '@/app/app-layout'

export default function ContractsPage() {
    return (
        <AppLayout>
            <div className="space-y-6">
                <div>
                    <h1 className="text-3xl font-bold">Contracts</h1>
                    <p className="text-gray-600 mt-1">
                        View and manage your contract documents
                    </p>
                </div>

                <div className="bg-white rounded-lg border border-gray-200 p-8">
                    <div className="text-center">
                        <div className="text-gray-400 mb-4">
                            <svg
                                className="w-16 h-16 mx-auto"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                                />
                            </svg>
                        </div>
                        <h3 className="text-lg font-semibold text-gray-900">No documents yet</h3>
                        <p className="text-gray-600 mt-2">
                            Upload your first document to get started with analysis
                        </p>
                        <a
                            href="/upload"
                            className="inline-block mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                        >
                            Upload Document
                        </a>
                    </div>
                </div>
            </div>
        </AppLayout>
    )
}
