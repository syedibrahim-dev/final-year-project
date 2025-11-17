import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, Send, Trophy, TrendingUp, Loader2, User, Bot } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Button } from '../App';

const AISimulationView = ({ orgId, token }) => {
    const [view, setView] = useState('lobby'); // 'lobby', 'active', 'feedback'
    const [personas, setPersonas] = useState([]);
    const [scenarios, setScenarios] = useState([]);
    const [selectedPersona, setSelectedPersona] = useState('');
    const [selectedScenario, setSelectedScenario] = useState('');
    const [session, setSession] = useState(null);
    const [messageInput, setMessageInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');
    const messagesEndRef = useRef(null);

    useEffect(() => {
        fetchPersonasAndScenarios();
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [session?.transcript]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    const fetchPersonasAndScenarios = async () => {
        setLoading(true);
        try {
            const data = await apiFetch(`/orgs/${orgId}/simulation/personas`, 'GET', null, token);
            setPersonas(data.personas);
            setScenarios(data.scenarios);
            if (data.personas.length > 0) setSelectedPersona(data.personas[0].key);
            if (data.scenarios.length > 0) setSelectedScenario(data.scenarios[0].key);
        } catch (err) {
            setError(err.message || 'Failed to load personas');
        } finally {
            setLoading(false);
        }
    };

    const handleStartSimulation = async () => {
        if (!selectedPersona || !selectedScenario) return;

        setLoading(true);
        setError('');
        try {
            const newSession = await apiFetch(`/orgs/${orgId}/simulation/start`, 'POST', {
                persona: selectedPersona,
                scenario: selectedScenario
            }, token);
            setSession(newSession);
            setView('active');
        } catch (err) {
            setError(err.message || 'Failed to start simulation');
        } finally {
            setLoading(false);
        }
    };

    const handleSendMessage = async (e) => {
        e.preventDefault();
        if (!messageInput.trim() || sending) return;

        const userMessage = messageInput.trim();
        setMessageInput('');
        setSending(true);

        try {
            const aiResponse = await apiFetch(
                `/orgs/${orgId}/simulation/${session.id}/message`,
                'POST',
                { content: userMessage },
                token
            );

            // Update local session transcript
            setSession(prev => ({
                ...prev,
                transcript: [
                    ...prev.transcript,
                    { role: 'user', content: userMessage, timestamp: new Date().toISOString() },
                    aiResponse
                ]
            }));
        } catch (err) {
            setError(err.message || 'Failed to send message');
        } finally {
            setSending(false);
        }
    };

    const handleEndSimulation = async () => {
        if (!session) return;

        setLoading(true);
        try {
            const completedSession = await apiFetch(
                `/orgs/${orgId}/simulation/${session.id}/end`,
                'POST',
                null,
                token
            );
            setSession(completedSession);
            setView('feedback');
        } catch (err) {
            setError(err.message || 'Failed to end simulation');
        } finally {
            setLoading(false);
        }
    };

    const handleNewSimulation = () => {
        setSession(null);
        setView('lobby');
        setMessageInput('');
        setError('');
    };

    // ===== LOBBY VIEW =====
    if (view === 'lobby') {
        if (loading) {
            return (
                <div className="flex items-center justify-center p-12">
                    <Loader2 className="animate-spin h-8 w-8 text-indigo-600" />
                </div>
            );
        }

        const selectedPersonaData = personas.find(p => p.key === selectedPersona);
        const selectedScenarioData = scenarios.find(s => s.key === selectedScenario);

        return (
            <div className="space-y-6">
                <div className="border-b pb-4">
                    <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                        <MessageCircle className="mr-2 text-indigo-600" size={28} />
                        AI Roleplay Simulation
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">Practice your sales skills with AI personas</p>
                </div>

                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                        <p className="font-semibold">Error</p>
                        <p>{error}</p>
                    </div>
                )}

                {/* Persona Selection */}
                <div className="space-y-3">
                    <label className="block text-sm font-semibold text-gray-700">Select Persona</label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {personas.map(persona => (
                            <button
                                key={persona.key}
                                onClick={() => setSelectedPersona(persona.key)}
                                className={`p-4 rounded-lg border-2 text-left transition-all ${
                                    selectedPersona === persona.key
                                        ? 'border-indigo-500 bg-indigo-50'
                                        : 'border-gray-200 hover:border-indigo-300'
                                }`}
                            >
                                <div className="font-semibold text-gray-800">{persona.name}</div>
                                <div className="text-sm text-gray-600">{persona.role}</div>
                                <div className="text-xs text-gray-500 mt-2">{persona.personality}</div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Scenario Selection */}
                <div className="space-y-3">
                    <label className="block text-sm font-semibold text-gray-700">Select Scenario</label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {scenarios.map(scenario => (
                            <button
                                key={scenario.key}
                                onClick={() => setSelectedScenario(scenario.key)}
                                className={`p-4 rounded-lg border-2 text-left transition-all ${
                                    selectedScenario === scenario.key
                                        ? 'border-indigo-500 bg-indigo-50'
                                        : 'border-gray-200 hover:border-indigo-300'
                                }`}
                            >
                                <div className="font-semibold text-gray-800 capitalize">
                                    {scenario.key.replace(/_/g, ' ')}
                                </div>
                                <div className="text-sm text-gray-600 mt-1">{scenario.description}</div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Start Button */}
                <div className="bg-gray-50 rounded-lg p-6">
                    <h4 className="font-semibold text-gray-800 mb-2">Ready to Start?</h4>
                    <p className="text-sm text-gray-600 mb-4">
                        You'll roleplay with <strong>{selectedPersonaData?.name}</strong> in a{' '}
                        <strong>{selectedScenarioData?.key.replace(/_/g, ' ')}</strong> scenario.
                    </p>
                    <Button onClick={handleStartSimulation} loading={loading}>
                        Start Simulation
                    </Button>
                </div>
            </div>
        );
    }

    // ===== ACTIVE CONVERSATION VIEW =====
    if (view === 'active') {
        return (
            <div className="flex flex-col h-[600px]">
                {/* Header */}
                <div className="flex-shrink-0 bg-indigo-600 text-white p-4 rounded-t-xl">
                    <div className="flex justify-between items-center">
                        <div>
                            <h4 className="font-semibold">
                                {personas.find(p => p.key === session?.persona)?.name || 'AI Persona'}
                            </h4>
                            <p className="text-xs opacity-90">
                                {scenarios.find(s => s.key === session?.scenario)?.key.replace(/_/g, ' ') || 'Scenario'}
                            </p>
                        </div>
                        <Button
                            onClick={handleEndSimulation}
                            className="bg-white text-indigo-600 hover:bg-gray-100"
                            loading={loading}
                        >
                            End & Get Feedback
                        </Button>
                    </div>
                </div>

                {/* Messages Container */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                    {session?.transcript.map((msg, idx) => (
                        <div
                            key={idx}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div className={`flex items-start space-x-2 max-w-[70%] ${
                                msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
                            }`}>
                                <div className={`p-2 rounded-full ${
                                    msg.role === 'user' ? 'bg-indigo-600' : 'bg-gray-600'
                                }`}>
                                    {msg.role === 'user' ? (
                                        <User size={16} className="text-white" />
                                    ) : (
                                        <Bot size={16} className="text-white" />
                                    )}
                                </div>
                                <div className={`p-3 rounded-lg ${
                                    msg.role === 'user'
                                        ? 'bg-indigo-600 text-white'
                                        : 'bg-white text-gray-800 border border-gray-200'
                                }`}>
                                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                    <p className={`text-xs mt-1 ${
                                        msg.role === 'user' ? 'text-indigo-200' : 'text-gray-400'
                                    }`}>
                                        {new Date(msg.timestamp).toLocaleTimeString([], {
                                            hour: '2-digit',
                                            minute: '2-digit'
                                        })}
                                    </p>
                                </div>
                            </div>
                        </div>
                    ))}
                    {sending && (
                        <div className="flex justify-start">
                            <div className="flex items-center space-x-2 bg-white p-3 rounded-lg border">
                                <Loader2 className="animate-spin text-indigo-600" size={16} />
                                <span className="text-sm text-gray-600">Typing...</span>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <form onSubmit={handleSendMessage} className="flex-shrink-0 bg-white p-4 border-t">
                    <div className="flex space-x-2">
                        <input
                            type="text"
                            value={messageInput}
                            onChange={(e) => setMessageInput(e.target.value)}
                            placeholder="Type your message..."
                            disabled={sending}
                            className="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                        />
                        <button
                            type="submit"
                            disabled={!messageInput.trim() || sending}
                            className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                        >
                            <Send size={18} />
                        </button>
                    </div>
                </form>
            </div>
        );
    }

    // ===== FEEDBACK VIEW =====
    if (view === 'feedback') {
        const score = session?.score || {};

        return (
            <div className="space-y-6">
                <div className="border-b pb-4 flex justify-between items-center">
                    <div>
                        <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                            <Trophy className="mr-2 text-yellow-500" size={28} />
                            Performance Feedback
                        </h3>
                        <p className="text-sm text-gray-500 mt-1">Review your simulation results</p>
                    </div>
                    <Button onClick={handleNewSimulation}>
                        Start New Simulation
                    </Button>
                </div>

                {/* Overall Score */}
                <div className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-xl p-8 text-center">
                    <div className="text-6xl font-bold mb-2">{score.overall || 0}</div>
                    <div className="text-xl">Overall Performance Score</div>
                </div>

                {/* Detailed Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                        { label: 'Engagement', value: score.engagement, color: 'blue' },
                        { label: 'Objection Handling', value: score.objection_handling, color: 'green' },
                        { label: 'Closing Ability', value: score.closing_ability, color: 'purple' },
                        { label: 'Discovery Questions', value: score.discovery_questions, color: 'yellow' }
                    ].map((metric, idx) => (
                        <div key={idx} className="bg-white border rounded-lg p-4 text-center">
                            <div className={`text-3xl font-bold text-${metric.color}-600 mb-1`}>
                                {metric.value || 0}
                            </div>
                            <div className="text-xs text-gray-600">{metric.label}</div>
                            <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                                <div
                                    className={`bg-${metric.color}-600 h-2 rounded-full`}
                                    style={{ width: `${metric.value || 0}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>

                {/* Recommendations */}
                {score.recommendations && score.recommendations.length > 0 && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                        <h4 className="font-semibold text-blue-900 mb-3 flex items-center">
                            <TrendingUp className="mr-2" size={20} />
                            Recommendations for Improvement
                        </h4>
                        <ul className="space-y-2">
                            {score.recommendations.map((rec, idx) => (
                                <li key={idx} className="text-sm text-blue-800 flex items-start">
                                    <span className="mr-2">•</span>
                                    <span>{rec}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Conversation Transcript */}
                <div className="bg-gray-50 rounded-lg p-6">
                    <h4 className="font-semibold text-gray-800 mb-4">Conversation Transcript</h4>
                    <div className="space-y-3 max-h-96 overflow-y-auto">
                        {session?.transcript.map((msg, idx) => (
                            <div key={idx} className={`p-3 rounded-lg ${
                                msg.role === 'user' ? 'bg-indigo-100' : 'bg-white border'
                            }`}>
                                <div className="font-semibold text-xs text-gray-600 mb-1">
                                    {msg.role === 'user' ? 'You' : personas.find(p => p.key === session.persona)?.name}
                                </div>
                                <p className="text-sm text-gray-800">{msg.content}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    return null;
};

export default AISimulationView;