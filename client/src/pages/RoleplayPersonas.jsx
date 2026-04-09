import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Loader2, Users, MessageCircle, Target, Shield, Flame, Mic } from 'lucide-react';
import { apiFetch } from '../utils/api';

export default function RoleplayPersonas({ token, navigate }) {
    const [personas, setPersonas] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => { fetchPersonas(); }, []);

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

    const startSession = async (personaId, mode = 'text') => {
        try {
            const response = await apiFetch('/roleplay/sessions/start', 'POST',
                { persona_id: personaId }, token
            );
            navigate('roleplay-chat', { sessionId: response.session_id, mode });
        } catch (err) {
            alert(`Failed to start session: ${err.message}`);
        }
    };

    const diffConfig = {
        beginner:     { color: 'from-teal-500 to-teal-700', bg: 'bg-teal-50', text: 'text-teal-700', border: 'border-teal-200', shadow: 'hover:shadow-teal-500/[0.08]', hoverBorder: 'hover:border-teal-300/60', accent: 'text-teal-600', icon: <Target size={14} />, label: 'Beginner', emoji: '🟢' },
        intermediate: { color: 'from-amber-500 to-amber-700', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', shadow: 'hover:shadow-amber-500/[0.08]', hoverBorder: 'hover:border-amber-300/60', accent: 'text-amber-600', icon: <Shield size={14} />, label: 'Intermediate', emoji: '🟡' },
        advanced:     { color: 'from-red-500 to-red-700', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', shadow: 'hover:shadow-red-500/[0.08]', hoverBorder: 'hover:border-red-300/60', accent: 'text-red-600', icon: <Flame size={14} />, label: 'Advanced', emoji: '🔴' },
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <div className="w-14 h-14 bg-gradient-to-br from-blue-600 to-teal-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-500/20 animate-pulse">
                        <Loader2 className="animate-spin h-7 w-7 text-white" />
                    </div>
                    <p className="text-stone-600 font-medium">Loading personas...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <div className="w-14 h-14 bg-red-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Users className="h-7 w-7 text-red-500" />
                    </div>
                    <p className="text-red-600 font-semibold mb-3">{error}</p>
                    <button
                        onClick={fetchPersonas}
                        className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm"
                    >
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="animate-fadeInUp">
            {/* Header */}
            <div className="mb-8">
                <h3 className="text-3xl font-bold text-stone-800 mb-1">AI Roleplay Training</h3>
                <p className="text-stone-500">Choose a customer persona to start practicing</p>
            </div>

            {/* Persona Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {personas.map((persona, idx) => {
                    const diff = diffConfig[persona.difficulty] || diffConfig.intermediate;
                    return (
                        <motion.div
                            key={persona.id}
                            initial={{ opacity: 0, y: 24 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: idx * 0.08, type: 'spring', stiffness: 260, damping: 22 }}
                            whileHover={{ y: -6, transition: { duration: 0.25 } }}
                            className={`group bg-white rounded-2xl border border-stone-200/80 ${diff.hoverBorder} shadow-sm hover:shadow-xl ${diff.shadow} transition-all duration-300 overflow-hidden`}
                        >
                            {/* Top gradient bar — color matches difficulty */}
                            <div className={`h-1.5 bg-gradient-to-r ${diff.color}`} />

                            <div className="p-5">
                                {/* Header row */}
                                <div className="flex items-start justify-between mb-3">
                                    <div className="flex-1 min-w-0">
                                        <h4 className={`text-lg font-bold text-stone-800 group-hover:${diff.accent} transition-colors truncate`}>
                                            {persona.name}
                                        </h4>
                                        <div className="flex items-center space-x-2 mt-1.5 flex-wrap gap-y-1">
                                            <span className={`inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold ${diff.bg} ${diff.text} ${diff.border} border`}>
                                                {diff.icon}
                                                <span>{diff.label}</span>
                                            </span>
                                            <span className="px-2.5 py-1 rounded-lg text-xs font-medium text-stone-500 bg-stone-100">
                                                {persona.tone}
                                            </span>
                                            {persona.scenario_type && persona.scenario_type !== 'acquisition' && (
                                                <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${
                                                    persona.scenario_type === 'displacement'
                                                        ? 'bg-red-50 text-red-600 border border-red-200'
                                                        : 'bg-blue-50 text-blue-600 border border-blue-200'
                                                }`}>
                                                    {persona.scenario_type}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="p-2 bg-blue-50 rounded-xl group-hover:bg-blue-100 transition-colors ml-3">
                                        <MessageCircle className="h-5 w-5 text-blue-600" />
                                    </div>
                                </div>

                                {/* Description */}
                                <p className="text-stone-500 text-sm leading-relaxed line-clamp-2 mb-4">
                                    {persona.description}
                                </p>

                                {/* Start buttons — Sapphire Chat + Teal Voice */}
                                <div className="flex space-x-2">
                                    <button
                                        onClick={() => startSession(persona.id, 'text')}
                                        className="flex-1 flex items-center justify-center space-x-1.5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all duration-200 shadow-sm shadow-blue-500/15"
                                    >
                                        <MessageCircle size={14} />
                                        <span>Chat</span>
                                    </button>
                                    <button
                                        onClick={() => startSession(persona.id, 'voice')}
                                        className="flex-1 flex items-center justify-center space-x-1.5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-xl text-sm font-semibold transition-all duration-200 shadow-sm shadow-teal-500/15"
                                    >
                                        <Mic size={14} />
                                        <span>Voice</span>
                                    </button>
                                </div>
                            </div>
                        </motion.div>
                    );
                })}
            </div>

            {personas.length === 0 && !loading && (
                <div className="text-center py-16 bg-stone-50 rounded-2xl border border-stone-200">
                    <Users className="h-12 w-12 text-stone-300 mx-auto mb-3" />
                    <p className="text-stone-600 font-semibold">No personas available</p>
                    <p className="text-stone-400 text-sm mt-1">Please contact your administrator</p>
                </div>
            )}
        </div>
    );
}
