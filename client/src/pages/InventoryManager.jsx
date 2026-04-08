import React, { useState, useEffect } from 'react';
import { apiFetch } from '../utils/api';
import { 
    Package, AlertTriangle, TrendingUp, Calendar, 
    RefreshCw, Loader2, DollarSign, Box 
} from 'lucide-react';
import { Card, Button } from '../App';

const InventoryManagerView = ({ orgId, token }) => {
    const [products, setProducts] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [forecastingId, setForecastingId] = useState(null);
    const [error, setError] = useState('');

    const fetchData = async () => {
        setLoading(true);
        setError('');
        try {
            // Fetch Products mapping directly to /inventory/products
            const prodRes = await apiFetch(`/inventory/products`, 'GET', null, token);
            setProducts(prodRes.products || []);
            
            // Fetch Alerts mapping directly to /inventory/alerts
            const alertRes = await apiFetch(`/inventory/alerts`, 'GET', null, token);
            setAlerts(alertRes.alerts || []);
        } catch (err) {
            setError(err.message || 'Failed to load inventory data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [orgId, token]);

    const handleForecast = async (productId) => {
        setForecastingId(productId);
        try {
            await apiFetch(`/inventory/forecast/${productId}`, 'POST', null, token);
            await fetchData(); // Refresh data after forecasting
        } catch (err) {
            setError(err.message || 'Forecast failed to execute');
        } finally {
            setForecastingId(null);
        }
    };

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
            <div className="mb-8 bg-gradient-to-r from-cyan-50 via-blue-50 to-indigo-50 p-6 rounded-3xl border-2 border-cyan-100 flex justify-between items-center">
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
                <Button 
                    onClick={fetchData} 
                    className="w-auto px-6"
                >
                    <RefreshCw size={18} className="mr-2" />
                    Refresh
                </Button>
            </div>

            {error && (
                <div className="bg-rose-50 border-2 border-rose-200 text-rose-700 p-4 rounded-xl mb-6 font-semibold flex items-center">
                    <AlertTriangle className="mr-3 text-rose-500" />
                    {error}
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
