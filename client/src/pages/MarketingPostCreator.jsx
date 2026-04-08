import React, { useState, useEffect, useCallback } from 'react';
import {
    ImageIcon, Sparkles, Send, Calendar, FileText,
    Trash2, Loader2, CheckCircle, Clock, AlertCircle,
    RefreshCw, Eye, ChevronDown, ChevronUp
} from 'lucide-react';
import { apiFetch } from '../utils/api';

const API_BASE = 'http://localhost:8000';

// ─── Module-level poll state ────────────────────────────────────────────
// These live outside React so they survive any component unmount/remount,
// including switching the sidebar page or the inner Create/All-Posts tab.
let _mktPollInterval = null;
let _mktElapsed = 0;

function _startPolling(jobId, token, onDone, onFail, onTick) {
    if (_mktPollInterval) return; // already running
    _mktElapsed = 0;
    _mktPollInterval = setInterval(async () => {
        _mktElapsed += 5;
        try {
            const job = await apiFetch(`/marketing/jobs/${jobId}`, 'GET', null, token);
            if (job.status === 'done') {
                clearInterval(_mktPollInterval);
                _mktPollInterval = null;
                onDone({ base64: job.image_base64, filename: job.image_filename, seed: job.seed });
            } else if (job.status === 'failed') {
                clearInterval(_mktPollInterval);
                _mktPollInterval = null;
                onFail(job.error || 'Image generation failed.');
            } else {
                onTick(`Generating… ${_mktElapsed}s elapsed`);
            }
        } catch {
            onTick(`Generating… ${_mktElapsed}s elapsed (checking…)`);
        }
    }, 5000);
}

// ─── helpers ─────────────────────────────────────────────────────────────────

const PLATFORMS = [
    { id: 'instagram', label: 'Instagram', icon: '📸', color: 'from-pink-500 to-rose-500' },
    { id: 'facebook',  label: 'Facebook',  icon: '👥', color: 'from-blue-600 to-blue-700' },
    { id: 'linkedin',  label: 'LinkedIn',  icon: '💼', color: 'from-sky-600 to-sky-700' },
];

const STATUS_BADGE = {
    draft:     { label: 'Draft',     cls: 'bg-slate-100 text-slate-600 border-slate-200'              },
    scheduled: { label: 'Scheduled', cls: 'bg-amber-100 text-amber-700 border-amber-300'              },
    published: { label: 'Published', cls: 'bg-emerald-100 text-emerald-700 border-emerald-300'        },
    failed:    { label: 'Failed',    cls: 'bg-rose-100 text-rose-700 border-rose-300'                 },
};

const SIZE_PRESETS = [
    { label: '1:1 Square',    w: 1024, h: 1024, icon: '⬛' },
    { label: '4:5 Portrait',  w: 820,  h: 1024, icon: '🟦' },
    { label: '16:9 Landscape',w: 1280, h: 720,  icon: '🟥' },
];

function Alert({ type = 'error', message, onClose }) {
    if (!message) return null;
    const styles = {
        error:   'bg-rose-50 border-rose-300 text-rose-700',
        success: 'bg-emerald-50 border-emerald-300 text-emerald-700',
        info:    'bg-blue-50 border-blue-300 text-blue-700',
    };
    return (
        <div className={`flex items-start space-x-3 p-4 rounded-2xl border ${styles[type]} mb-4`}>
            <span className="text-lg">{type === 'error' ? '⚠️' : type === 'success' ? '✅' : 'ℹ️'}</span>
            <p className="text-sm font-medium flex-1">{message}</p>
            {onClose && <button onClick={onClose} className="text-lg leading-none opacity-60 hover:opacity-100">×</button>}
        </div>
    );
}

// ─── Tab: Create Post ─────────────────────────────────────────────────────────

function CreatePostTab({ token, genState, setGenState }) {
    // Gen state comes from parent (survives sidebar/inner-tab navigation)
    const { loading: genLoading, status: genStatus, image: generatedImg, jobId: activeJobId } = genState;
    const setGenLoading   = (v) => setGenState(s => ({ ...s, loading: v }));
    const setGenStatus    = (v) => setGenState(s => ({ ...s, status: v }));
    const setGeneratedImg = (v) => setGenState(s => ({ ...s, image: v }));
    const setActiveJobId  = (v) => setGenState(s => ({ ...s, jobId: v }));

    // Local image form state (just form inputs, fine to reset on unmount)
    const [imgPrompt,    setImgPrompt]    = useState('');
    const [sizePreset,   setSizePreset]   = useState(0);
    const [steps,        setSteps]        = useState(20);

    // Caption state
    const [productName,  setProductName]  = useState('');
    const [captionTone,  setCaptionTone]  = useState('professional');
    const [extraContext, setExtraContext] = useState('');
    const [caption,      setCaption]      = useState('');
    const [capLoading,   setCapLoading]   = useState(false);

    // Post state
    const [platforms,    setPlatforms]    = useState([]);
    const [postStatus,   setPostStatus]   = useState('draft');
    const [scheduledAt,  setScheduledAt]  = useState('');
    const [saveLoading,  setSaveLoading]  = useState(false);

    // Feedback
    const [error,   setError]   = useState('');
    const [success, setSuccess] = useState('');

    const selectedSize = SIZE_PRESETS[sizePreset];

    // On mount: if a job was running when the user navigated away, resume polling
    useEffect(() => {
        if (activeJobId && genLoading && !_mktPollInterval) {
            _startPolling(
                activeJobId, token,
                (img)  => { setGeneratedImg(img);  setGenLoading(false); setGenStatus(''); setActiveJobId(null); },
                (err)  => { setGenStatus('');       setGenLoading(false); setActiveJobId(null); },
                (tick) => setGenStatus(tick),
            );
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Image generation ────────────────────────────────────────────────────
    const handleGenerateImage = async () => {
        if (!imgPrompt.trim()) { setError('Enter an image prompt first.'); return; }
        if (_mktPollInterval)  { setError('An image is already generating. Please wait.'); return; }

        setGenLoading(true);
        setError('');
        setGeneratedImg(null);
        setGenStatus('Starting generation…');

        try {
            // Start job — returns immediately with a job_id
            const { job_id } = await apiFetch('/marketing/generate-image/start', 'POST', {
                prompt: imgPrompt,
                width:  selectedSize.w,
                height: selectedSize.h,
                steps,
                seed: 0,
            }, token);

            setActiveJobId(job_id);
            setGenStatus(`Generating… 0s elapsed`);

            // Start module-level polling — survives tab/sidebar switches
            _startPolling(
                job_id, token,
                (img)  => { setGeneratedImg(img);  setGenLoading(false); setGenStatus(''); setActiveJobId(null); },
                (err)  => { setError(err);          setGenLoading(false); setGenStatus(''); setActiveJobId(null); },
                (tick) => setGenStatus(tick),
            );

        } catch (e) {
            setError(e.message || 'Failed to start image generation.');
            setGenLoading(false);
            setGenStatus('');
        }
    };

    // ── Caption generation ───────────────────────────────────────────────────
    const handleGenerateCaption = async () => {
        if (platforms.length === 0) { setError('Select at least one platform before generating a caption.'); return; }
        if (!productName.trim())    { setError('Enter a product name for caption generation.'); return; }

        setCapLoading(true);
        setError('');

        try {
            const data = await apiFetch('/marketing/generate-caption', 'POST', {
                product_name:       productName,
                platform:           platforms[0],   // use first selected platform as primary tone
                tone:               captionTone,
                additional_context: extraContext,
            }, token);

            setCaption(data.caption);
        } catch (e) {
            setError(e.message || 'Caption generation failed. Is Ollama running?');
        } finally {
            setCapLoading(false);
        }
    };

    // ── Platform toggle ───────────────────────────────────────────────────────
    const togglePlatform = (id) =>
        setPlatforms(prev => prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]);

    // ── Save post ─────────────────────────────────────────────────────────────
    const handleSave = async () => {
        if (!caption.trim())        { setError('Write or generate a caption.'); return; }
        if (!imgPrompt.trim())      { setError('Enter an image prompt (even if image generation is skipped).'); return; }
        if (platforms.length === 0) { setError('Select at least one platform.'); return; }
        if (postStatus === 'scheduled' && !scheduledAt) { setError('Choose a schedule date/time.'); return; }
        if (postStatus === 'scheduled' && new Date(scheduledAt) <= new Date()) {
            setError('Scheduled time must be in the future.');
            return;
        }

        setSaveLoading(true);
        setError('');
        setSuccess('');

        try {
            await apiFetch('/marketing/posts', 'POST', {
                caption,
                image_prompt:   imgPrompt,
                platforms,
                status:         postStatus,
                image_filename: generatedImg?.filename || null,
                image_seed:     generatedImg?.seed     || null,
                scheduled_at:   postStatus === 'scheduled' ? new Date(scheduledAt).toISOString() : null,
            }, token);

            setSuccess(postStatus === 'scheduled'
                ? `🕐 Post scheduled for ${new Date(scheduledAt).toLocaleString()}!`
                : '✅ Post saved as draft!');

            // Reset form
            setImgPrompt('');
            setCaption('');
            setProductName('');
            setExtraContext('');
            setPlatforms([]);
            setGeneratedImg(null);
            setPostStatus('draft');
            setScheduledAt('');
        } catch (e) {
            setError(e.message || 'Failed to save post.');
        } finally {
            setSaveLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <Alert type="error"   message={error}   onClose={() => setError('')} />
            <Alert type="success" message={success} onClose={() => setSuccess('')} />

            {/* ── Image Generation ─────────────────────────────────────── */}
            <Section icon="🎨" title="1 · Generate Image">
                <textarea
                    rows={3}
                    value={imgPrompt}
                    onChange={e => setImgPrompt(e.target.value)}
                    placeholder="Describe the image you want to generate…  e.g. 'A sleek black leather wallet on a wooden desk, soft studio lighting, product photography'"
                    className="w-full p-3.5 border-2 border-slate-200 rounded-2xl resize-none focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white text-sm"
                />

                {/* Size presets */}
                <div className="flex gap-2 mt-3 flex-wrap">
                    {SIZE_PRESETS.map((p, i) => (
                        <button
                            key={i}
                            onClick={() => setSizePreset(i)}
                            className={`px-4 py-2 rounded-xl text-xs font-bold border-2 transition-all ${
                                sizePreset === i
                                    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white border-transparent shadow-lg shadow-cyan-500/30'
                                    : 'border-slate-200 text-slate-600 hover:border-cyan-300'
                            }`}
                        >
                            {p.icon} {p.label} ({p.w}×{p.h})
                        </button>
                    ))}
                </div>

                {/* Steps */}
                <div className="mt-4 flex items-center gap-4">
                    <label className="text-xs font-bold text-slate-500 w-28">
                        Quality steps: <span className="text-cyan-600">{steps}</span>
                    </label>
                    <input
                        type="range" min={10} max={40} step={5} value={steps}
                        onChange={e => setSteps(Number(e.target.value))}
                        className="flex-1 accent-cyan-500"
                    />
                    <span className="text-xs text-slate-400">({steps <= 15 ? 'fast' : steps <= 25 ? 'balanced' : 'high quality'})</span>
                </div>

                <button
                    onClick={handleGenerateImage}
                    disabled={genLoading || !imgPrompt.trim()}
                    className="mt-4 w-full flex justify-center items-center py-3.5 px-6 rounded-2xl font-bold text-white bg-gradient-to-r from-violet-500 via-purple-500 to-pink-500 hover:from-violet-600 hover:to-pink-600 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-purple-500/30 transition-all"
                >
                    {genLoading
                        ? <><Loader2 className="animate-spin mr-2" size={18} /> {genStatus || 'Starting…'}</>
                        : <><ImageIcon size={18} className="mr-2" /> Generate Image</>
                    }
                </button>

                {/* Image preview */}
                {generatedImg && (
                    <div className="mt-4 relative rounded-2xl overflow-hidden border-2 border-purple-200 shadow-xl">
                        <img
                            src={`data:image/png;base64,${generatedImg.base64}`}
                            alt="Generated"
                            className="w-full object-cover max-h-80"
                        />
                        <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs p-2 flex justify-between">
                            <span>✅ Image generated</span>
                            <span className="opacity-70">seed: {generatedImg.seed}</span>
                        </div>
                    </div>
                )}
            </Section>

            {/* ── Platform Selection ───────────────────────────────────── */}
            <Section icon="📡" title="2 · Select Platforms">
                <div className="flex gap-3 flex-wrap">
                    {PLATFORMS.map(p => (
                        <button
                            key={p.id}
                            onClick={() => togglePlatform(p.id)}
                            className={`flex items-center gap-2 px-5 py-3 rounded-2xl font-bold text-sm border-2 transition-all ${
                                platforms.includes(p.id)
                                    ? `bg-gradient-to-r ${p.color} text-white border-transparent shadow-lg`
                                    : 'border-slate-200 text-slate-600 hover:border-slate-300 bg-white'
                            }`}
                        >
                            <span>{p.icon}</span> {p.label}
                            {platforms.includes(p.id) && <CheckCircle size={15} />}
                        </button>
                    ))}
                </div>
                {platforms.length > 0 && (
                    <p className="text-xs text-slate-400 mt-2">
                        Caption will be tuned for <strong>{platforms[0]}</strong> style.
                    </p>
                )}
            </Section>

            {/* ── Caption ─────────────────────────────────────────────── */}
            <Section icon="✍️" title="3 · Write Caption">

                {/* AI caption helper */}
                <div className="bg-gradient-to-r from-cyan-50 to-blue-50 border-2 border-cyan-100 rounded-2xl p-4 mb-4">
                    <p className="text-xs font-bold text-cyan-700 mb-3 flex items-center gap-1">
                        <Sparkles size={13} /> AI Caption Generator
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-bold text-slate-500 mb-1">Product / Offer name</label>
                            <input
                                type="text"
                                value={productName}
                                onChange={e => setProductName(e.target.value)}
                                placeholder="e.g. Premium Leather Wallet"
                                className="w-full p-2.5 text-sm border-2 border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-slate-500 mb-1">Tone</label>
                            <select
                                value={captionTone}
                                onChange={e => setCaptionTone(e.target.value)}
                                className="w-full p-2.5 text-sm border-2 border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white"
                            >
                                {['professional', 'casual', 'exciting', 'luxury', 'friendly', 'urgent'].map(t => (
                                    <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <input
                        type="text"
                        value={extraContext}
                        onChange={e => setExtraContext(e.target.value)}
                        placeholder="Optional: key benefits, price, target audience, promotion…"
                        className="w-full mt-3 p-2.5 text-sm border-2 border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white"
                    />
                    <button
                        onClick={handleGenerateCaption}
                        disabled={capLoading || !productName.trim() || platforms.length === 0}
                        className="mt-3 flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm font-bold text-white bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-cyan-500/30 transition-all"
                    >
                        {capLoading
                            ? <><Loader2 className="animate-spin" size={14} /> Generating…</>
                            : <><Sparkles size={14} /> Generate Caption</>
                        }
                    </button>
                </div>

                {/* Caption textarea */}
                <textarea
                    rows={5}
                    value={caption}
                    onChange={e => setCaption(e.target.value)}
                    placeholder="Write your caption here, or use the AI generator above…"
                    className="w-full p-3.5 border-2 border-slate-200 rounded-2xl resize-none focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white text-sm"
                />
                <p className="text-xs text-right text-slate-400 mt-1">{caption.length} chars</p>
            </Section>

            {/* ── Schedule & Save ─────────────────────────────────────── */}
            <Section icon="📅" title="4 · Save or Schedule">
                <div className="flex gap-3 mb-4">
                    {['draft', 'scheduled'].map(s => (
                        <button
                            key={s}
                            onClick={() => setPostStatus(s)}
                            className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl font-bold text-sm border-2 transition-all ${
                                postStatus === s
                                    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white border-transparent shadow-lg'
                                    : 'border-slate-200 text-slate-600 hover:border-slate-300 bg-white'
                            }`}
                        >
                            {s === 'draft'
                                ? <><FileText size={15} /> Save as Draft</>
                                : <><Clock size={15} /> Schedule Post</>
                            }
                        </button>
                    ))}
                </div>

                {postStatus === 'scheduled' && (
                    <div className="mb-4">
                        <label className="block text-xs font-bold text-slate-500 mb-2">
                            📅 Publishing date &amp; time
                        </label>
                        <input
                            type="datetime-local"
                            value={scheduledAt}
                            min={new Date(Date.now() + 60000).toISOString().slice(0, 16)}
                            onChange={e => setScheduledAt(e.target.value)}
                            className="w-full p-3 border-2 border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white text-sm"
                        />
                        <p className="text-xs text-slate-400 mt-1">
                            The server checks every 60 seconds and publishes automatically when the time arrives.
                        </p>
                    </div>
                )}

                {/* Posting to social platforms — coming soon note */}
                <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700 flex items-start gap-2">
                    <span>🔌</span>
                    <span>
                        <strong>Coming soon:</strong> Actual posting to {platforms.join(', ') || 'platforms'} via their APIs.
                        For now, the server marks scheduled posts as <em>published</em> at the right time.
                    </span>
                </div>

                <button
                    onClick={handleSave}
                    disabled={saveLoading}
                    className="w-full flex justify-center items-center py-4 px-6 rounded-2xl font-bold text-white bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600 hover:from-cyan-600 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-xl shadow-cyan-500/30 transition-all text-base"
                >
                    {saveLoading
                        ? <><Loader2 className="animate-spin mr-2" size={18} /> Saving…</>
                        : postStatus === 'scheduled'
                            ? <><Calendar size={18} className="mr-2" /> Confirm Schedule</>
                            : <><Send size={18} className="mr-2" /> Save Draft</>
                    }
                </button>
            </Section>
        </div>
    );
}

// ─── Tab: All Posts ───────────────────────────────────────────────────────────

function AllPostsTab({ token }) {
    const [posts,    setPosts]    = useState([]);
    const [loading,  setLoading]  = useState(true);
    const [filter,   setFilter]   = useState('all');
    const [error,    setError]    = useState('');
    const [deleting, setDeleting] = useState(null);

    const loadPosts = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const params = filter === 'all' ? '' : `?status=${filter}`;
            const data = await apiFetch(`/marketing/posts${params}`, 'GET', null, token);
            setPosts(data.posts || []);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [filter, token]);

    useEffect(() => { loadPosts(); }, [loadPosts]);

    const handleDelete = async (postId) => {
        if (!window.confirm('Delete this post and its image?')) return;
        setDeleting(postId);
        try {
            await apiFetch(`/marketing/posts/${postId}`, 'DELETE', null, token);
            setPosts(prev => prev.filter(p => p.id !== postId));
        } catch (e) {
            setError(e.message);
        } finally {
            setDeleting(null);
        }
    };

    const FILTERS = ['all', 'draft', 'scheduled', 'published', 'failed'];

    return (
        <div>
            <Alert type="error" message={error} onClose={() => setError('')} />

            {/* Filter pills + refresh */}
            <div className="flex items-center gap-2 mb-5 flex-wrap">
                {FILTERS.map(f => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`px-4 py-2 rounded-xl text-xs font-bold border-2 transition-all capitalize ${
                            filter === f
                                ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white border-transparent shadow'
                                : 'border-slate-200 text-slate-500 hover:border-cyan-300 bg-white'
                        }`}
                    >
                        {f === 'all' ? 'All' : STATUS_BADGE[f]?.label ?? f}
                    </button>
                ))}
                <button
                    onClick={loadPosts}
                    disabled={loading}
                    className="ml-auto flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border-2 border-slate-200 text-slate-500 hover:border-cyan-300 bg-white"
                >
                    <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
                </button>
            </div>

            {loading ? (
                <div className="text-center py-16">
                    <Loader2 className="animate-spin mx-auto text-cyan-500" size={36} />
                    <p className="mt-3 text-slate-500 text-sm">Loading posts…</p>
                </div>
            ) : posts.length === 0 ? (
                <div className="text-center py-16 text-slate-400">
                    <ImageIcon size={40} className="mx-auto mb-3 opacity-40" />
                    <p className="font-semibold">No posts found</p>
                    <p className="text-sm mt-1">Create your first marketing post in the Create tab.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {posts.map(post => (
                        <PostCard
                            key={post.id}
                            post={post}
                            deleting={deleting === post.id}
                            onDelete={() => handleDelete(post.id)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── Post Card ────────────────────────────────────────────────────────────────

function PostCard({ post, deleting, onDelete }) {
    const [expanded, setExpanded] = useState(false);
    const badge = STATUS_BADGE[post.status] ?? STATUS_BADGE.draft;

    return (
        <div className="bg-white border-2 border-slate-100 rounded-2xl shadow-md overflow-hidden hover:shadow-lg transition-shadow">
            {/* Image */}
            {post.image_filename ? (
                <img
                    src={`${API_BASE}/marketing/images/${post.image_filename}`}
                    alt="Post visual"
                    className="w-full h-44 object-cover"
                    onError={e => { e.target.style.display = 'none'; }}
                />
            ) : (
                <div className="w-full h-44 bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center">
                    <ImageIcon size={32} className="text-slate-300" />
                </div>
            )}

            <div className="p-4">
                {/* Status + platforms */}
                <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${badge.cls}`}>
                        {badge.label}
                    </span>
                    <div className="flex gap-1.5">
                        {(post.platforms || []).map(p => {
                            const pl = PLATFORMS.find(x => x.id === p);
                            return pl ? (
                                <span key={p} className="text-sm" title={pl.label}>{pl.icon}</span>
                            ) : null;
                        })}
                    </div>
                </div>

                {/* Caption preview */}
                <p className={`text-sm text-slate-700 mb-3 leading-relaxed ${expanded ? '' : 'line-clamp-3'}`}>
                    {post.caption}
                </p>
                {post.caption.length > 120 && (
                    <button
                        onClick={() => setExpanded(e => !e)}
                        className="text-xs text-cyan-600 hover:text-cyan-700 font-semibold flex items-center gap-1 mb-2"
                    >
                        {expanded ? <><ChevronUp size={12} /> Show less</> : <><ChevronDown size={12} /> Show more</>}
                    </button>
                )}

                {/* Scheduling info */}
                {post.scheduled_at && (
                    <div className="text-xs text-amber-600 flex items-center gap-1 mb-2">
                        <Clock size={11} />
                        Scheduled: {new Date(post.scheduled_at).toLocaleString()}
                    </div>
                )}
                {post.published_at && (
                    <div className="text-xs text-emerald-600 flex items-center gap-1 mb-2">
                        <CheckCircle size={11} />
                        Published: {new Date(post.published_at).toLocaleString()}
                    </div>
                )}
                {post.publish_error && (
                    <div className="text-xs text-rose-600 flex items-center gap-1 mb-2 bg-rose-50 rounded-lg p-2">
                        <AlertCircle size={11} />
                        {post.publish_error}
                    </div>
                )}

                {/* Footer */}
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
                    <span className="text-xs text-slate-400">
                        {new Date(post.created_at).toLocaleDateString()}
                    </span>
                    <button
                        onClick={onDelete}
                        disabled={deleting}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold text-rose-600 border border-rose-200 hover:bg-rose-50 disabled:opacity-50 transition-colors"
                    >
                        {deleting
                            ? <Loader2 size={11} className="animate-spin" />
                            : <Trash2 size={11} />
                        }
                        Delete
                    </button>
                </div>
            </div>
        </div>
    );
}

// ─── Section wrapper ────────────────────────────────────────────────────────

function Section({ icon, title, children }) {
    return (
        <div className="bg-white border-2 border-slate-100 rounded-2xl p-5 shadow-sm">
            <h3 className="text-sm font-black text-slate-700 mb-4 flex items-center gap-2">
                <span>{icon}</span>
                <span className="bg-gradient-to-r from-cyan-600 to-blue-700 bg-clip-text text-transparent">{title}</span>
            </h3>
            {children}
        </div>
    );
}

// ─── Main export ──────────────────────────────────────────────────────────────

export default function MarketingPostCreator({ token, genState, setGenState }) {
    const [tab, setTab] = useState('create');

    const TABS = [
        { id: 'create', label: '✨ Create Post' },
        { id: 'posts',  label: '📋 All Posts'  },
    ];

    return (
        <div>
            {/* Header */}
            <div className="mb-6 bg-gradient-to-r from-violet-50 via-pink-50 to-rose-50 p-6 rounded-3xl border-2 border-violet-100">
                <h2 className="text-3xl font-black bg-gradient-to-r from-violet-600 via-pink-600 to-rose-600 bg-clip-text text-transparent flex items-center gap-3">
                    <span className="p-3 bg-gradient-to-br from-violet-500 to-pink-500 rounded-2xl shadow-lg shadow-violet-500/30 text-white">
                        <ImageIcon size={26} />
                    </span>
                    AI Marketing Posts
                </h2>
                <p className="text-slate-600 mt-2 ml-16 text-sm">
                    Generate images with FLUX · Write captions with AI · Schedule to Facebook, Instagram &amp; LinkedIn
                </p>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-6 bg-slate-100 p-1.5 rounded-2xl w-fit">
                {TABS.map(t => (
                    <button
                        key={t.id}
                        onClick={() => setTab(t.id)}
                        className={`px-5 py-2.5 rounded-xl text-sm font-bold transition-all ${
                            tab === t.id
                                ? 'bg-white text-slate-800 shadow-md'
                                : 'text-slate-500 hover:text-slate-700'
                        }`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {tab === 'create' ? <CreatePostTab token={token} genState={genState} setGenState={setGenState} /> : <AllPostsTab token={token} />}
        </div>
    );
}
