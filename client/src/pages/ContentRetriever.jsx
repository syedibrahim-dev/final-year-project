import React, { useState } from 'react';
import { Search, Link, BookOpen, Loader2, AlertCircle } from 'lucide-react';
import { content as contentApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { Input, Button, PageHeader, RelatedLinks } from '../components/ui';

// Component to display a single search result chunk
const ChunkResult = ({ chunk, source, page, score, index }) => (
    <div className="p-4 border border-gray-200 rounded-lg bg-gray-50 shadow-sm hover:shadow-md transition duration-150">
        <div className="flex items-start justify-between mb-2">
            <span className="text-xs font-semibold text-gray-400">Result #{index + 1}</span>
            {score && (
                <span className="bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-semibold text-xs">
                    Score: {(score * 100).toFixed(1)}%
                </span>
            )}
        </div>
        
        <p className="text-sm text-gray-800 mb-3 leading-relaxed">
            {chunk}
        </p>
        
        <div className="flex justify-between items-center text-xs text-gray-500 pt-2 border-t border-gray-200">
            <span className="flex items-center space-x-1">
                <Link size={12} className="text-indigo-500"/>
                <span className="font-medium">{source}</span>
            </span>
            {page && (
                <span className="text-gray-400">
                    Page {page}
                </span>
            )}
        </div>
    </div>
);

function ContentRetrieverView() {
    const { token, user } = useAuth();
    const orgId = user?.organization_id;
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [searched, setSearched] = useState(false);
    const [resultCount, setResultCount] = useState(5);

    const handleSearch = async (e) => {
        e.preventDefault();
        
        console.log('🔍 Starting search...', { query, orgId, resultCount });
        
        setError('');
        setLoading(true);
        setResults([]);
        setSearched(true);
        
        if (!query.trim()) {
            setError("Please enter a search query.");
            setLoading(false);
            return;
        }

        if (!orgId) {
            setError("Organization ID is missing. Please log in again.");
            setLoading(false);
            return;
        }

        try {
            console.log('📡 Calling retrieve API...');
            
            // ✅ FIXED: Handle different API response formats
            const response = await contentApi.retrieve(orgId, query.trim(), resultCount, token);
            
            console.log('✅ API Response:', response);
            
            // ✅ FIXED: Handle both array and object responses
            let processedResults = [];
            
            if (Array.isArray(response)) {
                // Direct array of results
                processedResults = response.map(item => ({
                    chunk: item.content || item.chunk || item.text || '',
                    source: item.source || item.metadata?.source_file || 'Unknown',
                    page: item.page || item.metadata?.page || null,
                    score: item.relevance_score || item.score || item.distance || null
                }));
            } else if (response.results && Array.isArray(response.results)) {
                // Response with results array
                processedResults = response.results.map(item => ({
                    chunk: item.content || item.chunk || item.text || '',
                    source: item.source || item.metadata?.source_file || 'Unknown',
                    page: item.page || item.metadata?.page || null,
                    score: item.relevance_score || item.score || item.distance || null
                }));
            } else if (response.chunks && Array.isArray(response.chunks)) {
                // Response with chunks array
                processedResults = response.chunks.map(item => ({
                    chunk: item.content || item.chunk || item.text || '',
                    source: item.source || item.metadata?.source_file || 'Unknown',
                    page: item.page || item.metadata?.page || null,
                    score: item.relevance_score || item.score || item.distance || null
                }));
            }
            
            console.log('📊 Processed results:', processedResults.length, 'items');
            
            if (processedResults.length === 0) {
                setError('No relevant content found. Try rephrasing your query or uploading more content.');
            }
            
            setResults(processedResults);
            
        } catch (err) {
            console.error('❌ Search error:', err);
            
            // ✅ IMPROVED: Better error messages
            if (err.message.includes('404')) {
                setError('No content found in knowledge base. Please upload training materials first.');
            } else if (err.message.includes('401') || err.message.includes('403')) {
                setError('Authentication error. Please log in again.');
            } else if (err.message.includes('500')) {
                setError('Server error. The knowledge base might not be initialized yet.');
            } else {
                setError(err.message || 'Failed to search knowledge base. Please try again.');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <PageHeader
                title="Search Docs"
                subtitle="Run semantic searches across your training content to find specific information"
                backTo="/dashboard"
                backLabel="Dashboard"
            />

            {/* Search Form */}
            <form onSubmit={handleSearch} className="space-y-4 mb-8 max-w-2xl">
                <Input 
                    name="query" 
                    label="Your Question" 
                    type="text" 
                    placeholder="e.g., What is our policy on competitor pricing?"
                    value={query} 
                    onChange={(e) => setQuery(e.target.value)} 
                    required 
                />
                
                <div className="flex items-center gap-4">
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Number of Results
                        </label>
                        <select
                            value={resultCount}
                            onChange={(e) => setResultCount(Number(e.target.value))}
                            className="w-full p-3 border border-gray-300 rounded-lg bg-white focus:ring-indigo-500 focus:border-indigo-500"
                        >
                            <option value={3}>3 results</option>
                            <option value={5}>5 results</option>
                            <option value={10}>10 results</option>
                            <option value={15}>15 results</option>
                        </select>
                    </div>
                    
                    <div className="flex-1 flex items-end">
                        <Button type="submit" loading={loading} disabled={loading || !query.trim()}>
                            {loading ? (
                                <>
                                    <Loader2 size={16} className="animate-spin mr-2"/> 
                                    Searching...
                                </>
                            ) : (
                                <>
                                    <Search size={16} className="mr-2"/> 
                                    Search
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </form>
            
            {/* Error Display */}
            {error && (
                <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start space-x-3">
                    <AlertCircle size={20} className="text-red-600 flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="text-sm font-semibold text-red-800">Search Failed</p>
                        <p className="text-sm text-red-700 mt-1">{error}</p>
                    </div>
                </div>
            )}
            
            {/* Results Display */}
            <div className="mt-8">
                <div className="flex items-center justify-between mb-4">
                    <h4 className="text-xl font-semibold text-gray-800">
                        {results.length > 0 ? `Found ${results.length} Relevant Passage${results.length !== 1 ? 's' : ''}` : 'Search Results'}
                    </h4>
                    {searched && results.length > 0 && (
                        <span className="text-sm text-gray-500">
                            Query: "{query}"
                        </span>
                    )}
                </div>
                
                {/* Loading State */}
                {loading && (
                    <div className="text-center py-12">
                        <Loader2 className="animate-spin inline-block h-8 w-8 text-indigo-600 mb-3" />
                        <p className="text-gray-600">Searching knowledge base...</p>
                    </div>
                )}
                
                {/* Empty State - Not Searched Yet */}
                {!loading && !searched && (
                    <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200">
                        <Search size={48} className="text-gray-400 mx-auto mb-3" />
                        <p className="text-gray-500">Enter a query above to search your knowledge base</p>
                    </div>
                )}
                
                {/* Empty State - No Results */}
                {!loading && searched && results.length === 0 && !error && (
                    <div className="text-center py-12 bg-yellow-50 rounded-lg border border-yellow-200">
                        <AlertCircle size={48} className="text-yellow-600 mx-auto mb-3" />
                        <p className="text-gray-700 font-medium">No relevant passages found</p>
                        <p className="text-gray-600 text-sm mt-1">
                            Try rephrasing your query or upload more training materials
                        </p>
                    </div>
                )}
                
                {/* Results List */}
                {!loading && results.length > 0 && (
                    <div className="space-y-4">
                        {results.map((result, index) => (
                            <ChunkResult 
                                key={index} 
                                chunk={result.chunk} 
                                source={result.source} 
                                page={result.page} 
                                score={result.score}
                                index={index}
                            />
                        ))}
                    </div>
                )}
            </div>
            <RelatedLinks links={[
                { label: 'Knowledge Chat',   to: '/knowledge-chat' },
                { label: 'Manage Content',   to: '/content/manage' },
                { label: 'Upload Content',   to: '/content/upload' },
            ]} />
        </>
    );
}

export default ContentRetrieverView;