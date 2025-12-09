import React, { useState } from 'react';
import { Upload, CheckCircle, AlertCircle, Loader2, FileText } from 'lucide-react';
import { content as contentApi } from '../utils/api';
import { Card, Input, Button } from '../App';

export default function ContentUploadView({ orgId, token, user }) {
    const [file, setFile] = useState(null);
    const [version, setVersion] = useState('1.0');
    const [uploading, setUploading] = useState(false);
    const [message, setMessage] = useState('');
    const [uploadResult, setUploadResult] = useState(null);

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            // Validate file type
            const allowedTypes = ['application/pdf', 'text/plain'];
            if (!allowedTypes.includes(selectedFile.type)) {
                setMessage('❌ Only PDF and TXT files are supported');
                setFile(null);
                return;
            }
            
            // Validate file size (max 10MB)
            const maxSize = 10 * 1024 * 1024; // 10MB
            if (selectedFile.size > maxSize) {
                setMessage('❌ File size must be less than 10MB');
                setFile(null);
                return;
            }
            
            setFile(selectedFile);
            setMessage('');
            setUploadResult(null);
        }
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        
        if (!file) {
            setMessage('❌ Please select a file first');
            return;
        }

        setUploading(true);
        setMessage('');
        setUploadResult(null);

        try {
            console.log('📤 Uploading file:', file.name);
            console.log('📦 File type:', file.type);
            console.log('📊 File size:', file.size, 'bytes');
            console.log('🏷️  Version:', version);
            
            const result = await contentApi.upload(orgId, file, version, token);
            
            console.log('✅ Upload successful:', result);
            
            setUploadResult(result);
            setMessage(`✅ File "${file.name}" uploaded successfully!`);
            
            // Reset form
            setFile(null);
            setVersion('1.0');
            
            // Reset file input
            const fileInput = document.getElementById('file-input');
            if (fileInput) fileInput.value = '';
            
        } catch (error) {
            console.error('❌ Upload failed:', error);
            setMessage(`❌ Upload failed: ${error.message}`);
        } finally {
            setUploading(false);
        }
    };

    return (
        <Card title="Upload Training Content" icon={<Upload size={24} />}>
            <p className="mb-6 text-gray-600 text-sm">
                Upload sales training materials (PDF or TXT) to build your knowledge base.
            </p>

            <form onSubmit={handleUpload} className="space-y-6">
                {/* File Input */}
                <div>
                    <label htmlFor="file-input" className="block text-sm font-medium text-gray-700 mb-2">
                        Select Training Document *
                    </label>
                    <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-lg hover:border-indigo-400 transition-colors">
                        <div className="space-y-1 text-center">
                            <FileText className="mx-auto h-12 w-12 text-gray-400" />
                            <div className="flex text-sm text-gray-600">
                                <label
                                    htmlFor="file-input"
                                    className="relative cursor-pointer bg-white rounded-md font-medium text-indigo-600 hover:text-indigo-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500"
                                >
                                    <span>Upload a file</span>
                                    <input
                                        id="file-input"
                                        name="file"
                                        type="file"
                                        className="sr-only"
                                        accept=".pdf,.txt"
                                        onChange={handleFileChange}
                                        disabled={uploading}
                                    />
                                </label>
                                <p className="pl-1">or drag and drop</p>
                            </div>
                            <p className="text-xs text-gray-500">
                                PDF or TXT up to 10MB
                            </p>
                        </div>
                    </div>
                    
                    {/* Selected File Display */}
                    {file && (
                        <div className="mt-3 flex items-center p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
                            <CheckCircle className="text-indigo-600 mr-2" size={20} />
                            <div className="flex-1">
                                <p className="text-sm font-medium text-indigo-900">{file.name}</p>
                                <p className="text-xs text-indigo-700">
                                    {(file.size / 1024).toFixed(2)} KB
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                {/* Version Input */}
                <Input
                    name="version"
                    label="Version Number"
                    type="text"
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    placeholder="e.g., 1.0, 2.1"
                    disabled={uploading}
                    required
                />

                {/* Upload Button */}
                <Button
                    type="submit"
                    loading={uploading}
                    disabled={!file || uploading}
                >
                    {uploading ? (
                        <>
                            <Loader2 className="animate-spin mr-2" size={18} />
                            Uploading and Processing...
                        </>
                    ) : (
                        <>
                            <Upload className="mr-2" size={18} />
                            Upload Document
                        </>
                    )}
                </Button>
            </form>

            {/* Status Messages */}
            {message && (
                <div
                    className={`mt-6 p-4 rounded-lg border ${
                        message.startsWith('✅')
                            ? 'bg-green-50 border-green-200 text-green-800'
                            : 'bg-red-50 border-red-200 text-red-800'
                    }`}
                >
                    <div className="flex items-start">
                        {message.startsWith('✅') ? (
                            <CheckCircle className="mr-3 flex-shrink-0 text-green-600" size={20} />
                        ) : (
                            <AlertCircle className="mr-3 flex-shrink-0 text-red-600" size={20} />
                        )}
                        <div>
                            <p className="font-semibold">{message}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Upload Result Details */}
            {uploadResult && (
                <div className="mt-6 bg-gradient-to-r from-indigo-50 to-blue-50 rounded-lg p-6 border border-indigo-200">
                    <h4 className="font-semibold text-indigo-900 mb-3 flex items-center">
                        <CheckCircle className="mr-2 text-indigo-600" size={20} />
                        Upload Complete
                    </h4>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                            <span className="text-gray-600">Content ID:</span>
                            <p className="font-medium text-gray-900">{uploadResult.content_id}</p>
                        </div>
                        <div>
                            <span className="text-gray-600">File Name:</span>
                            <p className="font-medium text-gray-900">{uploadResult.file_name}</p>
                        </div>
                        <div>
                            <span className="text-gray-600">Version:</span>
                            <p className="font-medium text-gray-900">{uploadResult.version}</p>
                        </div>
                        <div>
                            <span className="text-gray-600">Pages:</span>
                            <p className="font-medium text-gray-900">{uploadResult.page_count}</p>
                        </div>
                        <div>
                            <span className="text-gray-600">Chunks Created:</span>
                            <p className="font-medium text-gray-900">{uploadResult.chunk_count}</p>
                        </div>
                        <div>
                            <span className="text-gray-600">Status:</span>
                            <p className="font-medium text-green-600">
                                {uploadResult.message || 'Ready for training'}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Info Box */}
            <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start">
                    <AlertCircle className="text-blue-600 mr-3 flex-shrink-0" size={20} />
                    <div className="text-sm text-blue-800">
                        <p className="font-semibold mb-1">Upload Tips:</p>
                        <ul className="list-disc list-inside space-y-1">
                            <li>Supported formats: PDF, TXT</li>
                            <li>Maximum file size: 10MB</li>
                            <li>Document will be automatically chunked and embedded</li>
                            <li>Use version numbers to track updates (e.g., 1.0, 1.1, 2.0)</li>
                        </ul>
                    </div>
                </div>
            </div>
        </Card>
    );
}