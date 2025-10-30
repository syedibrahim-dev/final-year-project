import React, { useState } from 'react';
import { Search, Link, BookOpen, Loader2 } from 'lucide-react';
import { content as contentApi } from '../utils/api'; 
// NOTE: Assuming UI components are exported from App.jsx as per our previous setup
import { Input, Button } from '../App'; 

// Component to display a single search result chunk
const ChunkResult = ({ chunk, source, page, score }) => (
    <div className="p-4 border border-gray-200 rounded-lg bg-gray-50 shadow-sm hover:shadow-md transition duration-150">
        <p className="text-sm text-gray-800 mb-2 font-medium">
            "{chunk}"
        </p>
        <div className="flex justify-between items-center text-xs text-gray-500 pt-2 border-t border-gray-100">
            <span className="flex items-center space-x-1">
                <Link size={12} className="text-indigo-500"/>
                <span>Source: {source} (Page {page})</span>
            </span>
            <span className="bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-semibold">
                Relevance: {score ? score.toFixed(3) : 'N/A'}
            </span>
        </div>
    </div>
);

function ContentRetrieverView({ orgId, token }) {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [searched, setSearched] = useState(false); // Track if a search has been performed

    const handleSearch = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        setResults([]);
        setSearched(true); // Mark that a search was attempted
        
        if (!query.trim()) {
            setError("Please enter a search query.");
            setLoading(false);
            return;
        }

        try {
            // Call the retriever API function
            const retrievedData = await contentApi.retrieve(orgId, query.trim(), 4, token);
            setResults(retrievedData);
        } catch (err) {
            setError(err.message || 'Knowledge base retrieval failed.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <h3 className="text-2xl font-bold text-gray-800 mb-6 flex items-center space-x-3 border-b pb-3">
                <BookOpen size={24} className="text-indigo-600"/> 
                <span>Search Knowledge Base (Test Embeddings)</span>
            </h3>
            <p className="mb-6 text-gray-600">
                Ask a question about your sales playbook. If the embeddings worked, the AI will find the most relevant passages.
            </p>

            {/* Search Form */}
            <form onSubmit={handleSearch} className="space-y-4 mb-8 max-w-lg">
                <Input 
                    name="query" 
                    label="Your Question" 
                    type="text" 
                    placeholder="E.g., What is our policy on competitor pricing?"
                    value={query} 
                    onChange={(e) => setQuery(e.target.value)} 
                    required 
                />
                
                <Button type="submit" loading={loading} className="w-full sm:w-auto">
                    {loading ? (
                        <><Loader2 size={16} className="animate-spin mr-2"/> Searching...</>
                    ) : (
                        <><Search size={16} className="mr-2"/> Search</>
                    )}
                </Button>
            </form>
            
            {error && <p className="mt-4 p-3 bg-red-100 text-sm font-medium text-red-700 rounded-lg">{error}</p>}
            
            {/* Results Display */}
            <div className="mt-8">
                <h4 className="text-xl font-semibold text-gray-800 mb-4">
                    Relevant Passages
                </h4>
                
                {!loading && results.length === 0 && searched && !error && (
                    <p className="text-gray-500">No relevant passages found for your query.</p>
                )}
                 {!loading && !searched && (
                    <p className="text-gray-500">Enter a query above to see results.</p>
                )}
                
                <div className="space-y-4">
                    {results.map((result, index) => (
                        <ChunkResult 
                            key={index} 
                            chunk={result.chunk} 
                            source={result.source} 
                            page={result.page} 
                            score={result.score}
                        />
                    ))}
                </div>
            </div>
        </>
    );
}

export default ContentRetrieverView;
