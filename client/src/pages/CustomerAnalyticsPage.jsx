import React, { useState, useEffect, useMemo } from 'react';
import {
    Users, DollarSign, Target, Layers, Loader2, AlertTriangle,
    TrendingUp, Award, RefreshCw, Store as StoreIcon, UserCheck,
    Activity, Calendar, PieChart as PieIcon
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
    ResponsiveContainer, Cell, Legend,
} from 'recharts';
import { customerAnalytics } from '../utils/api';

// ══════════════════════════════════════════════════════════════════
//  Helpers
// ══════════════════════════════════════════════════════════════════

const fmt$ = (v) => new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0,
}).format(v || 0);

const fmt$2 = (v) => new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 2,
}).format(v || 0);

const SEGMENT_COLORS = {
    'Champions':         '#10b981',  // emerald
    'Loyal Customers':   '#3b82f6',  // blue
    'Potential Loyalists': '#6366f1', // indigo
    'New Customers':     '#06b6d4',  // cyan
    "Can't Lose Them":   '#f59e0b',  // amber
    'At Risk':           '#ef4444',  // rose
    'Hibernating':       '#a855f7',  // purple
    'Lost':              '#64748b',  // slate
};

// Color gradient for cohort retention cells (0–100%)
const cohortCellColor = (pct) => {
    if (pct == null || isNaN(pct)) return '#f1f5f9';
    if (pct >= 80) return '#059669';
    if (pct >= 60) return '#10b981';
    if (pct >= 40) return '#34d399';
    if (pct >= 20) return '#6ee7b7';
    if (pct >= 10) return '#a7f3d0';
    if (pct > 0)   return '#d1fae5';
    return '#f1f5f9';
};


// ══════════════════════════════════════════════════════════════════
//  RFM TAB
// ══════════════════════════════════════════════════════════════════

const RfmTab = ({ token, storeId }) => {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    const load = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await customerAnalytics.getRfm(token, storeId);
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { if (token) load(); }, [token, storeId]);

    const chartData = useMemo(() => {
        if (!data?.segments) return [];
        return Object.entries(data.segments)
            .map(([name, s]) => ({
                name,
                count: s.count,
                pct: s.pct,
                avg_monetary: s.avg_monetary,
                color: SEGMENT_COLORS[name] || '#94a3b8',
            }))
            .sort((a, b) => b.count - a.count);
    }, [data]);

    const topCustomers = useMemo(() => {
        if (!data?.customers) return [];
        return [...data.customers]
            .sort((a, b) => b.monetary - a.monetary)
            .slice(0, 10);
    }, [data]);

    if (loading) return <LoadingBlock label="Computing RFM scores..." />;
    if (error) return <ErrorBlock message={error} onRetry={load} />;
    if (!data || data.customer_count === 0) {
        return <EmptyBlock message="No customer data available for this store." />;
    }

    return (
        <div className="space-y-6">
            {/* Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard icon={Users} label="Customers" value={data.customer_count.toLocaleString()} color="blue" />
                <MetricCard icon={Layers} label="Segments" value={Object.keys(data.segments).length} color="indigo" />
                <MetricCard
                    icon={Award}
                    label="Champions"
                    value={data.segments?.Champions?.count || 0}
                    color="emerald"
                    hint={`${data.segments?.Champions?.pct || 0}% of base`}
                />
                <MetricCard
                    icon={AlertTriangle}
                    label="At Risk + Lost"
                    value={(data.segments?.['At Risk']?.count || 0) + (data.segments?.Lost?.count || 0)}
                    color="rose"
                />
            </div>

            {/* Segment distribution chart */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <h4 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
                    <PieIcon size={18} className="mr-2 text-indigo-500" />
                    Customer Segments
                </h4>
                <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 60 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                            <XAxis
                                dataKey="name"
                                angle={-25}
                                textAnchor="end"
                                interval={0}
                                tick={{ fill: '#64748b', fontSize: 11 }}
                            />
                            <YAxis tick={{ fill: '#64748b', fontSize: 12 }} />
                            <RechartsTooltip
                                contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
                                formatter={(value, name, props) => {
                                    if (name === 'count') {
                                        return [`${value} customers (${props.payload.pct}%)`, 'Count'];
                                    }
                                    return [value, name];
                                }}
                            />
                            <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                                {chartData.map((entry, idx) => (
                                    <Cell key={idx} fill={entry.color} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Segment breakdown + top customers */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Segment details */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h4 className="text-lg font-bold text-slate-800 mb-4">Segment Details</h4>
                    <div className="space-y-2">
                        {chartData.map((s) => (
                            <div key={s.name} className="p-3 rounded-lg border border-slate-100 hover:bg-slate-50 transition">
                                <div className="flex items-center justify-between mb-1">
                                    <div className="flex items-center space-x-2">
                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: s.color }} />
                                        <span className="font-bold text-slate-800 text-sm">{s.name}</span>
                                    </div>
                                    <span className="text-xs font-bold text-slate-500">
                                        {s.count} ({s.pct}%)
                                    </span>
                                </div>
                                <div className="text-xs text-slate-500 ml-5">
                                    Avg monetary: <b>{fmt$(s.avg_monetary)}</b>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Top customers */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h4 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
                        <Award size={18} className="mr-2 text-amber-500" />
                        Top Customers
                    </h4>
                    <div className="space-y-2">
                        {topCustomers.map((c, idx) => (
                            <div key={c.customer_id} className="p-3 rounded-lg border border-slate-100 hover:bg-slate-50 transition flex items-center justify-between">
                                <div className="flex items-center space-x-3 min-w-0">
                                    <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-600 font-black text-xs flex items-center justify-center flex-shrink-0">
                                        {idx + 1}
                                    </div>
                                    <div className="min-w-0">
                                        <p className="font-bold text-slate-800 text-sm">Customer {c.customer_id}</p>
                                        <p className="text-xs text-slate-500">
                                            F={c.frequency} · R={c.recency_days}d ·
                                            <span className="font-mono ml-1">Score {c.rfm_score}</span>
                                        </p>
                                    </div>
                                </div>
                                <div className="text-right flex-shrink-0 ml-2">
                                    <p className="font-black text-emerald-600 text-sm">{fmt$(c.monetary)}</p>
                                    <p
                                        className="text-[10px] font-bold uppercase tracking-wide"
                                        style={{ color: SEGMENT_COLORS[c.segment] || '#94a3b8' }}
                                    >
                                        {c.segment}
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};


// ══════════════════════════════════════════════════════════════════
//  CLV TAB
// ══════════════════════════════════════════════════════════════════

const ClvTab = ({ token, storeId }) => {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    const load = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await customerAnalytics.getClv(token, { storeId, forecastMonths: 12 });
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { if (token) load(); }, [token, storeId]);

    if (loading) return <LoadingBlock label="Fitting BG/NBD model..." />;
    if (error) return <ErrorBlock message={error} onRetry={load} />;

    if (data?.error) {
        return (
            <div className="bg-amber-50 p-6 rounded-2xl border border-amber-100 flex items-start space-x-3">
                <AlertTriangle size={24} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                    <h4 className="font-bold text-amber-900">CLV Unavailable</h4>
                    <p className="text-sm text-amber-800 mt-1">{data.error}</p>
                </div>
            </div>
        );
    }

    const summary = data?.summary || {};
    const topCustomers = data?.top_customers || [];
    const hasData = summary.total_predicted_clv != null;

    if (!hasData) {
        return (
            <div className="bg-amber-50 p-6 rounded-2xl border border-amber-100 flex items-start space-x-3">
                <AlertTriangle size={24} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                    <h4 className="font-bold text-amber-900">Insufficient Data for CLV</h4>
                    <p className="text-sm text-amber-800 mt-1">
                        {summary.note || 'Need at least 10 customers with repeat purchases to fit the BG/NBD model.'}
                    </p>
                    <p className="text-xs text-amber-700 mt-2">
                        This is expected for small-sample stores (like Fake Store API demo with ~5 returning customers).
                        Try switching to a larger store.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Summary metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                    icon={Users}
                    label="Customers"
                    value={(data.customer_count || 0).toLocaleString()}
                    color="blue"
                />
                <MetricCard
                    icon={DollarSign}
                    label="Total CLV (12mo)"
                    value={fmt$(summary.total_predicted_clv)}
                    color="emerald"
                />
                <MetricCard
                    icon={TrendingUp}
                    label="Avg CLV / customer"
                    value={fmt$(summary.avg_predicted_clv)}
                    color="indigo"
                />
                <MetricCard
                    icon={Target}
                    label="Top 20% CLV share"
                    value={`${summary.top_20pct_clv_share?.toFixed(1) || 0}%`}
                    color="amber"
                    hint="Pareto check"
                />
            </div>

            {/* Model info */}
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-4 rounded-xl border border-blue-100 text-sm text-slate-700">
                <span className="font-bold">Model:</span> {summary.model || 'BG/NBD + Gamma-Gamma'} ·
                <span className="font-bold ml-2">Forecast horizon:</span> {data.forecast_months} months
            </div>

            {/* Top customers by CLV */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <h4 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
                    <Award size={18} className="mr-2 text-amber-500" />
                    Top Customers by Predicted CLV
                </h4>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-xs font-bold text-slate-500 uppercase tracking-wide border-b border-slate-200">
                                <th className="pb-2 pr-3">#</th>
                                <th className="pb-2 pr-3">Customer</th>
                                <th className="pb-2 pr-3 text-right">Predicted CLV</th>
                                <th className="pb-2 pr-3 text-right">Pred. Txns</th>
                                <th className="pb-2 pr-3 text-right">AOV</th>
                                <th className="pb-2 pr-3 text-right">Alive</th>
                            </tr>
                        </thead>
                        <tbody>
                            {topCustomers.map((c, idx) => (
                                <tr key={c.customer_id} className="border-b border-slate-100 hover:bg-slate-50">
                                    <td className="py-3 pr-3 text-slate-400 font-bold">{idx + 1}</td>
                                    <td className="py-3 pr-3 font-bold text-slate-800">
                                        Customer {c.customer_id}
                                    </td>
                                    <td className="py-3 pr-3 text-right font-black text-emerald-600">
                                        {fmt$2(c.predicted_clv)}
                                    </td>
                                    <td className="py-3 pr-3 text-right text-slate-600">
                                        {c.predicted_txns?.toFixed(1)}
                                    </td>
                                    <td className="py-3 pr-3 text-right text-slate-600">
                                        {fmt$2(c.predicted_avg_order_value)}
                                    </td>
                                    <td className="py-3 pr-3 text-right">
                                        <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                                            c.alive_probability > 0.9 ? 'bg-emerald-50 text-emerald-700' :
                                            c.alive_probability > 0.7 ? 'bg-amber-50 text-amber-700' :
                                                                        'bg-rose-50 text-rose-700'
                                        }`}>
                                            {(c.alive_probability * 100).toFixed(0)}%
                                        </span>
                                    </td>
                                </tr>
                            ))}
                            {topCustomers.length === 0 && (
                                <tr><td colSpan="6" className="text-center text-slate-400 py-6">No customers to display.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Citation */}
            <div className="text-xs text-slate-400 italic text-center">
                Reference: Fader, Hardie & Lee (2005) "RFM and CLV: Using Iso-value Curves for Customer Base Analysis",
                <em> Journal of Marketing Research</em>
            </div>
        </div>
    );
};


// ══════════════════════════════════════════════════════════════════
//  COHORT TAB
// ══════════════════════════════════════════════════════════════════

const CohortTab = ({ token, storeId }) => {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    const load = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await customerAnalytics.getCohortRetention(token, { storeId, maxMonths: 12 });
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { if (token) load(); }, [token, storeId]);

    if (loading) return <LoadingBlock label="Computing cohort retention..." />;
    if (error) return <ErrorBlock message={error} onRetry={load} />;
    if (!data || data.cohort_count === 0) {
        return <EmptyBlock message="No cohort data available for this store." />;
    }

    const maxMonth = data.max_months || 12;

    return (
        <div className="space-y-6">
            {/* Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                    icon={Users}
                    label="Total Cohorts"
                    value={data.cohort_count}
                    color="blue"
                />
                <MetricCard
                    icon={Activity}
                    label="M1 Retention"
                    value={`${data.summary?.avg_retention_month_1?.toFixed(1) || 0}%`}
                    color="emerald"
                />
                <MetricCard
                    icon={Calendar}
                    label="M3 Retention"
                    value={`${data.summary?.avg_retention_month_3?.toFixed(1) || 0}%`}
                    color="indigo"
                />
                <MetricCard
                    icon={TrendingUp}
                    label="M6 Retention"
                    value={`${data.summary?.avg_retention_month_6?.toFixed(1) || 0}%`}
                    color="amber"
                />
            </div>

            {/* Retention heatmap */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 overflow-x-auto">
                <h4 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
                    <Layers size={18} className="mr-2 text-indigo-500" />
                    Monthly Cohort Retention Matrix
                </h4>
                <p className="text-xs text-slate-500 mb-4">
                    % of each cohort returning in subsequent months. Green = high retention, grey = low.
                </p>

                <table className="min-w-full text-xs">
                    <thead>
                        <tr className="text-slate-500 font-bold">
                            <th className="text-left p-2 border-b border-slate-200">Cohort</th>
                            <th className="text-right p-2 border-b border-slate-200">Size</th>
                            {[...Array(maxMonth + 1).keys()].map((m) => (
                                <th key={m} className="text-center p-2 border-b border-slate-200 min-w-[50px]">
                                    M{m}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {data.cohorts.map((cohort) => (
                            <tr key={cohort.cohort_month} className="hover:bg-slate-50">
                                <td className="p-2 font-bold text-slate-700 border-b border-slate-100">
                                    {cohort.cohort_month}
                                </td>
                                <td className="p-2 text-right text-slate-600 border-b border-slate-100 font-mono">
                                    {cohort.cohort_size.toLocaleString()}
                                </td>
                                {[...Array(maxMonth + 1).keys()].map((m) => {
                                    const cell = cohort.retention.find((r) => r.month_offset === m);
                                    const pct = cell?.pct;
                                    const isAvailable = pct != null && !isNaN(pct);
                                    return (
                                        <td
                                            key={m}
                                            className="p-2 text-center border-b border-slate-100 font-bold"
                                            style={{
                                                backgroundColor: isAvailable ? cohortCellColor(pct) : '#f8fafc',
                                                color: isAvailable && pct >= 40 ? 'white' : '#475569',
                                            }}
                                        >
                                            {isAvailable ? `${pct.toFixed(0)}%` : '—'}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};


// ══════════════════════════════════════════════════════════════════
//  Shared UI blocks
// ══════════════════════════════════════════════════════════════════

const MetricCard = ({ icon: Icon, label, value, color = 'blue', hint }) => {
    const bgClass = {
        blue: 'bg-blue-50 text-blue-600',
        indigo: 'bg-indigo-50 text-indigo-600',
        emerald: 'bg-emerald-50 text-emerald-600',
        amber: 'bg-amber-50 text-amber-600',
        rose: 'bg-rose-50 text-rose-600',
    }[color] || 'bg-slate-50 text-slate-600';

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-4">
            <div className={`inline-flex p-2 rounded-lg ${bgClass} mb-3`}>
                <Icon size={18} />
            </div>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wide">{label}</p>
            <p className="text-2xl font-black text-slate-800 mt-1">{value}</p>
            {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
        </div>
    );
};

const LoadingBlock = ({ label }) => (
    <div className="flex flex-col items-center justify-center p-16 bg-white rounded-2xl border border-slate-100">
        <Loader2 className="animate-spin text-blue-500 mb-3" size={32} />
        <p className="text-slate-600 font-bold">{label}</p>
    </div>
);

const ErrorBlock = ({ message, onRetry }) => (
    <div className="bg-red-50 text-red-700 p-6 rounded-2xl border border-red-100 flex flex-col items-center">
        <AlertTriangle size={36} className="mb-3 text-red-400" />
        <p className="font-bold mb-3">{message}</p>
        {onRetry && (
            <button
                onClick={onRetry}
                className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-bold hover:bg-red-700">
                Retry
            </button>
        )}
    </div>
);

const EmptyBlock = ({ message }) => (
    <div className="bg-slate-50 p-10 rounded-2xl border border-slate-100 text-center">
        <Users size={36} className="mx-auto mb-3 text-slate-300" />
        <p className="text-slate-500 font-medium">{message}</p>
    </div>
);


// ══════════════════════════════════════════════════════════════════
//  MAIN PAGE
// ══════════════════════════════════════════════════════════════════

const CustomerAnalyticsPage = ({ token }) => {
    const [stores, setStores] = useState([]);
    const [selectedStoreId, setSelectedStoreId] = useState(null);
    const [tab, setTab] = useState('rfm');
    const [storesLoading, setStoresLoading] = useState(true);
    const [storesError, setStoresError] = useState(null);

    const loadStores = async () => {
        setStoresLoading(true);
        setStoresError(null);
        try {
            const result = await customerAnalytics.listStores(token);
            const list = result.stores || [];
            setStores(list);
            // Default to biggest store (most transactions)
            if (list.length > 0) {
                const biggest = list.reduce((a, b) =>
                    (b.transaction_count > a.transaction_count ? b : a)
                );
                setSelectedStoreId(biggest.id);
            }
        } catch (err) {
            setStoresError(err.message);
        } finally {
            setStoresLoading(false);
        }
    };

    useEffect(() => { if (token) loadStores(); }, [token]);

    const selectedStore = stores.find((s) => s.id === selectedStoreId);

    if (storesLoading) {
        return <LoadingBlock label="Loading stores..." />;
    }

    if (storesError) {
        return <ErrorBlock message={storesError} onRetry={loadStores} />;
    }

    if (stores.length === 0) {
        return (
            <div className="max-w-4xl mx-auto text-center bg-white p-12 rounded-2xl shadow-sm border border-slate-100">
                <StoreIcon size={48} className="mx-auto mb-4 text-slate-300" />
                <h3 className="text-xl font-bold text-slate-700 mb-2">No Stores Found</h3>
                <p className="text-slate-500 mb-6">
                    Connect a store from the Integrations page, or ingest a dataset via the seed scripts.
                </p>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto space-y-6">
            {/* Header + store selector */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h2 className="text-3xl font-black bg-gradient-to-r from-blue-700 to-indigo-600 bg-clip-text text-transparent mb-1 flex items-center">
                            <UserCheck className="mr-3 text-blue-600" size={28} />
                            Customer Analytics
                        </h2>
                        <p className="text-slate-500 font-medium ml-10">
                            RFM segmentation, BG/NBD CLV, and cohort retention
                        </p>
                    </div>

                    <div className="flex items-center space-x-3">
                        <label className="text-sm font-bold text-slate-600">Store:</label>
                        <select
                            value={selectedStoreId || ''}
                            onChange={(e) => setSelectedStoreId(parseInt(e.target.value))}
                            className="px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white font-medium text-slate-700"
                        >
                            {stores.map((s) => (
                                <option key={s.id} value={s.id}>
                                    {s.name} ({s.transaction_count.toLocaleString()} txns)
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {selectedStore && (
                    <div className="mt-4 flex flex-wrap gap-2 text-xs">
                        <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full font-bold">
                            {selectedStore.product_count.toLocaleString()} products
                        </span>
                        <span className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full font-bold">
                            {selectedStore.customer_count.toLocaleString()} customers
                        </span>
                        <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full font-bold">
                            {selectedStore.transaction_count.toLocaleString()} transactions
                        </span>
                        {selectedStore.platform && (
                            <span className="px-3 py-1 bg-slate-100 text-slate-600 rounded-full font-bold font-mono">
                                {selectedStore.platform}
                            </span>
                        )}
                    </div>
                )}
            </div>

            {/* Tabs */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-2 flex">
                {[
                    { id: 'rfm',    label: 'RFM Segmentation', icon: Layers },
                    { id: 'clv',    label: 'Lifetime Value',   icon: DollarSign },
                    { id: 'cohort', label: 'Cohort Retention', icon: Calendar },
                ].map((t) => (
                    <button
                        key={t.id}
                        onClick={() => setTab(t.id)}
                        className={`flex-1 flex items-center justify-center space-x-2 py-2.5 rounded-xl font-bold text-sm transition ${
                            tab === t.id
                                ? 'bg-blue-600 text-white shadow-md'
                                : 'text-slate-600 hover:bg-slate-50'
                        }`}
                    >
                        <t.icon size={16} />
                        <span>{t.label}</span>
                    </button>
                ))}
            </div>

            {/* Tab content */}
            {tab === 'rfm'    && <RfmTab    token={token} storeId={selectedStoreId} />}
            {tab === 'clv'    && <ClvTab    token={token} storeId={selectedStoreId} />}
            {tab === 'cohort' && <CohortTab token={token} storeId={selectedStoreId} />}
        </div>
    );
};

export default CustomerAnalyticsPage;
