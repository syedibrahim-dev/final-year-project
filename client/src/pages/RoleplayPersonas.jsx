import React, { useState, useEffect } from 'react';
import { Loader2, Users, TrendingUp, MessageCircle, DollarSign, Clock, Zap, ChevronRight } from 'lucide-react';
import { apiFetch } from '../utils/api';

export default function RoleplayPersonas({ token, navigate }) {
    const [personas, setPersonas] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        fetchPersonas();
    }, []);

    const fetchPersonas = async () => {
        try {
            setLoading(true);
            const data = await apiFetch('/roleplay/personas', 'GET', null, token);
            setPersonas(data.personas || []);
        } catch (err) {
            setError(err.message || 'Failed to load personas');
        } finally {
            setLoading(false);
        }
    };

    const startSession = async (personaId) => {
        try {
            const response = await apiFetch('/roleplay/sessions/start', 'POST',
                { persona_id: personaId },
                token
            );

            // Navigate to chat interface with session ID
            navigate('roleplay-chat', { sessionId: response.session_id });
        } catch (err) {
            alert(`Failed to start session: ${err.message}`);
        }
    };

    const getDifficultyColor = (difficulty) => {
        switch (difficulty) {
            case 'beginner': return 'from-emerald-500 to-green-600';
            case 'intermediate': return 'from-amber-500 to-orange-600';
            case 'advanced': return 'from-rose-500 to-red-600';
            default: return 'from-slate-500 to-gray-600';
        }
    };

    const getDifficultyIcon = (difficulty) => {
        switch (difficulty) {
            case 'beginner': return '🌱';
            case 'intermediate': return '⚡';
            case 'advanced': return '🔥';
            default: return '•';
        }
    };

    if (loading) {
        return (
            <div className="text-center p-16">
                <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-cyan-500 via-blue-500 to-indigo-600 rounded-3xl mb-6 shadow-2xl shadow-cyan-500/40 animate-pulse">
                    <Loader2 className="animate-spin h-10 w-10 text-white" />
                </div>
                <p className="mt-4 text-slate-700 text-xl font-bold">Loading personas...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center p-16">
                <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-rose-500 to-red-600 rounded-3xl mb-6 shadow-2xl shadow-rose-500/40">
                    <Users className="h-10 w-10 text-white" />
                </div>
                <p className="mt-4 text-rose-700 text-xl font-bold">{error}</p>
                <button
                    onClick={fetchPersonas}
                    className="mt-6 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-2xl font-bold hover:from-cyan-600 hover:to-blue-700 transition-all shadow-lg"
                >
                    Try Again
                </button>
            </div>
        );
    }

    return (
        <>
            <div className="mb-8 bg-gradient-to-r from-cyan-50 via-blue-50 to-indigo-50 p-6 rounded-3xl border-2 border-cyan-100">
                <div className="flex items-center space-x-3 mb-3">
                    <div className="p-3 bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-2xl shadow-lg shadow-cyan-500/30">
                        <Users size={28} />
                    </div>
                    <h3 className="text-4xl font-black bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-700 bg-clip-text text-transparent">
                        AI Roleplay Training
                    </h3>
                </div>
                <p className="text-slate-600 text-xl font-semibold ml-16">
                    Practice sales conversations with AI customer personas
                </p>
                <p className="text-slate-500 text-sm mt-2 ml-16">
                    Choose a customer type below to start your practice session
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {personas.map((persona) => (
                    <div
                        key={persona.id}
                        className="bg-gradient-to-br from-white to-slate-50 p-6 rounded-3xl border-2 border- slate-200 shadow-xl hover:shadow-2xl hover:border-cyan-300 transition-all duration-300 group cursor-pointer"
                        onClick={() => startSession(persona.id)}
                    >
                        {/* Header */}
                        <div className="flex items-start justify-between mb-4">
                            <div className="flex-1">
                                <h4 className="text-2xl font-black text-slate-800 mb-2 group-hover:text-cyan-600 transition-colors">
                                    {persona.name}
                                </h4>
                                <div className="flex items-center space-x-2">
                                    <span className={`px-3 py-1 rounded-xl text-xs font-black text-white bg-gradient-to-r ${getDifficultyColor(persona.difficulty)} shadow-md`}>
                                        {getDifficultyIcon(persona.difficulty)} {persona.difficulty.toUpperCase()}
                                    </span>
                                    <span className="px-3 py-1 rounded-xl text-xs font-bold text-slate-600 bg-slate-100">
                                        {persona.tone}
                                    </span>
                                </div>
                            </div>
                            <div className="p-2 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-2xl shadow-lg shadow-cyan-500/30 group-hover:scale-110 transition-transform">
                                <MessageCircle className="h-6 w-6 text-white" />
                            </div>
                        </div>

                        {/* Description */}
                        <p className="text-slate-600 text-sm mb-4 line-clamp-3">
                            {persona.description}
                        </p>

                        {/* Start Button */}
                        <button
                            className="w-full flex items-center justify-center space-x-2 py-3 px-4 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white rounded-2xl shadow-lg shadow-cyan-500/30 font-bold transition-all duration-200 transform group-hover:scale-[1.02] group-hover:shadow-xl active:scale-[0.98]"
                        >
                            <Zap size={18} />
                            <span>Start Practice Session</span>
                            <ChevronRight size={18} />
                        </button>
                    </div>
                ))}
            </div>

            {personas.length === 0 && !loading && (
                <div className="text-center p-16 bg-gradient-to-br from-slate-50 to-cyan-50 rounded-3xl border-2 border-slate-200">
                    <Users className="h-16 w-16 text-slate-400 mx-auto mb-4" />
                    <p className="text-slate-600 text-lg font-bold">No personas available</p>
                    <p className="text-slate-500 text-sm mt-2">Please contact your administrator</p>
                </div>
            )}
        </>
    );
}
