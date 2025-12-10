import React, { useState, useEffect, useRef } from 'react';
import { Loader2, Send, X, MessageCircle, User, Bot, Clock } from 'lucide-react';
import { apiFetch } from '../utils/api';

export default function RoleplayChat({ sessionId, token, onEnd }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [sessionInfo, setSessionInfo] = useState(null);
    const [loadingSession, setLoadingSession] = useState(true);
    const messagesEndRef = useRef(null);

    useEffect(() => {
        if (sessionId) {
            fetchSessionInfo();
            fetchMessages();
        }
    }, [sessionId]);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    const fetchSessionInfo = async () => {
        try {
            const data = await apiFetch(`/roleplay/sessions/${sessionId}`, 'GET', null, token);
            setSessionInfo(data);
        } catch (err) {
            console.error('Failed to load session info:', err);
        }
    };

    const fetchMessages = async () => {
        try {
            setLoadingSession(true);
            const data = await apiFetch(`/roleplay/sessions/${sessionId}/messages`, 'GET', null, token);
            setMessages(data.messages || []);
        } catch (err) {
            console.error('Failed to load messages:', err);
        } finally {
            setLoadingSession(false);
        }
    };

    const sendMessage = async (e) => {
        e.preventDefault();

        if (!input.trim() || loading) return;

        const userMessage = input.trim();
        setInput('');

        // Add user message to UI immediately
        const tempUserMsg = {
            id: Date.now(),
            sender: 'trainee',
            text: userMessage,
            timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, tempUserMsg]);

        setLoading(true);

        try {
            const response = await apiFetch(
                `/roleplay/sessions/${sessionId}/message`,
                'POST',
                { message: userMessage },
                token
            );

            // Add AI response
            const aiMsg = {
                id: response.ai_message_id,
                sender: 'ai_customer',
                text: response.ai_response,
                timestamp: new Date().toISOString()
            };
            setMessages(prev => [...prev, aiMsg]);
        } catch (err) {
            alert(`Failed to send message: ${err.message}`);
            // Remove the optimistically added message on error
            setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
        } finally {
            setLoading(false);
        }
    };

    const endSession = async () => {
        try {
            const response = await apiFetch(
                `/roleplay/sessions/${sessionId}/end`,
                'POST',
                null,
                token
            );
            
            // Navigate to feedback page with NLP evaluation data and session ID
            onEnd?.(response.nlp_evaluation, sessionId);
        } catch (err) {
            alert(`Failed to end session: ${err.message}`);
        }
    };

    if (loadingSession) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center">
                    <Loader2 className="animate-spin h-12 w-12 text-cyan-500 mx-auto mb-4" />
                    <p className="text-slate-600 font-bold">Loading conversation...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="bg-gradient-to-r from-cyan-50 via-blue-50 to-indigo-50 p-4 rounded-t-3xl border-2 border-b-0 border-cyan-100">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                        <div className="p-2 bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-xl shadow-lg">
                            <MessageCircle size={20} />
                        </div>
                        <div>
                            <h3 className="text-lg font-black text-slate-800">
                                {sessionInfo?.persona_name || 'AI Customer'}
                            </h3>
                            <p className="text-xs text-slate-500 font-semibold">
                                Practice Session • {messages.length} messages
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={endSession}
                        className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white rounded-xl shadow-lg font-bold text-sm transition-all"
                    >
                        <X size={16} />
                        <span>End Session</span>
                    </button>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gradient-to-br from-slate-50 to-cyan-50/30 border-2 border-t-0 border-b-0 border-cyan-100">
                {messages.length === 0 && (
                    <div className="text-center py-12">
                        <Bot className="h-16 w-16 text-slate-300 mx-auto mb-4" />
                        <p className="text-slate-500 font-bold">Start the conversation!</p>
                        <p className="text-slate-400 text-sm mt-2">Introduce yourself and begin your sales pitch</p>
                    </div>
                )}

                {messages.map((msg, index) => (
                    <ChatMessage key={msg.id || index} message={msg} persona={sessionInfo?.persona_name} />
                ))}

                {loading && (
                    <div className="flex items-start space-x-3">
                        <div className="p-2 bg-gradient-to-br from-slate-400 to-slate-500 text-white rounded-xl shadow-md">
                            <Bot size={20} />
                        </div>
                        <div className="flex-1 bg-white p-4 rounded-2xl shadow-md border-2 border-slate-200">
                            <div className="flex items-center space-x-2 text-slate-500">
                                <Loader2 className="animate-spin h-4 w-4" />
                                <span className="text-sm font-semibold">Customer is typing...</span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={sendMessage} className="p-4 bg-white border-2 border-t-0 border-cyan-100 rounded-b-3xl">
                <div className="flex items-center space-x-3">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Type your message..."
                        disabled={loading}
                        className="flex-1 p-3 border-2 border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                    />
                    <button
                        type="submit"
                        disabled={loading || !input.trim()}
                        className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white rounded-xl shadow-lg font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                    >
                        {loading ? (
                            <Loader2 className="animate-spin h-5 w-5" />
                        ) : (
                            <>
                                <Send size={18} />
                                <span>Send</span>
                            </>
                        )}
                    </button>
                </div>
            </form>
        </div>
    );
}

// ChatMessage Component
function ChatMessage({ message, persona }) {
    const isTrainee = message.sender === 'trainee';

    return (
        <div className={`flex items-start space-x-3 ${isTrainee ? 'flex-row-reverse space-x-reverse' : ''}`}>
            <div className={`p-2 rounded-xl shadow-md ${isTrainee
                    ? 'bg-gradient-to-br from-cyan-500 to-blue-600'
                    : 'bg-gradient-to-br from-slate-400 to-slate-500'
                } text-white`}>
                {isTrainee ? <User size={20} /> : <Bot size={20} />}
            </div>

            <div className={`flex-1 max-w-[70%]`}>
                <div className={`p-4 rounded-2xl shadow-md border-2 ${isTrainee
                        ? 'bg-gradient-to-br from-cyan-50 to-blue-50 border-cyan-200'
                        : 'bg-white border-slate-200'
                    }`}>
                    <p className={`text-sm font-bold mb-1 ${isTrainee ? 'text-cyan-700' : 'text-slate-600'
                        }`}>
                        {isTrainee ? 'You' : persona || 'Customer'}
                    </p>
                    <p className="text-slate-800 leading-relaxed">
                        {message.text}
                    </p>
                </div>
                <p className="text-xs text-slate-400 mt-1 px-2 flex items-center space-x-1">
                    <Clock size={10} />
                    <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
                </p>
            </div>
        </div>
    );
}
