import AppLayout from '@/app/app-layout'

export default function ReportsPage() {
    return (
        <AppLayout>
            <div className="space-y-6">
                <div>
                    <h1 className="text-3xl font-bold">Reports</h1>
                    <p className="text-gray-600 mt-1">
                        Generate and view portfolio reports
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <button className="p-6 rounded-lg border border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-colors text-left">
                        <h3 className="font-semibold text-gray-900">Portfolio Risk Report</h3>
                        <p className="text-sm text-gray-600 mt-1">
                            Summary of risks across all documents
                        </p>
                    </button>

                    <button className="p-6 rounded-lg border border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-colors text-left">
                        <h3 className="font-semibold text-gray-900">Obligation Calendar</h3>
                        <p className="text-sm text-gray-600 mt-1">
                            Timeline of deadlines and obligations
                        </p>
                    </button>
                </div>
            </div>
        </AppLayout>
    )
}
