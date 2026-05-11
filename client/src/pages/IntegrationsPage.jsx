import React, { useState, useEffect } from 'react';
import {
    Plug, Store, Globe, RefreshCw, Trash2, CheckCircle, AlertCircle,
    Loader2, Plus, X, Key, Link as LinkIcon, Activity
} from 'lucide-react';
import { integrations as integrationsApi } from '../utils/api';

const IntegrationsPage = ({ token }) => {
    const [platforms, setPlatforms] = useState([]);
    const [connected, setConnected] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [connectModalOpen, setConnectModalOpen] = useState(false);
    const [selectedPlatform, setSelectedPlatform] = useState(null);
    const [connectForm, setConnectForm] = useState({ store_name: '', api_key: '', api_secret: '', base_url: '' });
    const [connecting, setConnecting] = useState(false);
    const [connectError, setConnectError] = useState(null);
    const [syncingId, setSyncingId] = useState(null);

    const loadAll = async () => {
        setLoading(true);
        setError(null);
        try {
            const [p, c] = await Promise.all([
                integrationsApi.listPlatforms(token),
                integrationsApi.listConnected(token),
            ]);
            setPlatforms(p.platforms || []);
            setConnected(c.integrations || []);
        } catch (err) {
            setError(err.message || 'Failed to load integrations');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (token) loadAll();
    }, [token]);

    const openConnectModal = (platform) => {
        setSelectedPlatform(platform);
        setConnectForm({
            store_name: `${platform.display_name} Store`,
            api_key: '',
            api_secret: '',
            base_url: '',
        });
        setConnectError(null);
        setConnectModalOpen(true);
    };

    const closeModal = () => {
        setConnectModalOpen(false);
        setSelectedPlatform(null);
        setConnectError(null);
    };

    const handleConnect = async () => {
        if (!selectedPlatform) return;
        if (!connectForm.store_name.trim()) {
            setConnectError('Store name is required');
            return;
        }
        setConnecting(true);
        setConnectError(null);
        try {
            await integrationsApi.connect({
                platform: selectedPlatform.platform,
                store_name: connectForm.store_name.trim(),
                api_key: connectForm.api_key.trim() || null,
                api_secret: connectForm.api_secret.trim() || null,
                base_url: connectForm.base_url.trim() || null,
            }, token);
            closeModal();
            await loadAll();
        } catch (err) {
            setConnectError(err.message || 'Connection failed');
        } finally {
            setConnecting(false);
        }
    };

    const handleSync = async (integrationId) => {
        setSyncingId(integrationId);
        try {
            await integrationsApi.sync(integrationId, token);
            await loadAll();
        } catch (err) {
            alert(`Sync failed: ${err.message}`);
        } finally {
            setSyncingId(null);
        }
    };

    const handleDisconnect = async (integrationId, storeName) => {
        if (!confirm(`Disconnect "${storeName}"? (Synced data will be kept.)`)) return;
        try {
            await integrationsApi.disconnect(integrationId, token);
            await loadAll();
        } catch (err) {
            alert(`Disconnect failed: ${err.message}`);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center p-20 min-h-[60vh]">
                <Loader2 className="animate-spin text-blue-500 mb-4" size={40} />
                <h3 className="text-xl font-bold text-slate-700">Loading integrations...</h3>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <h2 className="text-3xl font-black bg-gradient-to-r from-blue-700 to-indigo-600 bg-clip-text text-transparent mb-1 flex items-center">
                    <Plug className="mr-3 text-blue-600" size={28} />
                    Store Integrations
                </h2>
                <p className="text-slate-500 font-medium ml-10">
                    Connect external ecommerce platforms — analytics run on the synced data automatically.
                </p>
            </div>

            {error && (
                <div className="bg-red-50 text-red-700 p-4 rounded-xl border border-red-100 flex items-center">
                    <AlertCircle size={20} className="mr-3" />
                    <span>{error}</span>
                </div>
            )}

            {/* Supported platforms */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <h3 className="text-xl font-bold text-slate-800 mb-4 flex items-center">
                    <Globe className="mr-2 text-indigo-500" size={20} />
                    Available Platforms
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {platforms.map((p) => (
                        <div key={p.platform}
                             className="p-5 border border-slate-200 rounded-xl hover:border-blue-300 hover:shadow-md transition-all">
                            <div className="flex items-start justify-between mb-3">
                                <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
                                    <Store size={20} />
                                </div>
                                {!p.requires_api_key && (
                                    <span className="px-2.5 py-0.5 bg-emerald-50 text-emerald-700 text-[11px] font-bold rounded-full border border-emerald-100">
                                        No key needed
                                    </span>
                                )}
                            </div>
                            <h4 className="font-bold text-slate-800 mb-1">{p.display_name}</h4>
                            <p className="text-xs text-slate-500 mb-4 line-clamp-3 min-h-[3rem]">{p.description}</p>
                            <button
                                onClick={() => openConnectModal(p)}
                                className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold text-sm transition">
                                <Plus size={16} />
                                <span>Connect</span>
                            </button>
                        </div>
                    ))}
                    {platforms.length === 0 && (
                        <p className="col-span-full text-center text-slate-400 py-8">No platforms available.</p>
                    )}
                </div>
            </div>

            {/* Connected stores */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <h3 className="text-xl font-bold text-slate-800 mb-4 flex items-center">
                    <LinkIcon className="mr-2 text-emerald-500" size={20} />
                    Connected Stores ({connected.length})
                </h3>
                {connected.length === 0 ? (
                    <div className="text-center py-10 text-slate-400">
                        <Store size={40} className="mx-auto mb-3 opacity-40" />
                        <p className="font-medium">No stores connected yet.</p>
                        <p className="text-sm mt-1">Pick a platform above to get started.</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {connected.map((i) => {
                            const summary = i.last_sync_summary || {};
                            const isSyncing = syncingId === i.id;
                            const statusColor =
                                i.last_sync_status === 'success' ? 'emerald' :
                                i.last_sync_status === 'failed'  ? 'rose' :
                                i.last_sync_status === 'in_progress' ? 'amber' : 'slate';

                            return (
                                <div key={i.id}
                                     className="p-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition">
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center space-x-3 mb-2">
                                                <h4 className="font-bold text-slate-800 truncate">{i.store_name}</h4>
                                                <span className={`px-2 py-0.5 bg-${statusColor}-50 text-${statusColor}-700 text-[11px] font-bold rounded-full border border-${statusColor}-100`}>
                                                    {i.last_sync_status || 'never'}
                                                </span>
                                                <span className="text-xs font-mono text-slate-400">{i.platform}</span>
                                            </div>

                                            {i.last_synced_at && (
                                                <p className="text-xs text-slate-500 mb-2">
                                                    Last synced: {new Date(i.last_synced_at).toLocaleString()}
                                                </p>
                                            )}

                                            {summary && Object.keys(summary).length > 0 && (
                                                <div className="flex flex-wrap gap-3 mt-2 text-xs">
                                                    {summary.products_fetched != null && (
                                                        <span className="px-2.5 py-1 bg-slate-100 rounded-md text-slate-700">
                                                            <b>{summary.products_fetched}</b> products
                                                        </span>
                                                    )}
                                                    {summary.customers_fetched != null && (
                                                        <span className="px-2.5 py-1 bg-slate-100 rounded-md text-slate-700">
                                                            <b>{summary.customers_fetched}</b> customers
                                                        </span>
                                                    )}
                                                    {summary.transactions_inserted != null && (
                                                        <span className="px-2.5 py-1 bg-slate-100 rounded-md text-slate-700">
                                                            <b>{summary.transactions_inserted}</b> transactions
                                                        </span>
                                                    )}
                                                </div>
                                            )}

                                            {i.last_sync_error && (
                                                <p className="text-xs text-rose-600 mt-2">
                                                    Error: {i.last_sync_error}
                                                </p>
                                            )}
                                        </div>

                                        <div className="flex flex-col space-y-2">
                                            <button
                                                onClick={() => handleSync(i.id)}
                                                disabled={isSyncing}
                                                className="flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-xs font-bold transition">
                                                <RefreshCw size={14} className={isSyncing ? 'animate-spin' : ''} />
                                                <span>{isSyncing ? 'Syncing...' : 'Sync Now'}</span>
                                            </button>
                                            <button
                                                onClick={() => handleDisconnect(i.id, i.store_name)}
                                                className="flex items-center space-x-1.5 px-3 py-1.5 bg-white hover:bg-rose-50 text-rose-600 border border-rose-200 rounded-lg text-xs font-bold transition">
                                                <Trash2 size={14} />
                                                <span>Disconnect</span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Connect Modal */}
            {connectModalOpen && selectedPlatform && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl">
                        <div className="flex justify-between items-start mb-4">
                            <div>
                                <h3 className="text-2xl font-black text-slate-800">
                                    Connect {selectedPlatform.display_name}
                                </h3>
                                <p className="text-sm text-slate-500 mt-1">{selectedPlatform.description}</p>
                            </div>
                            <button
                                onClick={closeModal}
                                className="p-2 hover:bg-slate-100 rounded-lg text-slate-500">
                                <X size={20} />
                            </button>
                        </div>

                        <div className="space-y-4 mt-6">
                            <div>
                                <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">
                                    Store Name
                                </label>
                                <input
                                    type="text"
                                    value={connectForm.store_name}
                                    onChange={(e) => setConnectForm({ ...connectForm, store_name: e.target.value })}
                                    placeholder="My Store"
                                    className="w-full mt-1 px-4 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>

                            {selectedPlatform.requires_api_key && (
                                <>
                                    <div>
                                        <label className="text-xs font-bold text-slate-600 uppercase tracking-wide flex items-center">
                                            <Key size={12} className="mr-1" /> API Key
                                        </label>
                                        <input
                                            type="password"
                                            value={connectForm.api_key}
                                            onChange={(e) => setConnectForm({ ...connectForm, api_key: e.target.value })}
                                            placeholder="sk_..."
                                            className="w-full mt-1 px-4 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs font-bold text-slate-600 uppercase tracking-wide">
                                            API Secret (optional)
                                        </label>
                                        <input
                                            type="password"
                                            value={connectForm.api_secret}
                                            onChange={(e) => setConnectForm({ ...connectForm, api_secret: e.target.value })}
                                            className="w-full mt-1 px-4 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                        />
                                    </div>
                                </>
                            )}

                            {!selectedPlatform.requires_api_key && (
                                <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-100 flex items-start space-x-3">
                                    <CheckCircle className="text-emerald-600 flex-shrink-0 mt-0.5" size={18} />
                                    <div>
                                        <p className="text-sm font-bold text-emerald-800">No API key needed</p>
                                        <p className="text-xs text-emerald-700 mt-0.5">
                                            This is a public demo API. You can connect directly.
                                        </p>
                                    </div>
                                </div>
                            )}

                            {connectError && (
                                <div className="bg-rose-50 p-3 rounded-lg border border-rose-100 text-sm text-rose-700 flex items-center">
                                    <AlertCircle size={16} className="mr-2 flex-shrink-0" />
                                    <span>{connectError}</span>
                                </div>
                            )}
                        </div>

                        <div className="flex space-x-3 mt-6">
                            <button
                                onClick={closeModal}
                                className="flex-1 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold transition">
                                Cancel
                            </button>
                            <button
                                onClick={handleConnect}
                                disabled={connecting}
                                className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl font-bold transition flex items-center justify-center">
                                {connecting ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin mr-2" />
                                        Testing...
                                    </>
                                ) : (
                                    <>
                                        <LinkIcon size={16} className="mr-2" />
                                        Connect
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default IntegrationsPage;
