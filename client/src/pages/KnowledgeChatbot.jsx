import React, { useState, useRef, useEffect } from 'react';
import { Send, Trash2, Download, MessageSquare, ArrowLeft } from 'lucide-react';
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
            <div className="flex items-center justify-between mb-6 pb-4 border-b-2 border-slate-200">
                <div className="flex items-center gap-3">
                    <MessageSquare className="w-8 h-8 text-blue-600" />
                    <div>
                        <h2 className="text-2xl font-bold text-gray-900">Knowledge Assistant</h2>
                        <p className="text-sm text-gray-500">Ask questions about your training materials</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handleExport}
                        className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg flex items-center gap-2 transition-colors"
                        title="Export conversation"
                    >
                        <Download className="w-4 h-4" />
                        Export
                    </button>
                    <button
                        onClick={handleClearHistory}
                        className="px-4 py-2 text-red-600 bg-red-50 hover:bg-red-100 rounded-lg flex items-center gap-2 transition-colors"
                        title="Clear history"
                    >
                        <Trash2 className="w-4 h-4" />
                        Clear
                    </button>
                </div>
            </div>

            {/* Chat Container */}
            <div className="flex flex-col flex-1 bg-white rounded-lg border-2 border-slate-200 overflow-hidden">
                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                    {messages.length === 0 && (
                        <div className="text-center text-gray-500 mt-12">
                            <MessageSquare className="w-16 h-16 mx-auto mb-4 opacity-30" />
                            <h3 className="text-lg font-semibold mb-2">Start a conversation</h3>
                            <p className="mb-6">Ask me anything about your training materials</p>
                            
                            {/* Suggested Questions */}
                            <div className="max-w-2xl mx-auto">
                                <p className="text-sm font-medium mb-3">Try asking:</p>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                    {suggestedQuestions.map((question, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => handleSuggestionClick(question)}
                                            className="p-3 text-left text-sm bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                                        >
                                            💡 {question}
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
                                className={`max-w-[75%] rounded-lg p-4 shadow-sm ${
                                    msg.type === 'user'
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-100 text-gray-900'
                                }`}
                            >
                                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                                
                                {msg.sources && msg.sources.length > 0 && (
                                    <div className="mt-4 pt-3 border-t border-gray-300">
                                        <p className="text-xs font-semibold mb-2 opacity-75">📚 Sources:</p>
                                        <div className="space-y-1">
                                            {msg.sources.map((source, sidx) => (
                                                <div key={sidx} className="text-xs opacity-75">
                                                    <span className="font-medium">{source.filename}</span>
                                                    {source.page !== 'N/A' && ` • Page ${source.page}`}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                
                                <p className="text-xs opacity-50 mt-2">
                                    {new Date(msg.timestamp).toLocaleTimeString()}
                                </p>
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div className="flex justify-start">
                            <div className="bg-gray-100 rounded-lg p-4 shadow-sm">
                                <div className="flex gap-1">
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4 border-t bg-gray-50">
                    <div className="flex gap-3">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                            placeholder="Type your question here..."
                            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                            disabled={loading}
                        />
                        <button
                            onClick={handleSend}
                            disabled={loading || !input.trim()}
                            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2 font-medium transition-colors"
                        >
                            <Send className="w-5 h-5" />
                            Send
                        </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                        Press Enter to send • Shift+Enter for new line
                    </p>
                </div>
            </div>
        </div>
    );
};

export default KnowledgeChatbot;