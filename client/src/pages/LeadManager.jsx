import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Upload, Users, TrendingUp, UserCheck, AlertTriangle, ChevronDown, Eye, RefreshCw, Filter, Trash2 } from 'lucide-react';
import { leadsApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { PageHeader, RelatedLinks } from '../components/ui';

// Allocation badge colors
const ALLOCATION_STYLES = {
    AI_OUTREACH: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-300', label: 'AI Outreach' },
    MANUAL_REVIEW: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-300', label: 'Manual Review' },
    NURTURE_CAMPAIGN: { bg: 'bg-slate-100', text: 'text-slate-600', border: 'border-slate-300', label: 'Nurture' },
    PENDING: { bg: 'bg-slate-100', text: 'text-slate-600', border: 'border-slate-300', label: 'Pending' },
};

const STATUS_STYLES = {
    PENDING: { bg: 'bg-slate-100', text: 'text-slate-500', label: 'Pending' },
    DRAFTING_OUTREACH: { bg: 'bg-indigo-100', text: 'text-indigo-600', label: 'Drafting...' },
    AI_ACTIVE: { bg: 'bg-emerald-100', text: 'text-emerald-600', label: 'Active' },
    MANUAL_REVIEW: { bg: 'bg-amber-100', text: 'text-amber-600', label: 'Review' },
};

const StatusBadge = ({ status }) => {
    const style = STATUS_STYLES[status] || STATUS_STYLES.PENDING;
    return (
        <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider ${style.bg} ${style.text}`}>
            {style.label}
        </span>
    );
};


const AllocationBadge = ({ allocation }) => {
    const style = ALLOCATION_STYLES[allocation] || ALLOCATION_STYLES.PENDING;
    return (
        <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-bold border whitespace-nowrap ${style.bg} ${style.text} ${style.border}`}>
            {style.label}
        </span>
    );
};

// (Score bar removed as per user request)

// ===== Upload Section =====
const UploadSection = ({ token, onUploadComplete }) => {
    const [dragging, setDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [file, setFile] = useState(null);
    const [mappingData, setMappingData] = useState(null); // { headers, suggested_mapping, canonical_fields }
    const [userMapping, setUserMapping] = useState({}); // { csv_header: canonical_field }
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const handleFileSelect = async (selectedFile) => {
        if (!selectedFile.name.endsWith('.csv')) {
            setError('Only CSV files are supported');
            return;
        }
        setFile(selectedFile);
        setAnalyzing(true);
        setError(null);
        setResult(null);
        
        try {
            const res = await leadsApi.analyzeColumns(selectedFile, token);
            setMappingData(res);
            // Pre-fill user mapping state with backend suggestions
            setUserMapping(res.suggested_mapping || {});
        } catch (e) {
            setError(e.message || 'Failed to read CSV columns');
            setFile(null);
        } finally {
            setAnalyzing(false);
        }
    };

    const handleMappingChange = (csvHeader, canonicalField) => {
        setUserMapping(prev => {
            const newMap = { ...prev };
            if (canonicalField) {
                newMap[csvHeader] = canonicalField;
            } else {
                delete newMap[csvHeader];
            }
            return newMap;
        });
    };

    const handleUpload = async () => {
        setUploading(true);
        setError(null);
        
        try {
            const res = await leadsApi.upload(file, userMapping, token);
            setResult(res);
            setFile(null);
            setMappingData(null);
            setUserMapping({});
            if (onUploadComplete) onUploadComplete();
        } catch (e) {
            setError(e.message || 'Upload failed');
        } finally {
            setUploading(false);
        }
    };

    const cancelUpload = () => {
        setFile(null);
        setMappingData(null);
        setUserMapping({});
        setError(null);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files[0]) handleFileSelect(e.dataTransfer.files[0]);
    };

    // Nice display names for canonical fields
    const displayNames = {
        company_name: 'Company Name (*)',
        email: 'Email',
        phone: 'Phone',
        decision_maker_job_title: 'Job Title',
        industry: 'Industry',
        country: 'Country',
        city: 'City',
        employee_count: 'Employee Count',
        annual_revenue_range: 'Annual Revenue',
        website: 'Website'
    };

    return (
        <div className="mb-8">
            {/* Step 1: Drop zone (show if no file selected and no upload result) */}
            {!file && !result && (
                <div
                    onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-200 cursor-pointer
                        ${dragging ? 'border-blue-400 bg-blue-50' : 'border-slate-300 hover:border-blue-300 hover:bg-blue-50/50'}`}
                    onClick={() => document.getElementById('csv-file-input').click()}
                >
                    <Upload className={`mx-auto mb-3 ${dragging ? 'text-blue-500' : 'text-slate-400'}`} size={36} />
                    <p className="text-sm font-semibold text-slate-600">
                        {analyzing ? 'Analyzing columns...' : 'Drop a CSV file here or click to browse'}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                        Map your columns to our system automatically
                    </p>
                    <input
                        id="csv-file-input"
                        type="file"
                        accept=".csv"
                        className="hidden"
                        onChange={(e) => { if (e.target.files[0]) handleFileSelect(e.target.files[0]); e.target.value = null; }}
                    />
                </div>
            )}

            {/* Step 2: Column Mapping UI */}
            {mappingData && (
                <div className="bg-white border text-center border-blue-200 shadow-lg shadow-blue-100 p-6 rounded-2xl">
                    <div className="flex justify-between items-center mb-4">
                        <div>
                            <h4 className="font-bold text-slate-800">Map Columns for "{file.name}"</h4>
                            <p className="text-xs text-slate-500">We auto-detected some columns. Please confirm or adjust them.</p>
                        </div>
                        <div className="space-x-2">
                            <button onClick={cancelUpload} className="px-4 py-2 text-sm font-semibold text-slate-500 hover:bg-slate-100 rounded-xl transition-colors">
                                Cancel
                            </button>
                            <button 
                                onClick={handleUpload} 
                                disabled={uploading}
                                className="px-4 py-2 text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors shadow-md disabled:opacity-50"
                            >
                                {uploading ? 'Processing...' : 'Confirm & Score Leads'}
                            </button>
                        </div>
                    </div>
                    
                    <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 max-h-[400px] overflow-y-auto">
                        <div className="grid grid-cols-2 gap-4 mb-2 px-2">
                            <div className="text-xs font-bold text-slate-500 uppercase">Your CSV Column</div>
                            <div className="text-xs font-bold text-slate-500 uppercase">System Field</div>
                        </div>
                        {mappingData.headers.map((header) => {
                            const mappedValue = userMapping[header] || '';
                            const isMapped = !!mappedValue;
                            return (
                                <div key={header} className={`grid grid-cols-2 gap-4 items-center p-2 rounded-lg mb-1 ${isMapped ? 'bg-white border border-blue-100' : 'hover:bg-slate-100'}`}>
                                    <div className="font-medium text-sm text-slate-700 truncate" title={header}>
                                        {header}
                                    </div>
                                    <div>
                                        <select
                                            value={mappedValue}
                                            onChange={(e) => handleMappingChange(header, e.target.value)}
                                            className={`w-full text-sm rounded-lg border px-3 py-1.5 focus:ring-2 focus:outline-none transition-colors ${
                                                isMapped ? 'border-blue-300 bg-blue-50 text-blue-800 focus:ring-blue-200' : 'border-slate-300 bg-white text-slate-500 focus:ring-slate-200'
                                            }`}
                                        >
                                            <option value="">-- Do not import --</option>
                                            {mappingData.canonical_fields.map((field) => (
                                                <option key={field} value={field} disabled={Object.values(userMapping).includes(field) && userMapping[header] !== field}>
                                                    {displayNames[field] || field}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Step 3: Upload result */}
            {result && result.summary && (
                <div className="mt-4 p-5 bg-emerald-50 border border-emerald-200 rounded-2xl relative">
                    <button 
                        onClick={() => setResult(null)} 
                        className="absolute top-4 right-4 text-emerald-600 font-bold text-sm bg-emerald-100 px-3 py-1 rounded-lg hover:bg-emerald-200"
                    >
                        Upload Another
                    </button>
                    <h4 className="text-sm font-bold text-emerald-700 mb-3">Upload Complete</h4>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        <div className="bg-white rounded-xl p-3 text-center border border-emerald-100">
                            <p className="text-2xl font-black text-slate-800">{result.summary.new_leads ?? result.summary.total_leads}</p>
                            <p className="text-xs text-slate-500 font-medium">New Leads</p>
                        </div>
                        <div className="bg-white rounded-xl p-3 text-center border border-emerald-100">
                            <p className="text-2xl font-black text-emerald-600">{result.summary.ai_outreach}</p>
                            <p className="text-xs text-slate-500 font-medium">AI Outreach</p>
                        </div>
                        <div className="bg-white rounded-xl p-3 text-center border border-amber-100">
                            <p className="text-2xl font-black text-amber-600">{result.summary.manual_review}</p>
                            <p className="text-xs text-slate-500 font-medium">Manual Review</p>
                        </div>
                        <div className="bg-white rounded-xl p-3 text-center border border-rose-100">
                            <p className="text-2xl font-black text-rose-600">{result.summary.nurture_campaign}</p>
                            <p className="text-xs text-slate-500 font-medium">Nurture</p>
                        </div>
                        {result.summary.skipped_duplicates > 0 && (
                            <div className="bg-white rounded-xl p-3 text-center border border-slate-200">
                                <p className="text-2xl font-black text-slate-400">{result.summary.skipped_duplicates}</p>
                                <p className="text-xs text-slate-500 font-medium">Skipped (Dup)</p>
                            </div>
                        )}
                    </div>

                    {result.warnings && result.warnings.length > 0 && (
                        <div className="mt-2">
                            {result.warnings.map((w, i) => (
                                <p key={i} className="text-xs text-amber-600 flex items-center">
                                    <AlertTriangle size={12} className="mr-1" /> {w}
                                </p>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {error && (
                <div className="mt-4 p-4 bg-rose-50 border border-rose-200 rounded-2xl relative">
                    <button onClick={() => setError(null)} className="absolute top-2 right-4 text-xs font-bold text-rose-500">Dismiss</button>
                    <p className="text-sm text-rose-600 font-medium">{error}</p>
                </div>
            )}
        </div>
    );
};

// ===== Bulk Outreach Modal =====
const BulkOutreachModal = ({ onClose, onSubmit, isSubmitting }) => {
    const [goal, setGoal] = useState("Push for a 15 min discovery call highlighting how our solutions solve common industry pain points.");

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit(goal);
    };

    return createPortal(
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4" onClick={onClose}>
            <div
                className="bg-white rounded-3xl shadow-2xl p-6 max-w-lg w-full relative border border-slate-200"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="mb-5">
                    <h3 className="text-xl font-black text-slate-800 flex items-center">
                        <span className="mr-2">🚀</span> Trigger AI Outreach
                    </h3>
                    <p className="text-sm text-slate-500 mt-1">Generate and send contextual emails to all eligible AI Outreach leads in the background.</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Campaign Goal</label>
                        <textarea
                            value={goal}
                            onChange={(e) => setGoal(e.target.value)}
                            className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            rows={3}
                            placeholder="What should the AI try to achieve in this email?"
                            required
                        />
                    </div>

                    <div className="flex space-x-3 pt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold rounded-xl transition-colors text-sm"
                            disabled={isSubmitting}
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmitting || !goal.trim()}
                            className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-colors text-sm disabled:opacity-50 flex justify-center items-center"
                        >
                            {isSubmitting ? <RefreshCw size={16} className="animate-spin" /> : "Start Campaign"}
                        </button>
                    </div>
                </form>
            </div>
        </div>,
        document.body
    );
};

// ===== Lead Detail Modal =====
const LeadDetailModal = ({ lead, onClose, onUpdate, token }) => {
    const [updating, setUpdating] = useState(false);

    const handleAllocationChange = async (e) => {
        const newAllocation = e.target.value;
        if (!newAllocation || newAllocation === lead.allocation) return;
        
        setUpdating(true);
        try {
            await leadsApi.updateAllocation(lead.id, newAllocation, token);
            if (onUpdate) onUpdate();
            onClose();
        } catch (error) {
            console.error('Failed to update allocation:', error);
            alert('Failed to update allocation');
            setUpdating(false);
        }
    };

    if (!lead) return null;

    return createPortal(
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-start justify-center z-[100] p-4 overflow-y-auto" onClick={onClose}>
            <div
                className="bg-white rounded-3xl shadow-2xl p-6 max-w-lg w-full mt-10 mb-10 relative border border-slate-200"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-black text-slate-800">{lead.company_name}</h3>
                    <div className="flex items-center space-x-2">
                        {updating && <RefreshCw size={14} className="animate-spin text-slate-400" />}
                        <AllocationBadge allocation={lead.allocation} />
                        <select 
                            value=""
                            onChange={handleAllocationChange}
                            disabled={updating}
                            className="bg-transparent text-xs text-slate-400 hover:text-blue-500 font-medium cursor-pointer focus:outline-none"
                            title="Override Allocation"
                        >
                            <option value="" disabled>✎ Change</option>
                            <option value="AI_OUTREACH">AI Outreach</option>
                            <option value="MANUAL_REVIEW">Manual Review</option>
                            <option value="NURTURE_CAMPAIGN">Nurture</option>
                        </select>
                    </div>
                </div>

                <div className="space-y-3">
                    {[
                        ['Email', lead.email],
                        ['Phone', lead.phone],
                        ['Job Title', lead.job_title],
                        ['Industry', lead.industry],
                        ['Country', lead.country],
                        ['City', lead.city],
                        ['Employees', lead.employee_count],
                        ['Revenue', lead.revenue_range],
                        ['Status', lead.status],
                        ['Created', lead.created_at ? new Date(lead.created_at).toLocaleDateString() : '-'],
                    ].map(([label, value]) => (
                        <div key={label} className="flex justify-between py-1.5 border-b border-slate-50">
                            <span className="text-xs font-semibold text-slate-500 uppercase">{label}</span>
                            <span className="text-sm text-slate-700 font-medium">{value || '—'}</span>
                        </div>
                    ))}
                </div>

                <button
                    onClick={onClose}
                    className="mt-5 w-full py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold rounded-xl transition-colors text-sm"
                >
                    Close
                </button>
            </div>
        </div>,
        document.body
    );
};

// ===== Main Component =====
export default function LeadManager() {
    const { token } = useAuth();
    const [leads, setLeads] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');
    const [selectedLead, setSelectedLead] = useState(null);
    const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
    const [triggeringBulk, setTriggeringBulk] = useState(false);

    const fetchLeads = useCallback(async () => {
        setLoading(true);
        try {
            const res = await leadsApi.getLeads(token, { statusFilter: filter || undefined });
            setLeads(res.leads || []);
            setTotal(res.total || 0);
        } catch (e) {
            console.error('Failed to fetch leads:', e);
        } finally {
            setLoading(false);
        }
    }, [token, filter]);

    const handleClearLeads = async () => {
        if (!window.confirm('Are you sure you want to delete ALL leads? This cannot be undone.')) return;
        setLoading(true);
        try {
            await leadsApi.clearLeads(token);
            setLeads([]);
            setTotal(0);
        } catch (e) {
            console.error('Failed to clear leads:', e);
            alert('Failed to clear leads: ' + e.message);
        } finally {
            setLoading(false);
        }
    };

    const handleTriggerBulk = async (goal) => {
        setTriggeringBulk(true);
        try {
            const res = await leadsApi.triggerBulkOutreach(goal, token);
            alert(res.message);
            setIsBulkModalOpen(false);
            fetchLeads(); // refresh to show DRAFTING_OUTREACH status
        } catch (e) {
            console.error('Failed to trigger bulk outreach:', e);
            alert('Failed to start outreach: ' + e.message);
        } finally {
            setTriggeringBulk(false);
        }
    };

    useEffect(() => { fetchLeads(); }, [fetchLeads]);

    // Summary stats from current leads
    const stats = {
        total: total,
        aiOutreach: leads.filter(l => l.allocation === 'AI_OUTREACH').length,
        manual: leads.filter(l => l.allocation === 'MANUAL_REVIEW').length,
        nurture: leads.filter(l => l.allocation === 'NURTURE_CAMPAIGN').length,
    };

    return (
        <div>
            <PageHeader
                title="Lead Scoring"
                subtitle="Upload CRM leads, score with ML for win probability, and prioritize outreach"
                backTo="/dashboard"
                backLabel="Dashboard"
                action={
                    <div className="flex gap-2">
                        <button onClick={() => setIsBulkModalOpen(true)} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg transition flex items-center gap-1.5">
                            <span>🚀</span> AI Outreach
                        </button>
                        <button onClick={handleClearLeads} className="p-2 bg-red-50 hover:bg-red-100 rounded-lg transition" title="Clear all leads">
                            <Trash2 size={15} className="text-red-500" />
                        </button>
                        <button onClick={fetchLeads} className="p-2 bg-slate-100 hover:bg-slate-200 rounded-lg transition" title="Refresh">
                            <RefreshCw size={15} className="text-slate-500" />
                        </button>
                    </div>
                }
            />

            {/* Upload */}
            <UploadSection token={token} onUploadComplete={fetchLeads} />

            {/* Stats bar */}
            {stats.total > 0 && (
                <div className="grid grid-cols-4 gap-3 mb-6">
                    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-4 rounded-2xl border border-blue-100 text-center">
                        <Users className="mx-auto text-blue-500 mb-1" size={20} />
                        <p className="text-xl font-black text-slate-800">{stats.total}</p>
                        <p className="text-xs text-slate-500 font-medium">Total</p>
                    </div>
                    <div className="bg-gradient-to-br from-emerald-50 to-green-50 p-4 rounded-2xl border border-emerald-100 text-center">
                        <UserCheck className="mx-auto text-emerald-500 mb-1" size={20} />
                        <p className="text-xl font-black text-emerald-600">{stats.aiOutreach}</p>
                        <p className="text-xs text-slate-500 font-medium">AI Outreach</p>
                    </div>
                    <div className="bg-gradient-to-br from-amber-50 to-yellow-50 p-4 rounded-2xl border border-amber-100 text-center">
                        <TrendingUp className="mx-auto text-amber-500 mb-1" size={20} />
                        <p className="text-xl font-black text-amber-600">{stats.manual}</p>
                        <p className="text-xs text-slate-500 font-medium">Manual Review</p>
                    </div>
                    <div className="bg-gradient-to-br from-rose-50 to-red-50 p-4 rounded-2xl border border-rose-100 text-center">
                        <AlertTriangle className="mx-auto text-rose-500 mb-1" size={20} />
                        <p className="text-xl font-black text-rose-600">{stats.nurture}</p>
                        <p className="text-xs text-slate-500 font-medium">Nurture</p>
                    </div>
                </div>
            )}

            {/* Filter bar */}
            <div className="flex items-center space-x-2 mb-4">
                <Filter size={14} className="text-slate-400" />
                <select
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    className="text-sm border border-slate-200 rounded-xl px-3 py-2 bg-white text-slate-600 font-medium focus:outline-none focus:ring-2 focus:ring-blue-200"
                >
                    <option value="">All Leads</option>
                    <option value="AI_OUTREACH">AI Outreach</option>
                    <option value="MANUAL_REVIEW">Manual Review</option>
                    <option value="NURTURE_CAMPAIGN">Nurture</option>
                </select>
            </div>

            {/* Leads table */}
            {loading ? (
                <div className="text-center py-12">
                    <RefreshCw className="mx-auto animate-spin text-blue-400" size={24} />
                    <p className="text-sm text-slate-400 mt-2">Loading leads...</p>
                </div>
            ) : leads.length === 0 ? (
                <div className="text-center py-12 bg-slate-50 rounded-2xl">
                    <Users className="mx-auto text-slate-300 mb-2" size={36} />
                    <p className="text-sm text-slate-400 font-medium">No leads yet. Upload a CSV to get started.</p>
                </div>
            ) : (
                <div className="overflow-x-auto rounded-2xl border border-slate-200">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-slate-50 border-b border-slate-200">
                                <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 uppercase">Company</th>
                                <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 uppercase">Contact</th>
                                <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 uppercase">Industry</th>

                                <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 uppercase">Decision</th>
                                <th className="text-left px-4 py-3 text-xs font-bold text-slate-500 uppercase">Status</th>
                                <th className="text-center px-4 py-3 text-xs font-bold text-slate-500 uppercase">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leads.map((lead) => (
                                <tr key={lead.id} className="border-b border-slate-100 hover:bg-blue-50/40 transition-colors">
                                    <td className="px-4 py-3">
                                        <p className="font-bold text-slate-800">{lead.company_name}</p>
                                        <p className="text-xs text-slate-400">{lead.job_title || '—'}</p>
                                    </td>
                                    <td className="px-4 py-3">
                                        <p className="text-slate-600">{lead.email || '—'}</p>
                                    </td>
                                    <td className="px-4 py-3">
                                        <p className="text-slate-600">{lead.industry || '—'}</p>
                                        <p className="text-xs text-slate-400">{lead.country}</p>
                                    </td>

                                    <td className="px-4 py-3">
                                        <AllocationBadge allocation={lead.allocation} />
                                    </td>
                                    <td className="px-4 py-3">
                                        <StatusBadge status={lead.status} />
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        <button
                                            onClick={() => setSelectedLead(lead)}
                                            className="p-1.5 bg-slate-50 hover:bg-blue-50 text-slate-400 hover:text-blue-500 rounded-lg transition-colors inline-block"
                                            title="View Details"
                                        >
                                            <Eye size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Detail modal */}
            {selectedLead && (
                <LeadDetailModal 
                    lead={selectedLead} 
                    onClose={() => setSelectedLead(null)} 
                    onUpdate={fetchLeads}
                    token={token}
                />
            )}

            {/* Bulk Outreach modal */}
            {isBulkModalOpen && (
                <BulkOutreachModal
                    onClose={() => setIsBulkModalOpen(false)}
                    onSubmit={handleTriggerBulk}
                    isSubmitting={triggeringBulk}
                />
            )}
            <RelatedLinks links={[
                { label: 'AI Roleplay',           to: '/roleplay' },
                { label: 'Marketing Posts',        to: '/marketing' },
                { label: 'Transaction Analytics',  to: '/analytics' },
            ]} />
        </div>
    );
}
