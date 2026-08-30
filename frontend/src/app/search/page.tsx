import AppLayout from '@/app/app-layout'

export default function SearchPage() {
    return (
        <AppLayout>
            <div className="space-y-6">
                <div>
                    <h1 className="text-3xl font-bold">Search</h1>
                    <p className="text-gray-600 mt-1">
                        Search across all your documents
                    </p>
                </div>

                <div className="bg-white rounded-lg border border-gray-200 p-8">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Search Query
                            </label>
                            <input
                                type="text"
                                placeholder="Enter search term or ask a question..."
                                className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Search Mode
                                </label>
                                <select className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <option>Hybrid</option>
                                    <option>Keyword</option>
                                    <option>Semantic</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Document Type
                                </label>
                                <select className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <option>All Types</option>
                                </select>
                            </div>
                        </div>

                        <button className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium">
                            Search
                        </button>
                    </div>
                </div>
            </div>
        </AppLayout>
    )
}
