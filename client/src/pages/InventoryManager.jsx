import React, { useState, useEffect } from 'react';
import { inventory as inventoryApi, customerAnalytics } from '../utils/api';
import {
    Package, AlertTriangle, TrendingUp, Calendar,
    RefreshCw, Loader2, DollarSign, Box, Store as StoreIcon,
    Zap, CheckCircle, XCircle
} from 'lucide-react';
import { Card, Button } from '../App';

const InventoryManagerView = ({ orgId, token }) => {
    const [products, setProducts] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [forecastingId, setForecastingId] = useState(null);
    const [error, setError] = useState('');

    // Store selector state
    const [stores, setStores] = useState([]);
    const [selectedStoreId, setSelectedStoreId] = useState(null);
    const [storesLoading, setStoresLoading] = useState(true);

    // Bulk refresh job state
    const [activeJobId, setActiveJobId] = useState(null);
    const [jobState, setJobState] = useState(null);
    const [startingJob, setStartingJob] = useState(false);

    const fetchData = async (storeId = selectedStoreId) => {
        setLoading(true);
        setError('');
        try {
            const prodRes = await inventoryApi.getProducts(token, storeId);
            setProducts(prodRes.products || []);

            const alertRes = await inventoryApi.getAlerts(token, storeId);
            setAlerts(alertRes.alerts || []);
        } catch (err) {
            setError(err.message || 'Failed to load inventory data');
        } finally {
            setLoading(false);
        }
    };

    // Fetch stores once on mount, default to biggest
    useEffect(() => {
        if (!token) return;
        (async () => {
            setStoresLoading(true);
            try {
                const res = await customerAnalytics.listStores(token);
                const list = res.stores || [];
                setStores(list);
                if (list.length > 0) {
                    const biggest = list.reduce((a, b) =>
                        (b.transaction_count > a.transaction_count ? b : a)
                    );
                    setSelectedStoreId(biggest.id);
                }
            } catch (err) {
                console.error('Failed to load stores:', err);
            } finally {
                setStoresLoading(false);
            }
        })();
    }, [token]);

    // Re-fetch when store selection changes
    useEffect(() => {
        if (token && !storesLoading) {
            fetchData(selectedStoreId);
        }
    }, [token, selectedStoreId, storesLoading]);

    const selectedStore = stores.find((s) => s.id === selectedStoreId);

    const handleForecast = async (productId) => {
        setForecastingId(productId);
        try {
            await inventoryApi.triggerForecast(productId, token);
            await fetchData(selectedStoreId);
        } catch (err) {
            setError(err.message || 'Forecast failed to execute');
        } finally {
            setForecastingId(null);
        }
    };

    const handleStartBulkRefresh = async () => {
        if (!selectedStore) return;
        const count = selectedStore.product_count || 0;
        const etaMin = Math.round(count * 3 / 60);
        const msg = `This will forecast ${count.toLocaleString()} products for "${selectedStore.name}".\n\n` +
                    `Estimated time: ~${etaMin} minute${etaMin === 1 ? '' : 's'} (${count} × ~3s each).\n\n` +
                    `The job runs in the background — you can keep using the UI. Continue?`;
        if (!window.confirm(msg)) return;

        setStartingJob(true);
        setError('');
        try {
            const job = await inventoryApi.startRefreshJob(token, selectedStoreId);
            setActiveJobId(job.id);
            setJobState(job);
        } catch (err) {
            setError(err.message || 'Failed to start bulk refresh');
        } finally {
            setStartingJob(false);
        }
    };

    // Poll job status every 2s while active
    useEffect(() => {
        if (!activeJobId) return;

        let cancelled = false;
        const poll = async () => {
            try {
                const state = await inventoryApi.getRefreshJob(token, activeJobId);
                if (cancelled) return;
                setJobState(state);

                if (state.status !== 'running' && state.status !== 'queued') {
                    // Done — clear and refresh product list
                    setActiveJobId(null);
                    await fetchData(selectedStoreId);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err.message || 'Lost connection to job');
                    setActiveJobId(null);
                }
            }
        };

        const interval = setInterval(poll, 2000);
        // Also poll immediately so the user sees running-state fast
        poll();

        return () => {
            cancelled = true;
            clearInterval(interval);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeJobId]);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center p-12 h-64">
                <Loader2 className="animate-spin text-cyan-600 mb-4 h-12 w-12" />
                <p className="text-slate-600 font-bold">Loading Store Data...</p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div className="mb-8 bg-gradient-to-r from-cyan-50 via-blue-50 to-indigo-50 p-6 rounded-3xl border-2 border-cyan-100">
                <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-4">
                    <div>
                        <h3 className="text-3xl font-black text-slate-800 mb-2 flex items-center space-x-3">
                            <div className="p-3 bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-2xl shadow-lg shadow-cyan-500/30">
                                <Box size={26} />
                            </div>
                            <span className="bg-gradient-to-r from-cyan-600 to-blue-700 bg-clip-text text-transparent">
                                Inventory Forecasting
                            </span>
                        </h3>
                    </div>

                    <div className="flex items-center space-x-3 flex-wrap gap-2">
                        {stores.length > 0 && (
                            <div className="flex items-center space-x-2">
                                <StoreIcon size={18} className="text-cyan-700" />
                                <select
                                    value={selectedStoreId || ''}
                                    onChange={(e) => setSelectedStoreId(e.target.value ? parseInt(e.target.value) : null)}
                                    className="px-4 py-2 border-2 border-cyan-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white font-bold text-slate-700 text-sm shadow-sm"
                                >
                                    <option value="">All stores (aggregated)</option>
                                    {stores.map((s) => (
                                        <option key={s.id} value={s.id}>
                                            {s.name} ({s.product_count.toLocaleString()} products)
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}
                        <Button
                            onClick={() => fetchData(selectedStoreId)}
                            className="w-auto px-6"
                        >
                            <RefreshCw size={18} className="mr-2" />
                            Refresh
                        </Button>
                        <button
                            onClick={handleStartBulkRefresh}
                            disabled={!selectedStoreId || startingJob || activeJobId}
                            className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 disabled:from-slate-300 disabled:to-slate-400 text-white rounded-xl font-bold text-sm shadow-md transition"
                            title={!selectedStoreId ? "Pick a store first" : "Run Prophet forecast on every product in this store"}
                        >
                            <Zap size={16} />
                            <span>
                                {startingJob ? 'Starting...' :
                                 activeJobId ? 'Job running...' :
                                 `Forecast All (${selectedStore?.product_count?.toLocaleString() || 0})`}
                            </span>
                        </button>
                    </div>
                </div>

                {selectedStore && (
                    <div className="mt-4 flex flex-wrap gap-2 text-xs">
                        <span className="px-3 py-1 bg-white/70 text-cyan-700 rounded-full font-bold border border-cyan-100">
                            {selectedStore.product_count.toLocaleString()} products
                        </span>
                        <span className="px-3 py-1 bg-white/70 text-blue-700 rounded-full font-bold border border-blue-100">
                            {selectedStore.customer_count.toLocaleString()} customers
                        </span>
                        <span className="px-3 py-1 bg-white/70 text-indigo-700 rounded-full font-bold border border-indigo-100">
                            {selectedStore.transaction_count.toLocaleString()} transactions
                        </span>
                        {selectedStore.platform && (
                            <span className="px-3 py-1 bg-white/70 text-slate-600 rounded-full font-bold font-mono border border-slate-100">
                                {selectedStore.platform}
                            </span>
                        )}
                    </div>
                )}
            </div>

            {error && (
                <div className="bg-rose-50 border-2 border-rose-200 text-rose-700 p-4 rounded-xl mb-6 font-semibold flex items-center">
                    <AlertTriangle className="mr-3 text-rose-500" />
                    {error}
                </div>
            )}

            {/* BULK FORECAST JOB PROGRESS */}
            {jobState && (
                <div className={`bg-white border-2 p-5 rounded-3xl shadow-lg mb-6 ${
                    jobState.status === 'succeeded' ? 'border-emerald-200' :
                    jobState.status === 'failed' ? 'border-rose-200' :
                    'border-cyan-200'
                }`}>
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                            {jobState.status === 'running' || jobState.status === 'queued' ? (
                                <Loader2 className="animate-spin text-cyan-600" size={22} />
                            ) : jobState.status === 'succeeded' ? (
                                <CheckCircle className="text-emerald-600" size={22} />
                            ) : (
                                <XCircle className="text-rose-600" size={22} />
                            )}
                            <div>
                                <h4 className="font-black text-slate-800">
                                    {jobState.status === 'queued' && 'Queued — initialising...'}
                                    {jobState.status === 'running' && 'Forecasting in progress'}
                                    {jobState.status === 'succeeded' && 'Forecast job complete'}
                                    {jobState.status === 'failed' && 'Forecast job failed'}
                                </h4>
                                <p className="text-xs text-slate-500 font-mono">job {jobState.id.slice(0, 8)}...</p>
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="text-2xl font-black text-slate-800">
                                {jobState.processed.toLocaleString()} / {jobState.total.toLocaleString()}
                            </p>
                            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">
                                {jobState.progress_pct}% processed
                            </p>
                        </div>
                    </div>

                    {/* Progress bar */}
                    <div className="h-3 bg-slate-100 rounded-full overflow-hidden mb-3">
                        <div
                            className={`h-full transition-all duration-500 ${
                                jobState.status === 'failed'
                                    ? 'bg-gradient-to-r from-rose-500 to-red-600'
                                    : jobState.status === 'succeeded'
                                    ? 'bg-gradient-to-r from-emerald-500 to-teal-600'
                                    : 'bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600 animate-pulse'
                            }`}
                            style={{ width: `${Math.max(jobState.progress_pct, 2)}%` }}
                        />
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-xs">
                        <span className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full font-bold border border-emerald-100">
                            ✓ {jobState.succeeded} succeeded
                        </span>
                        {jobState.failed > 0 && (
                            <span className="px-3 py-1 bg-rose-50 text-rose-700 rounded-full font-bold border border-rose-100">
                                ✗ {jobState.failed} failed
                            </span>
                        )}
                        {jobState.last_product_name && jobState.status === 'running' && (
                            <span className="text-slate-500 truncate max-w-md">
                                Latest: <span className="font-mono text-slate-700">{jobState.last_product_name}</span>
                            </span>
                        )}
                        {jobState.finished_at && (
                            <span className="text-slate-500">
                                Finished {new Date(jobState.finished_at).toLocaleTimeString()}
                            </span>
                        )}
                    </div>

                    {jobState.errors && jobState.errors.length > 0 && (
                        <details className="mt-3 text-xs">
                            <summary className="cursor-pointer text-rose-600 font-bold">
                                Show errors ({jobState.errors.length})
                            </summary>
                            <ul className="mt-2 space-y-1 text-slate-600 max-h-32 overflow-y-auto">
                                {jobState.errors.map((e, i) => (
                                    <li key={i} className="font-mono">
                                        <span className="text-slate-400">{e.product_name || `product_id=${e.product_id}`}:</span>{' '}
                                        {e.error}
                                    </li>
                                ))}
                            </ul>
                        </details>
                    )}

                    {(jobState.status === 'succeeded' || jobState.status === 'failed') && (
                        <button
                            onClick={() => setJobState(null)}
                            className="mt-3 text-xs text-slate-500 hover:text-slate-700 font-bold"
                        >
                            Dismiss
                        </button>
                    )}
                </div>
            )}

            {/* ALERTS SECTION */}
            {alerts.length > 0 && (
                <div className="bg-gradient-to-br from-orange-50 to-red-50 p-6 rounded-3xl border-2 border-orange-200 shadow-xl mb-8">
                    <h4 className="text-xl font-black text-orange-800 mb-4 flex items-center">
                        <AlertTriangle className="mr-2" size={24} />
                        Active Stock Alerts ({alerts.length})
                    </h4>
                    <div className="space-y-3">
                        {alerts.map(alert => (
                            <div key={alert.id} className="bg-white/70 p-4 rounded-xl border border-orange-200 flex items-start">
                                <span className={`inline-flex items-center justify-center h-8 w-8 rounded-full mr-4 shrink-0 
                                    ${alert.alert_type === 'OUT_OF_STOCK' ? 'bg-red-100 text-red-600' : 
                                      alert.alert_type === 'LOW_STOCK' ? 'bg-orange-100 text-orange-600' : 'bg-yellow-100 text-yellow-600'}`}>
                                    !
                                </span>
                                <div>
                                    <p className="font-bold text-slate-800">{alert.message}</p>
                                    <p className="text-xs text-slate-500 mt-1">
                                        For: {alert.product_name} • Triggered: {new Date(alert.created_at).toLocaleString()}
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* PRODUCTS DIRECTORY */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {products.length === 0 ? (
                    <div className="col-span-full bg-slate-50 p-8 rounded-3xl border-2 border-dashed border-slate-200 text-center">
                        <Package size={48} className="text-slate-300 mx-auto mb-4" />
                        <h4 className="text-xl font-bold text-slate-700">No Products Found</h4>
                        <p className="text-slate-500 mt-2">Connect your store or seed data to see inventory.</p>
                    </div>
                ) : (
                    products.map(product => {
                        const isLowStock = product.current_stock <= product.reorder_point;
                        const isOutOfStock = product.current_stock === 0;
                        
                        return (
                            <div key={product.id} className="bg-white p-6 rounded-3xl border-2 border-slate-100 shadow-lg hover:shadow-xl transition-all duration-300 flex flex-col group">
                                <div className="flex justify-between items-start mb-4">
                                    <h4 className="text-lg font-black text-slate-800 leading-tight">
                                        {product.name}
                                    </h4>
                                    <span className={`px-2 py-1 text-xs font-black rounded-lg
                                        ${isOutOfStock ? 'bg-red-100 text-red-700' : 
                                          isLowStock ? 'bg-orange-100 text-orange-700' : 'bg-emerald-100 text-emerald-700'}`}>
                                        {isOutOfStock ? 'OOS' : 'Active'}
                                    </span>
                                </div>
                                
                                <p className="text-xs text-slate-400 font-mono mb-4">{product.sku}</p>
                                
                                <div className="grid grid-cols-2 gap-3 mb-6 flex-grow">
                                    <div className="bg-slate-50 p-3 rounded-2xl flex flex-col justify-center">
                                        <div className="flex items-center text-xs text-slate-500 mb-1">
                                            <Package size={14} className="mr-1" /> Stock
                                        </div>
                                        <span className={`text-xl font-black ${isOutOfStock ? 'text-red-600' : isLowStock ? 'text-orange-600' : 'text-slate-700'}`}>
                                            {product.current_stock}
                                        </span>
                                    </div>
                                    <div className="bg-slate-50 p-3 rounded-2xl flex flex-col justify-center">
                                        <div className="flex items-center text-xs text-slate-500 mb-1">
                                            <DollarSign size={14} className="mr-1" /> Price
                                        </div>
                                        <span className="text-xl font-black text-slate-700">
                                            ${product.price}
                                        </span>
                                    </div>
                                    
                                    <div className="col-span-2 bg-gradient-to-r from-blue-50 to-indigo-50 p-3 rounded-2xl">
                                        <div className="flex items-center text-xs text-blue-600 font-bold mb-1">
                                            <Calendar size={14} className="mr-1" /> 
                                            Forecasted Depletion
                                        </div>
                                        <span className="text-sm font-black text-indigo-900">
                                            {product.predicted_depletion_date 
                                                ? new Date(product.predicted_depletion_date).toLocaleDateString(undefined, {
                                                    weekday: 'short', year: 'numeric', month: 'short', day: 'numeric'
                                                  }) 
                                                : "No forecast calculated"}
                                        </span>
                                    </div>
                                </div>
                                
                                <Button 
                                    onClick={() => handleForecast(product.id)}
                                    loading={forecastingId === product.id}
                                    disabled={forecastingId !== null}
                                    className="mt-auto py-3 bg-gradient-to-r from-slate-800 to-slate-700 hover:from-slate-700 hover:to-slate-600"
                                >
                                    {forecastingId === product.id ? (
                                        "Calculating..."
                                    ) : (
                                        <>
                                            <TrendingUp size={16} className="mr-2" />
                                            Generate AI Forecast
                                        </>
                                    )}
                                </Button>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};

export default InventoryManagerView;
