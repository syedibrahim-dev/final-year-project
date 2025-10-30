import React, { useState, useEffect } from 'react';
import { Book, FileText, Trash2, Loader2, AlertTriangle, CheckCircle } from 'lucide-react';
import { content as contentApi } from '../utils/api'; 
import { Button } from '../App'; // Assuming UI components are exported from App.jsx

// --- Main View to List Uploaded Documents ---
function ContentManagerView({ orgId, token }) {
    const [contentList, setContentList] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [deleteState, setDeleteState] = useState({}); // Track loading/success per item

    // Fetch the list of uploaded documents on mount
    const fetchContent = async () => {
        setLoading(true);
        try {
            const data = await contentApi.listContent(orgId, token);
            setContentList(data);
        } catch (err) {
            setError(err.message || 'Failed to fetch content list.');
        } finally {
            setLoading(false);
        }
    };
    
    useEffect(() => {
        fetchContent();
    }, [orgId, token]);

    const handleDelete = async (contentId) => {
        // Use window.confirm for simplicity, replace with modal in production
        if (!window.confirm("Are you sure you want to delete this document? This will remove all associated vectors from the knowledge base.")) {
            return;
        }

        setDeleteState(prev => ({ ...prev, [contentId]: { loading: true, error: null } }));
        setError('');

        try {
            // Call the new delete API endpoint
            await contentApi.deleteContent(orgId, contentId, token);
            setDeleteState(prev => ({ ...prev, [contentId]: { loading: false, error: null } }));
            // Refresh the list
            fetchContent();
        } catch (err) {
            setError(err.message || 'Failed to delete content.');
            setDeleteState(prev => ({ ...prev, [contentId]: { loading: false, error: err.message } }));
        }
    };

    return (
        <div>
            <h3 className="text-2xl font-bold text-gray-800 mb-4 flex items-center space-x-3">
                <Book size={24} className="text-indigo-600" /> 
                <span>Manage Training Content</span>
            </h3>
            <p className="mb-6 text-gray-600">
                View, manage, and delete uploaded documents. Deleting a document removes it from the search index.
            </p>
            
            {loading && <div className="text-center p-4"><Loader2 className="animate-spin inline-block h-6 w-6 text-indigo-600" /></div>}
            {error && <p className="mt-4 p-3 bg-red-100 text-sm font-medium text-red-700 rounded-lg">{error}</p>}
            
            {!loading && contentList.length === 0 && (
                <p className="text-gray-500 p-6 bg-gray-50 rounded-lg">
                    No training documents have been uploaded yet. 
                    Go to the <strong className="text-indigo-600">"Upload Content"</strong> tab to get started.
                </p>
            )}

            <div className="space-y-3">
                {contentList.map(content => (
                    <div key={content.id} className="p-4 border rounded-lg flex flex-col sm:flex-row justify-between sm:items-center bg-white shadow-sm">
                        <div>
                            <p className="font-semibold text-gray-800 flex items-center">
                                <FileText size={16} className="mr-2 text-indigo-500"/>
                                {content.file_name}
                            </p>
                            <p className="text-xs text-gray-500 mt-1 sm:ml-8">
                                Chunks: {content.chunk_count} | 
                                Uploaded: {new Date(content.upload_date).toLocaleDateString()} |
                                ID: {content.id}
                            </p>
                        </div>
                        <Button 
                            onClick={() => handleDelete(content.id)} 
                            loading={deleteState[content.id]?.loading}
                            className="w-full sm:w-auto mt-3 sm:mt-0 bg-red-600 hover:bg-red-700 focus:ring-red-500"
                        >
                            <Trash2 size={16} className="mr-2"/> Delete
                        </Button>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default ContentManagerView;