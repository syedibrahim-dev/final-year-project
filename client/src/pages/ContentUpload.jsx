import React, { useState } from 'react';
import { Upload, FileText } from 'lucide-react';
import { content as contentApi } from '../utils/api'; 
// NOTE: Card, Input, and Button are imported from App.jsx where they are exported
import { Card, Input, Button } from '../App'; 

function ContentUploadView({ orgId, token, user }) {
    const [file, setFile] = useState(null);
    const [productName, setProductName] = useState('');
    const [version, setVersion] = useState('1.0');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError('');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setMessage('');
        
        if (!file) {
            setError("Please select a PDF file.");
            return;
        }
        if (file.type !== 'application/pdf') {
            setError("Only PDF files are currently supported.");
            return;
        }

        // --- CRITICAL FIX: Trim the product name before submission ---
        const trimmedProductName = productName.trim();
        if (!trimmedProductName) {
             setError("Product Name / Topic cannot be empty.");
             return;
        }
        // --- END FIX ---


        setLoading(true);
        try {
            const metadata = { 
                product_name: trimmedProductName, // Use trimmed value
                version: version 
            };
            
            // Call the content API upload function
            const result = await contentApi.upload(orgId, metadata, file, token);
            
            setMessage(`Success! Document "${file.name}" indexed. Chunks: ${result.chunks_indexed}. Content ID: ${result.content_id}`);
            setFile(null); // Clear file state
            document.getElementById('file-input').value = ''; // Clear actual file input
            setProductName('');
            setVersion('1.0');

        } catch (err) {
            // Error handling improved: if error.message is available, use it.
            setError(err.message || 'File upload and indexing failed.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <h3 className="text-2xl font-bold text-gray-800 mb-6 flex items-center space-x-3">
                <Upload size={24} className="text-indigo-600"/> <span>Upload Training Content</span>
            </h3>
            <p className="mb-6 text-gray-600">Upload a PDF document to create a searchable knowledge base for your organization. Indexing may take time.</p>

            <form onSubmit={handleSubmit} className="space-y-6 max-w-lg">
                
                <Input name="product_name" label="Product Name / Topic" type="text" value={productName} onChange={(e) => setProductName(e.target.value)} required />
                
                <Input name="version" label="Version" type="text" value={version} onChange={(e) => setVersion(e.target.value)} required />
                
                <div>
                    <label htmlFor="file-input" className="block text-sm font-medium text-gray-700 mb-1">
                        Select PDF File
                    </label>
                    <input 
                        id="file-input"
                        type="file" 
                        accept=".pdf"
                        onChange={handleFileChange} 
                        required 
                        className="w-full p-3 border border-gray-300 rounded-lg bg-white file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer transition duration-150"
                    />
                    {file && <p className="text-xs mt-2 text-indigo-600 font-medium flex items-center space-x-1"><FileText size={14}/> <span>Ready to upload: {file.name}</span></p>}
                </div>
                
                <Button type="submit" loading={loading} className="bg-green-600 hover:bg-green-700">
                    {loading ? 'Processing & Indexing...' : 'Upload & Index Content'}
                </Button>
            </form>
            
            {error && <p className="mt-4 p-3 bg-red-100 text-sm font-medium text-red-700 rounded-lg">{error}</p>}
            {message && <p className="mt-4 p-3 bg-green-100 text-sm font-medium text-green-700 rounded-lg break-words">{message}</p>}
        </>
    );
}

export default ContentUploadView;
