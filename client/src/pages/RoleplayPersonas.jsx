import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Users, MessageCircle, Target, Shield, Flame, Mic } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { PageHeader, EmptyState, RelatedLinks } from '../components/ui';

const DIFF_CONFIG = {
    beginner:     { gradient: 'from-teal-500 to-teal-700',  bg: 'bg-teal-50',  text: 'text-teal-700',  border: 'border-teal-200',  hoverBorder: 'hover:border-teal-300',  icon: <Target size={13} />,  label: 'Beginner',     topBar: 'from-teal-400 to-teal-600' },
    intermediate: { gradient: 'from-amber-500 to-amber-700', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', hoverBorder: 'hover:border-amber-300', icon: <Shield size={13} />, label: 'Intermediate', topBar: 'from-amber-400 to-amber-600' },
    advanced:     { gradient: 'from-red-500 to-red-700',    bg: 'bg-red-50',   text: 'text-red-700',   border: 'border-red-200',   hoverBorder: 'hover:border-red-300',   icon: <Flame size={13} />,  label: 'Advanced',     topBar: 'from-red-400 to-red-600' },
};

export default function RoleplayPersonas() {
    const { token } = useAuth();
    const navigate = useNavigate();
    const [personas, setPersonas] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => { fetchPersonas(); }, []);

    const fetchPersonas = async () => {
        try {
            setLoading(true);
            setError('');
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
            const response = await apiFetch('/roleplay/sessions/start', 'POST', { persona_id: personaId }, token);
            navigate(`/roleplay/chat/${response.session_id}`, { state: { mode } });
        } catch (err) {
            alert(`Failed to start session: ${err.message}`);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto mb-3" />
                    <p className="text-sm text-slate-500">Loading personas…</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <div className="w-12 h-12 bg-red-50 rounded-xl flex items-center justify-center mx-auto mb-3">
                        <Users className="h-6 w-6 text-red-400" />
                    </div>
                    <p className="text-sm text-red-600 font-medium mb-3">{error}</p>
                    <button onClick={fetchPersonas} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div>
            <PageHeader
                title="AI Roleplay"
                subtitle="Choose a buyer persona to start a sales simulation"
                backTo="/dashboard"
                backLabel="Dashboard"
            />

            {/* Step indicator */}
            <div className="flex items-center gap-2 mb-6">
                {['Choose Persona', 'Practice Session', 'Review Feedback'].map((step, i) => (
                    <React.Fragment key={step}>
                        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold ${i === 0 ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-400'}`}>
                            <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${i === 0 ? 'bg-white text-blue-600' : 'bg-slate-300 text-white'}`}>{i + 1}</span>
                            {step}
                        </div>
                        {i < 2 && <div className="w-5 h-px bg-slate-200" />}
                    </React.Fragment>
                ))}
            </div>

            {personas.length === 0 ? (
                <EmptyState
                    icon={Users}
                    title="No personas available"
                    description="Please contact your administrator to add buyer personas."
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    {personas.map((persona) => {
                        const diff = DIFF_CONFIG[persona.difficulty] || DIFF_CONFIG.intermediate;
                        return (
                            <div
                                key={persona.id}
                                className={`bg-white rounded-xl border border-slate-200 ${diff.hoverBorder} shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden`}
                            >
                                {/* Difficulty colour bar */}
                                <div className={`h-1 bg-gradient-to-r ${diff.topBar}`} />

                                <div className="p-5">
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="flex-1 min-w-0">
                                            <h3 className="text-base font-bold text-slate-800 truncate">{persona.name}</h3>
                                            <div className="flex flex-wrap items-center gap-2 mt-1.5">
                                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold border ${diff.bg} ${diff.text} ${diff.border}`}>
                                                    {diff.icon} {diff.label}
                                                </span>
                                                <span className="px-2 py-0.5 rounded-md text-xs font-medium text-slate-500 bg-slate-100">
                                                    {persona.tone}
                                                </span>
                                                {persona.scenario_type && persona.scenario_type !== 'acquisition' && (
                                                    <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${persona.scenario_type === 'displacement' ? 'bg-red-50 text-red-600 border border-red-200' : 'bg-blue-50 text-blue-600 border border-blue-200'}`}>
                                                        {persona.scenario_type}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="p-2 bg-blue-50 rounded-xl ml-3 flex-shrink-0">
                                            <MessageCircle className="h-5 w-5 text-blue-600" />
                                        </div>
                                    </div>

                                    <p className="text-sm text-slate-500 leading-relaxed line-clamp-2 mb-4">
                                        {persona.description}
                                    </p>

                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => startSession(persona.id, 'text')}
                                            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors shadow-sm"
                                        >
                                            <MessageCircle size={14} /> Chat
                                        </button>
                                        <button
                                            onClick={() => startSession(persona.id, 'voice')}
                                            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm font-semibold transition-colors shadow-sm"
                                        >
                                            <Mic size={14} /> Voice
                                        </button>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            <RelatedLinks links={[
                { label: 'Performance Dashboard', to: '/performance' },
                { label: 'Knowledge Chat',        to: '/knowledge-chat' },
            ]} />
        </div>
    );
}
