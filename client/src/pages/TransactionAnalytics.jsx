import React, { useState, useEffect } from 'react';
import { 
    TrendingUp, Activity, DollarSign, ShoppingCart, 
    AlertTriangle, Package, Calendar, RefreshCw
} from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, AreaChart, Area
} from 'recharts';
import { storeAnalytics } from '../utils/api';

const TransactionAnalytics = ({ token }) => {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await storeAnalytics.getDashboard(token);
            setData(result);
        } catch (err) {
            setError(err.message || "Failed to load analytics data");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (token) {
            fetchData();
        }
    }, [token]);

    const formatCurrency = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

    const StatCard = ({ title, value, growth, icon: Icon, prefix = "" }) => {
        const isPositive = growth >= 0;
        return (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 flex flex-col justify-between">
                <div className="flex justify-between items-start mb-4">
                    <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
                        <Icon size={24} />
                    </div>
                    <div className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                        isPositive ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'
                    }`}>
                        {isPositive ? '+' : ''}{growth}%
                    </div>
                </div>
                <div>
                    <h4 className="text-slate-500 text-sm font-semibold mb-1">{title}</h4>
                    <p className="text-3xl font-black text-slate-800 tracking-tight">
                        {prefix}{typeof value === 'number' && prefix === '' ? value.toLocaleString() : value}
                    </p>
                </div>
            </div>
        );
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center p-20 min-h-[60vh]">
                <Activity className="animate-spin text-blue-500 mb-4" size={40} />
                <h3 className="text-xl font-bold text-slate-700">Analyzing Transactions...</h3>
                <p className="text-slate-500 mt-2">Crunching numbers and detecting anomalies</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-50 text-red-600 p-8 rounded-2xl border border-red-100 flex flex-col items-center">
                <AlertTriangle size={48} className="mb-4 text-red-400" />
                <h3 className="text-2xl font-bold mb-2">Analytics Error</h3>
                <p>{error}</p>
                <button 
                    onClick={fetchData}
                    className="mt-6 px-6 py-2 bg-red-600 text-white rounded-full font-bold hover:bg-red-700 transition"
                >
                    Try Again
                </button>
            </div>
        );
    }

    if (!data) return null;

    return (
        <div className="max-w-6xl mx-auto space-y-6">
            <div className="flex justify-between items-center mb-8 bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <div>
                    <h2 className="text-3xl font-black bg-gradient-to-r from-blue-700 to-indigo-600 bg-clip-text text-transparent mb-1 flex items-center">
                        <Activity className="mr-3 text-blue-600" size={28} />
                        Transaction Analytics
                    </h2>
                    <p className="text-slate-500 font-medium ml-10">Monitor store performance, trends, and anomalies</p>
                </div>
                <button 
                    onClick={fetchData}
                    className="flex items-center space-x-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold transition"
                >
                    <RefreshCw size={18} />
                    <span>Refresh</span>
                </button>
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard 
                    title="Total Revenue (30d)" 
                    value={formatCurrency(data.kpis.revenue.value)} 
                    growth={data.kpis.revenue.growth} 
                    icon={DollarSign} 
                />
                <StatCard 
                    title="Total Orders (30d)" 
                    value={data.kpis.orders.value} 
                    growth={data.kpis.orders.growth} 
                    icon={ShoppingCart} 
                />
                <StatCard 
                    title="Avg Order Value (30d)" 
                    value={formatCurrency(data.kpis.aov.value)} 
                    growth={data.kpis.aov.growth} 
                    icon={TrendingUp} 
                />
            </div>

            {/* Trends Chart */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-bold text-slate-800 flex items-center">
                        <Calendar className="mr-2 text-indigo-500" size={20} />
                        Revenue Trend (30 Days)
                    </h3>
                </div>
                <div className="h-80 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data.trends} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.3}/>
                                    <stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                            <XAxis 
                                dataKey="date" 
                                axisLine={false} 
                                tickLine={false} 
                                tick={{ fill: '#64748b', fontSize: 12 }} 
                                tickFormatter={(str) => {
                                    const date = new Date(str);
                                    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                                }}
                            />
                            <YAxis 
                                axisLine={false} 
                                tickLine={false} 
                                tick={{ fill: '#64748b', fontSize: 12 }}
                                tickFormatter={(val) => `$${val}`}
                            />
                            <RechartsTooltip 
                                formatter={(value) => [formatCurrency(value), "Revenue"]}
                                labelFormatter={(label) => new Date(label).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
                            />
                            <Area type="monotone" dataKey="revenue" stroke="#4f46e5" strokeWidth={3} fillOpacity={1} fill="url(#colorRevenue)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Top Products */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h3 className="text-xl font-bold text-slate-800 flex items-center mb-6">
                        <Package className="mr-2 text-emerald-500" size={20} />
                        Top Performing Products
                    </h3>
                    <div className="space-y-4">
                        {data.top_products.map((product, idx) => (
                            <div key={product.id} className="flex items-center justify-between p-4 rounded-xl hover:bg-slate-50 transition border border-transparent hover:border-slate-100">
                                <div className="flex items-center space-x-4">
                                    <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-500 font-black flex items-center justify-center text-sm border border-slate-200">
                                        {idx + 1}
                                    </div>
                                    <div>
                                        <p className="font-bold text-slate-800">{product.name}</p>
                                        <p className="text-xs text-slate-500 font-mono mt-0.5">{product.sku}</p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <p className="font-black text-emerald-600">{formatCurrency(product.revenue)}</p>
                                    <p className="text-xs text-slate-500 font-medium">{product.quantity} sold</p>
                                </div>
                            </div>
                        ))}
                        {data.top_products.length === 0 && (
                            <p className="text-center text-slate-500 py-8">No recent product sales.</p>
                        )}
                    </div>
                </div>

                {/* Anomalies */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h3 className="text-xl font-bold text-slate-800 flex items-center mb-6">
                        <AlertTriangle className="mr-2 text-rose-500" size={20} />
                        Sales Anomalies (60d)
                    </h3>
                    <div className="space-y-4">
                        {data.anomalies.map((anomaly, idx) => (
                            <div key={idx} className={`p-4 rounded-xl border ${
                                anomaly.type === 'spike' 
                                    ? 'bg-emerald-50/50 border-emerald-100' 
                                    : 'bg-rose-50/50 border-rose-100'
                            }`}>
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex flex-col">
                                        <span className="text-sm font-bold text-slate-700">
                                            {new Date(anomaly.date).toLocaleDateString('en-US', { weekday: 'short', month: 'long', day: 'numeric' })}
                                        </span>
                                        <span className={`text-xs font-bold mt-1 px-2 py-0.5 rounded-full w-max ${
                                            anomaly.type === 'spike' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                                        }`}>
                                            {anomaly.type === 'spike' ? 'Unexpected Spike' : 'Unexpected Drop'} (Z: {anomaly.z_score})
                                        </span>
                                    </div>
                                    <div className="text-right">
                                        <p className="font-black text-slate-800">{formatCurrency(anomaly.actual_revenue)}</p>
                                        <p className="text-xs text-slate-500">Expected approx. {formatCurrency(anomaly.expected_revenue)}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                        {data.anomalies.length === 0 && (
                            <div className="flex flex-col items-center justify-center py-10 text-slate-400">
                                <Activity size={32} className="mb-2 opacity-30" />
                                <p>No major anomalies detected recently.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TransactionAnalytics;
