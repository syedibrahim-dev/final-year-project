import React, { useState, useEffect } from 'react';
import { Book, FileText, Trash2, Loader2, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import { content as contentApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { Button, PageHeader, RelatedLinks } from '../components/ui';

// --- Single Content Item Component ---
const ContentItem = ({ contentItem, onDelete, deleteState }) => {
    const [showConfirm, setShowConfirm] = useState(false);

    const handleDeleteClick = () => {
        if (showConfirm) {
            onDelete(contentItem);
            setShowConfirm(false);
        } else {
            setShowConfirm(true);
            // Auto-cancel after 3 seconds
            setTimeout(() => setShowConfirm(false), 3000);
        }
    };

    const isDeleting = deleteState[contentItem.id]?.loading;

    return (
        <div 
            className={`p-4 border rounded-lg flex flex-col sm:flex-row justify-between sm:items-center bg-white shadow-sm hover:shadow-md transition-all ${
                isDeleting ? 'opacity-50 pointer-events-none' : ''
            }`}
        >
            <div className="flex-1">
                <p className="font-semibold text-gray-800 flex items-center flex-wrap gap-2">
                    <FileText size={16} className="text-indigo-500 flex-shrink-0"/>
                    <span className="break-all">{contentItem.file_name}</span>
                    {/* Source type badge */}
                    {contentItem.source_type === 'url' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                            🌐 URL
                        </span>
                    )}
                    {contentItem.source_type === 'media' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                            🎥 Media
                        </span>
                    )}
                    {(!contentItem.source_type || contentItem.source_type === 'document') && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                            📄 Document
                        </span>
                    )}
                </p>
                
                <div className="text-xs text-gray-500 mt-2 space-y-1 sm:ml-8">
                    <p>
                        📦 <strong>Chunks:</strong> {contentItem.chunk_count || 0} | 
                        📄 <strong>Pages:</strong> {contentItem.page_count || 'N/A'} |
                        📝 <strong>Version:</strong> {contentItem.version || '1.0'}
                    </p>
                    {contentItem.source_url && (
                        <p>
                            🔗 <strong>Source:</strong>{' '}
                            <a href={contentItem.source_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">
                                {contentItem.source_url.length > 60 ? contentItem.source_url.substring(0, 60) + '...' : contentItem.source_url}
                            </a>
                        </p>
                    )}
                    <p>
                        📅 <strong>Uploaded:</strong> {new Date(contentItem.upload_date).toLocaleString()}
                    </p>
                    <p>
                        👤 <strong>Uploader ID:</strong> {contentItem.uploader_id}
                    </p>
                    <p className="text-gray-400">
                        🔑 <strong>Content ID:</strong> {contentItem.content_id}
                    </p>
                    <p className="text-gray-400">
                        🆔 <strong>Database ID:</strong> {contentItem.id}
                    </p>
                </div>
                
                {/* Error for this specific item */}
                {deleteState[contentItem.id]?.error && (
                    <div className="text-xs text-red-600 mt-2 sm:ml-8 bg-red-50 p-2 rounded">
                        ⚠️ {deleteState[contentItem.id].error}
                    </div>
                )}
            </div>
            
            <div className="mt-3 sm:mt-0 sm:ml-4">
                <Button 
                    onClick={handleDeleteClick}
                    loading={isDeleting}
                    disabled={isDeleting}
                    className={`w-full sm:w-auto ${
                        showConfirm 
                            ? 'bg-red-700 hover:bg-red-800' 
                            : 'bg-red-600 hover:bg-red-700'
                    } focus:ring-red-500 disabled:opacity-50`}
                >
                    {isDeleting ? (
                        <>
                            <Loader2 size={16} className="mr-2 animate-spin"/> Deleting...
                        </>
                    ) : showConfirm ? (
                        <>
                            <AlertTriangle size={16} className="mr-2"/> Click to Confirm
                        </>
                    ) : (
                        <>
                            <Trash2 size={16} className="mr-2"/> Delete
                        </>
                    )}
                </Button>
            </div>
        </div>
    );
};

// --- Main View to List Uploaded Documents ---
function ContentManagerView() {
    const { token, user } = useAuth();
    const orgId = user?.organization_id;
    const [contentList, setContentList] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [deleteState, setDeleteState] = useState({});
    const [refreshing, setRefreshing] = useState(false);

    // ✅ Fetch the list of uploaded documents
    const fetchContent = async (isRefresh = false) => {
        if (isRefresh) {
            setRefreshing(true);
        } else {
            setLoading(true);
        }
        
        setError('');
        
        console.log('📚 Fetching content list...', { orgId });
        
        try {
            const data = await contentApi.listContent(orgId, token);
            
            console.log('✅ Content list received:', data);
            
            // ✅ Handle different response formats
            let processedList = [];
            
            if (Array.isArray(data)) {
                processedList = data;
            } else if (data.items && Array.isArray(data.items)) {
                processedList = data.items;
            } else if (data.contents && Array.isArray(data.contents)) {
                processedList = data.contents;
            } else {
                console.warn('⚠️ Unexpected response format:', data);
                processedList = [];
            }
            
            console.log('📊 Processed content list:', processedList.length, 'items');
            
            setContentList(processedList);
            
        } catch (err) {
            console.error('❌ Failed to fetch content:', err);
            
            // ✅ Better error messages
            if (err.message.includes('404')) {
                setError('No content found. Upload training materials to get started.');
            } else if (err.message.includes('401') || err.message.includes('403')) {
                setError('Authentication error. Please log in again.');
            } else {
                setError(err.message || 'Failed to fetch content list.');
            }
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };
    
    // ✅ Fetch on mount
    useEffect(() => {
        if (orgId && token) {
            fetchContent();
        } else {
            console.warn('⚠️ Missing orgId or token');
            setError('Missing organization ID or token. Please log in again.');
            setLoading(false);
        }
    }, [orgId, token]);

    // ✅ Handle delete with better error handling
    const handleDelete = async (contentItem) => {
        console.log('🗑️ Deleting content:', {
            dbId: contentItem.id,
            contentId: contentItem.content_id,
            fileName: contentItem.file_name
        });
        
        setDeleteState(prev => ({ 
            ...prev, 
            [contentItem.id]: { loading: true, error: null } 
        }));
        setError('');
        setSuccessMessage('');

        try {
            // ✅ FIXED: Use content_id instead of database id
            const contentIdToDelete = contentItem.content_id || contentItem.id;
            
            console.log('📡 Calling delete API...', { 
                orgId, 
                contentId: contentIdToDelete,
                fileName: contentItem.file_name 
            });
            
            // ✅ Use content_id from the item
            await contentApi.deleteContent(orgId, contentIdToDelete, token);
            
            console.log('✅ Content deleted successfully');
            
            setDeleteState(prev => ({ 
                ...prev, 
                [contentItem.id]: { loading: false, error: null } 
            }));
            
            setSuccessMessage(`"${contentItem.file_name}" deleted successfully!`);
            
            // Remove from list immediately for better UX
            setContentList(prev => prev.filter(item => item.id !== contentItem.id));
            
            // Refresh the list after 1 second to ensure sync
            setTimeout(() => {
                fetchContent(true);
                setSuccessMessage('');
            }, 1500);
            
        } catch (err) {
            console.error('❌ Delete failed:', err);
            
            let errorMsg = err.message || 'Failed to delete content.';
            
            // ✅ Better error messages
            if (err.message.includes('404')) {
                errorMsg = 'Content not found in database. It may have already been deleted.';
            } else if (err.message.includes('403') || err.message.includes('401')) {
                errorMsg = 'Permission denied. You may not have access to delete this content.';
            }
            
            setError(`Failed to delete "${contentItem.file_name}": ${errorMsg}`);
            
            setDeleteState(prev => ({ 
                ...prev, 
                [contentItem.id]: { loading: false, error: errorMsg } 
            }));
            
            // Refresh to see current state
            setTimeout(() => fetchContent(true), 1000);
        }
    };

    // ✅ Manual refresh
    const handleRefresh = () => {
        console.log('🔄 Manual refresh triggered');
        fetchContent(true);
    };

    return (
        <div>
            <PageHeader
                title="Manage Content"
                subtitle="View, search, and delete training documents in your knowledge base"
                backTo="/dashboard"
                backLabel="Dashboard"
                action={
                    <button
                        onClick={handleRefresh}
                        disabled={refreshing}
                        className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
                    >
                        <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
                        <span>{refreshing ? 'Refreshing…' : 'Refresh'}</span>
                    </button>
                }
            />

            {/* Loading State */}
            {loading && (
                <div className="text-center p-12">
                    <Loader2 className="animate-spin inline-block h-8 w-8 text-indigo-600 mb-3" />
                    <p className="text-gray-500">Loading content...</p>
                </div>
            )}
            
            {/* Success Message */}
            {successMessage && (
                <div className="mb-4 p-3 bg-green-100 text-sm font-medium text-green-700 rounded-lg flex items-center">
                    <CheckCircle size={18} className="mr-2 flex-shrink-0" />
                    {successMessage}
                </div>
            )}
            
            {/* Error Message */}
            {error && (
                <div className="mb-4 p-3 bg-red-100 text-sm font-medium text-red-700 rounded-lg flex items-center">
                    <AlertTriangle size={18} className="mr-2 flex-shrink-0" />
                    <div>
                        <p className="font-semibold">Error</p>
                        <p>{error}</p>
                    </div>
                </div>
            )}
            
            {/* Empty State */}
            {!loading && contentList.length === 0 && !error && (
                <div className="text-gray-500 p-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300 text-center">
                    <FileText size={48} className="text-gray-400 mx-auto mb-3" />
                    <p className="text-lg font-medium text-gray-700 mb-2">
                        No knowledge sources yet
                    </p>
                    <p>
                        Add training materials from documents, websites, or audio/video.
                    </p>
                    <p className="mt-2">
                        Go to <strong className="text-indigo-600">"Add Knowledge Sources"</strong> to get started.
                    </p>
                </div>
            )}

            {/* Content List */}
            {!loading && contentList.length > 0 && (
                <>
                    <div className="mb-3 text-sm text-gray-600">
                        Showing {contentList.length} document{contentList.length !== 1 ? 's' : ''}
                    </div>
                    
                    <div className="space-y-3">
                        {contentList.map(contentItem => (
                            <ContentItem
                                key={contentItem.id}
                                contentItem={contentItem}
                                onDelete={handleDelete}
                                deleteState={deleteState}
                            />
                        ))}
                    </div>
                </>
            )}
            <RelatedLinks links={[
                { label: 'Upload Content',  to: '/content/upload' },
                { label: 'Knowledge Chat',  to: '/knowledge-chat' },
            ]} />
        </div>
    );
}

export default ContentManagerView;