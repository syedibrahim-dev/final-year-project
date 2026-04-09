import React, { useState, useRef, useEffect } from 'react';
import { Send, Trash2, Download, MessageSquare, Sparkles, BookOpen } from 'lucide-react';
import { apiFetch } from '../utils/api';

const KnowledgeChatbot = ({ orgId, token }) => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || loading) return;

        const userMessage = {
            type: 'user',
            content: input,
            timestamp: new Date().toISOString()
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setLoading(true);

        try {
            const response = await apiFetch('/chatbot/chat', 'POST', {
                question: input,
                use_history: true,
                top_k: 5
            }, token);

            const botMessage = {
                type: 'bot',
                content: response.answer,
                sources: response.sources,
                timestamp: response.timestamp
            };

            setMessages(prev => [...prev, botMessage]);

        } catch (error) {
            console.error('Chat error:', error);
            
            const errorMessage = {
                type: 'bot',
                content: `Sorry, I encountered an error: ${error.message}`,
                timestamp: new Date().toISOString()
            };

            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setLoading(false);
        }
    };

    const handleClearHistory = async () => {
        if (!window.confirm('Clear conversation history?')) return;

        try {
            await apiFetch('/chatbot/clear-history', 'POST', null, token);
            setMessages([]);
        } catch (error) {
            console.error('Clear history error:', error);
            alert('Failed to clear history');
        }
    };

    const handleExport = async () => {
        try {
            const data = await apiFetch('/chatbot/export', 'GET', null, token);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `conversation-${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Export error:', error);
            alert('Failed to export conversation');
        }
    };

    const suggestedQuestions = [
        "What are the key sales techniques?",
        "Explain the customer onboarding process",
        "What are common objections and how to handle them?",
        "Summarize the product features"
    ];

    const handleSuggestionClick = (question) => {
        setInput(question);
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-stone-200">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-teal-500 to-teal-700 rounded-xl flex items-center justify-center shadow-md shadow-teal-500/20">
                        <Sparkles className="w-5 h-5 text-white" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-stone-800">Knowledge Assistant</h2>
                        <p className="text-sm text-stone-500">Ask questions about your training materials</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handleExport}
                        className="px-4 py-2 text-stone-600 bg-stone-100 hover:bg-stone-200 rounded-xl flex items-center gap-2 transition-colors text-sm font-medium"
                        title="Export conversation"
                    >
                        <Download className="w-4 h-4" />
                        Export
                    </button>
                    <button
                        onClick={handleClearHistory}
                        className="px-4 py-2 text-red-600 bg-red-50 hover:bg-red-100 rounded-xl flex items-center gap-2 transition-colors text-sm font-medium"
                        title="Clear history"
                    >
                        <Trash2 className="w-4 h-4" />
                        Clear
                    </button>
                </div>
            </div>

            {/* Chat Container */}
            <div className="flex flex-col flex-1 bg-white rounded-2xl border border-stone-200 overflow-hidden shadow-sm">
                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                    {messages.length === 0 && (
                        <div className="text-center text-stone-500 mt-12">
                            <div className="w-16 h-16 bg-teal-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                <MessageSquare className="w-8 h-8 text-teal-500" />
                            </div>
                            <h3 className="text-lg font-bold text-stone-700 mb-1">Start a conversation</h3>
                            <p className="mb-8 text-stone-400">Ask me anything about your training materials</p>
                            
                            {/* Suggested Questions */}
                            <div className="max-w-2xl mx-auto">
                                <p className="text-xs font-bold uppercase tracking-wide text-stone-400 mb-3">Try asking</p>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                    {suggestedQuestions.map((question, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => handleSuggestionClick(question)}
                                            className="p-3 text-left text-sm bg-stone-50 hover:bg-teal-50 hover:border-teal-200 border border-stone-200 rounded-xl transition-all duration-200 text-stone-600 hover:text-teal-700"
                                        >
                                            <span className="text-teal-500 mr-1.5">→</span> {question}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {messages.map((msg, idx) => (
                        <div
                            key={idx}
                            className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[75%] rounded-2xl p-4 ${
                                    msg.type === 'user'
                                        ? 'bg-blue-600 text-white shadow-md shadow-blue-500/15'
                                        : 'bg-stone-50 text-stone-800 border border-stone-200'
                                }`}
                            >
                                <p className="whitespace-pre-wrap leading-relaxed text-sm">{msg.content}</p>
                                
                                {msg.sources && msg.sources.length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-stone-200">
                                        <p className="text-xs font-bold mb-2 flex items-center gap-1.5 text-stone-500">
                                            <BookOpen size={12} />
                                            Sources
                                        </p>
                                        <div className="space-y-1">
                                            {msg.sources.map((source, sidx) => (
                                                <div key={sidx} className="text-xs text-stone-500">
                                                    <span className="font-medium text-stone-600">{source.filename}</span>
                                                    {source.page !== 'N/A' && ` • Page ${source.page}`}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                
                                <p className={`text-[10px] mt-2 ${msg.type === 'user' ? 'text-blue-200' : 'text-stone-400'}`}>
                                    {new Date(msg.timestamp).toLocaleTimeString()}
                                </p>
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div className="flex justify-start">
                            <div className="bg-stone-50 border border-stone-200 rounded-2xl p-4">
                                <div className="flex gap-1.5">
                                    <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4 border-t border-stone-100 bg-stone-50/50">
                    <div className="flex gap-3">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                            placeholder="Type your question here..."
                            className="flex-1 px-4 py-3 border border-stone-300 rounded-xl focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400 outline-none bg-white text-stone-800 placeholder:text-stone-400 text-sm"
                            disabled={loading}
                        />
                        <button
                            onClick={handleSend}
                            disabled={loading || !input.trim()}
                            className="px-5 py-3 bg-teal-600 text-white rounded-xl hover:bg-teal-700 disabled:bg-stone-300 disabled:cursor-not-allowed flex items-center gap-2 font-semibold text-sm transition-all shadow-sm shadow-teal-500/15"
                        >
                            <Send className="w-4 h-4" />
                            Send
                        </button>
                    </div>
                    <p className="text-xs text-stone-400 mt-2">
                        Press Enter to send • Powered by RAG
                    </p>
                </div>
            </div>
        </div>
    );
};

export default KnowledgeChatbot;