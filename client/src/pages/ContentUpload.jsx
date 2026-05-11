import React, { useState } from 'react';
import { Upload, CheckCircle, AlertCircle, Loader2, FileText, Globe, Video, Link } from 'lucide-react';
import { content as contentApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { Input, Button, PageHeader, RelatedLinks } from '../components/ui';

// ── Tab Button ──
const TabButton = ({ active, icon: Icon, label, onClick }) => (
    <button
        onClick={onClick}
        className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-all ${
            active
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
        }`}
    >
        <Icon size={16} />
        {label}
    </button>
);

// ── Success Result Card ──
const ResultCard = ({ result, type }) => (
    <div className="mt-6 bg-gradient-to-r from-blue-50 to-teal-50 rounded-lg p-6 border border-blue-200">
        <h4 className="font-semibold text-blue-900 mb-3 flex items-center">
            <CheckCircle className="mr-2 text-blue-600" size={20} />
            {type === 'url' ? 'URL Scraped' : type === 'media' ? 'Media Transcribed' : 'Upload Complete'}
        </h4>
        <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
                <span className="text-stone-600">Content ID:</span>
                <p className="font-medium text-stone-800">{result.content_id}</p>
            </div>
            <div>
                <span className="text-stone-600">Source:</span>
                <p className="font-medium text-stone-800">{result.file_name}</p>
            </div>
            {result.word_count && (
                <div>
                    <span className="text-stone-600">Words:</span>
                    <p className="font-medium text-stone-800">{result.word_count.toLocaleString()}</p>
                </div>
            )}
            {result.title && (
                <div>
                    <span className="text-stone-600">Title:</span>
                    <p className="font-medium text-stone-800">{result.title}</p>
                </div>
            )}
            {result.duration !== undefined && (
                <div>
                    <span className="text-stone-600">Duration:</span>
                    <p className="font-medium text-stone-800">{Math.round(result.duration)}s</p>
                </div>
            )}
            {result.language && (
                <div>
                    <span className="text-stone-600">Language:</span>
                    <p className="font-medium text-stone-800">{result.language}</p>
                </div>
            )}
            <div>
                <span className="text-gray-600">Chunks Created:</span>
                <p className="font-medium text-gray-900">{result.chunk_count}</p>
            </div>
            {result.page_count !== undefined && (
                <div>
                    <span className="text-gray-600">Pages:</span>
                    <p className="font-medium text-gray-900">{result.page_count}</p>
                </div>
            )}
            <div className="col-span-2">
                <span className="text-gray-600">Status:</span>
                <p className="font-medium text-green-600">{result.message || 'Ready for training'}</p>
            </div>
        </div>
    </div>
);

// ── Status Message ──
const StatusMessage = ({ message }) => {
    if (!message) return null;
    const isSuccess = message.startsWith('✅');
    return (
        <div className={`mt-6 p-4 rounded-lg border ${
            isSuccess ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'
        }`}>
            <div className="flex items-start">
                {isSuccess ? (
                    <CheckCircle className="mr-3 flex-shrink-0 text-green-600" size={20} />
                ) : (
                    <AlertCircle className="mr-3 flex-shrink-0 text-red-600" size={20} />
                )}
                <p className="font-semibold">{message}</p>
            </div>
        </div>
    );
};

export default function ContentUploadView() {
    const { token, user } = useAuth();
    const orgId = user?.organization_id;
    const [activeTab, setActiveTab] = useState('document');
    
    // Document upload state
    const [file, setFile] = useState(null);
    const [version, setVersion] = useState('1.0');
    
    // URL scrape state
    const [url, setUrl] = useState('');
    const [urlVersion, setUrlVersion] = useState('1.0');
    
    // Media upload state
    const [mediaFile, setMediaFile] = useState(null);
    const [mediaVersion, setMediaVersion] = useState('1.0');
    const [language, setLanguage] = useState('en');
    
    // Shared state
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState('');
    const [result, setResult] = useState(null);

    // ── Document Upload Handler ──
    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            const allowedTypes = ['application/pdf', 'text/plain'];
            if (!allowedTypes.includes(selectedFile.type)) {
                setMessage('❌ Only PDF and TXT files are supported');
                setFile(null);
                return;
            }
            const maxSize = 10 * 1024 * 1024;
            if (selectedFile.size > maxSize) {
                setMessage('❌ File size must be less than 10MB');
                setFile(null);
                return;
            }
            setFile(selectedFile);
            setMessage('');
            setResult(null);
        }
    };

    const handleDocumentUpload = async (e) => {
        e.preventDefault();
        if (!file) { setMessage('❌ Please select a file first'); return; }
        setLoading(true); setMessage(''); setResult(null);
        try {
            const res = await contentApi.upload(orgId, file, version, token);
            setResult(res);
            setMessage(`✅ File "${file.name}" uploaded successfully!`);
            setFile(null); setVersion('1.0');
            const fileInput = document.getElementById('file-input');
            if (fileInput) fileInput.value = '';
        } catch (error) {
            setMessage(`❌ Upload failed: ${error.message}`);
        } finally { setLoading(false); }
    };

    // ── URL Scrape Handler ──
    const handleUrlScrape = async (e) => {
        e.preventDefault();
        if (!url.trim()) { setMessage('❌ Please enter a URL'); return; }
        setLoading(true); setMessage(''); setResult(null);
        try {
            const res = await contentApi.scrapeUrl(orgId, url.trim(), urlVersion, token);
            setResult(res);
            setMessage(`✅ URL scraped successfully! ${res.word_count} words extracted.`);
            setUrl(''); setUrlVersion('1.0');
        } catch (error) {
            setMessage(`❌ Scraping failed: ${error.message}`);
        } finally { setLoading(false); }
    };

    // ── Media Upload Handler ──
    const handleMediaChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            const allowedExts = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.mp4', '.webm', '.mkv', '.avi', '.mov'];
            const ext = '.' + selectedFile.name.split('.').pop().toLowerCase();
            if (!allowedExts.includes(ext)) {
                setMessage(`❌ File type ${ext} not supported. Use: ${allowedExts.join(', ')}`);
                setMediaFile(null);
                return;
            }
            const maxSize = 100 * 1024 * 1024;
            if (selectedFile.size > maxSize) {
                setMessage('❌ File size must be less than 100MB');
                setMediaFile(null);
                return;
            }
            setMediaFile(selectedFile);
            setMessage('');
            setResult(null);
        }
    };

    const handleMediaUpload = async (e) => {
        e.preventDefault();
        if (!mediaFile) { setMessage('❌ Please select a media file first'); return; }
        setLoading(true); setMessage(''); setResult(null);
        try {
            const res = await contentApi.uploadMedia(orgId, mediaFile, mediaVersion, language, token);
            setResult(res);
            setMessage(`✅ Media transcribed! ${res.word_count} words from ${Math.round(res.duration)}s audio.`);
            setMediaFile(null); setMediaVersion('1.0');
            const mediaInput = document.getElementById('media-input');
            if (mediaInput) mediaInput.value = '';
        } catch (error) {
            setMessage(`❌ Transcription failed: ${error.message}`);
        } finally { setLoading(false); }
    };

    const switchTab = (tab) => {
        setActiveTab(tab);
        setMessage('');
        setResult(null);
    };

    return (
        <div>
        <PageHeader
            title="Upload Content"
            subtitle="Add training materials to your knowledge base — documents, URLs, or media"
            backTo="/dashboard"
            backLabel="Dashboard"
        />
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <p className="mb-4 text-slate-500 text-sm">
                Supported: PDF, DOCX, TXT, MP3, MP4, or import from a URL.
            </p>

            {/* Tab Selector */}
            <div className="flex gap-2 mb-6">
                <TabButton active={activeTab === 'document'} icon={FileText} label="Document" onClick={() => switchTab('document')} />
                <TabButton active={activeTab === 'url'} icon={Globe} label="Website URL" onClick={() => switchTab('url')} />
                <TabButton active={activeTab === 'media'} icon={Video} label="Audio/Video" onClick={() => switchTab('media')} />
            </div>

            {/* ══════ Document Upload Tab ══════ */}
            {activeTab === 'document' && (
                <form onSubmit={handleDocumentUpload} className="space-y-6">
                    <div>
                        <label htmlFor="file-input" className="block text-sm font-medium text-gray-700 mb-2">
                            Select Training Document *
                        </label>
                        <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-lg hover:border-indigo-400 transition-colors">
                            <div className="space-y-1 text-center">
                                <FileText className="mx-auto h-12 w-12 text-gray-400" />
                                <div className="flex text-sm text-gray-600">
                                    <label htmlFor="file-input" className="relative cursor-pointer bg-white rounded-md font-medium text-indigo-600 hover:text-indigo-500">
                                        <span>Upload a file</span>
                                        <input id="file-input" type="file" className="sr-only" accept=".pdf,.txt" onChange={handleFileChange} disabled={loading} />
                                    </label>
                                    <p className="pl-1">or drag and drop</p>
                                </div>
                                <p className="text-xs text-gray-500">PDF or TXT up to 10MB</p>
                            </div>
                        </div>
                        {file && (
                            <div className="mt-3 flex items-center p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
                                <CheckCircle className="text-indigo-600 mr-2" size={20} />
                                <div className="flex-1">
                                    <p className="text-sm font-medium text-indigo-900">{file.name}</p>
                                    <p className="text-xs text-indigo-700">{(file.size / 1024).toFixed(2)} KB</p>
                                </div>
                            </div>
                        )}
                    </div>
                    <Input name="version" label="Version Number" type="text" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="e.g., 1.0" disabled={loading} required />
                    <Button type="submit" loading={loading} disabled={!file || loading}>
                        {loading ? (<><Loader2 className="animate-spin mr-2" size={18} />Uploading...</>) : (<><Upload className="mr-2" size={18} />Upload Document</>)}
                    </Button>
                </form>
            )}

            {/* ══════ URL Scrape Tab ══════ */}
            {activeTab === 'url' && (
                <form onSubmit={handleUrlScrape} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">Website URL *</label>
                        <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <Link size={16} className="text-gray-400" />
                            </div>
                            <input
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="https://www.example.com/product-page"
                                className="block w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                                disabled={loading}
                                required
                            />
                        </div>
                        <p className="mt-1.5 text-xs text-gray-500">
                            Paste any webpage URL — we'll extract the text content automatically. Works with most websites including JS-rendered pages.
                        </p>
                    </div>
                    <Input name="url-version" label="Version Number" type="text" value={urlVersion} onChange={(e) => setUrlVersion(e.target.value)} placeholder="e.g., 1.0" disabled={loading} required />
                    <Button type="submit" loading={loading} disabled={!url.trim() || loading}>
                        {loading ? (<><Loader2 className="animate-spin mr-2" size={18} />Scraping website...</>) : (<><Globe className="mr-2" size={18} />Scrape URL</>)}
                    </Button>

                    {/* URL Tips */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <div className="flex items-start">
                            <AlertCircle className="text-blue-600 mr-3 flex-shrink-0" size={20} />
                            <div className="text-sm text-blue-800">
                                <p className="font-semibold mb-1">Tips:</p>
                                <ul className="list-disc list-inside space-y-1">
                                    <li>Use product pages, FAQ pages, or about pages for best results</li>
                                    <li>JS-heavy pages are auto-detected and rendered with a headless browser</li>
                                    <li>The scraped content becomes available for roleplay and MCQs immediately</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </form>
            )}

            {/* ══════ Media Upload Tab ══════ */}
            {activeTab === 'media' && (
                <form onSubmit={handleMediaUpload} className="space-y-6">
                    <div>
                        <label htmlFor="media-input" className="block text-sm font-medium text-gray-700 mb-2">
                            Select Audio or Video File *
                        </label>
                        <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-lg hover:border-purple-400 transition-colors">
                            <div className="space-y-1 text-center">
                                <Video className="mx-auto h-12 w-12 text-gray-400" />
                                <div className="flex text-sm text-gray-600">
                                    <label htmlFor="media-input" className="relative cursor-pointer bg-white rounded-md font-medium text-purple-600 hover:text-purple-500">
                                        <span>Upload media</span>
                                        <input id="media-input" type="file" className="sr-only" accept=".mp3,.wav,.m4a,.ogg,.flac,.mp4,.webm,.mkv,.avi,.mov" onChange={handleMediaChange} disabled={loading} />
                                    </label>
                                    <p className="pl-1">or drag and drop</p>
                                </div>
                                <p className="text-xs text-gray-500">MP3, WAV, MP4, WebM, etc. up to 100MB</p>
                            </div>
                        </div>
                        {mediaFile && (
                            <div className="mt-3 flex items-center p-3 bg-purple-50 border border-purple-200 rounded-lg">
                                <CheckCircle className="text-purple-600 mr-2" size={20} />
                                <div className="flex-1">
                                    <p className="text-sm font-medium text-purple-900">{mediaFile.name}</p>
                                    <p className="text-xs text-purple-700">{(mediaFile.size / 1024 / 1024).toFixed(2)} MB</p>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <Input name="media-version" label="Version" type="text" value={mediaVersion} onChange={(e) => setMediaVersion(e.target.value)} placeholder="1.0" disabled={loading} required />
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
                            <select
                                value={language}
                                onChange={(e) => setLanguage(e.target.value)}
                                className="block w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                                disabled={loading}
                            >
                                <option value="en">English</option>
                                <option value="auto">Auto-detect</option>
                                <option value="es">Spanish</option>
                                <option value="fr">French</option>
                                <option value="de">German</option>
                                <option value="ar">Arabic</option>
                                <option value="ur">Urdu</option>
                                <option value="hi">Hindi</option>
                                <option value="zh">Chinese</option>
                            </select>
                        </div>
                    </div>

                    <Button type="submit" loading={loading} disabled={!mediaFile || loading}>
                        {loading ? (<><Loader2 className="animate-spin mr-2" size={18} />Transcribing... (may take a minute)</>) : (<><Video className="mr-2" size={18} />Upload & Transcribe</>)}
                    </Button>

                    {/* Media Tips */}
                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                        <div className="flex items-start">
                            <AlertCircle className="text-purple-600 mr-3 flex-shrink-0" size={20} />
                            <div className="text-sm text-purple-800">
                                <p className="font-semibold mb-1">How it works:</p>
                                <ul className="list-disc list-inside space-y-1">
                                    <li>Audio is transcribed using AI speech-to-text (Whisper)</li>
                                    <li>The transcript is then indexed into your knowledge base</li>
                                    <li>Great for product demos, training recordings, and sales calls</li>
                                    <li>Transcription takes ~1 minute per 5 minutes of audio</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </form>
            )}

            {/* Status & Results (shared across all tabs) */}
            <StatusMessage message={message} />
            {result && <ResultCard result={result} type={activeTab} />}
        </div>
        <RelatedLinks links={[
            { label: 'Manage Content',  to: '/content/manage' },
            { label: 'Knowledge Chat',  to: '/knowledge-chat' },
        ]} />
        </div>
    );
}