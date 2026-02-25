import React, { useState, useEffect } from 'react';
import { Loader2, Award, TrendingUp, AlertCircle, CheckCircle, ArrowLeft, BarChart3, FileText } from 'lucide-react';
import { apiFetch } from '../utils/api';

export default function RoleplayFeedback({ sessionId, token, onBack, initialNlpData }) {
    const [nlpEvaluation, setNlpEvaluation] = useState(initialNlpData || null);
    const [llmFeedback, setLlmFeedback] = useState(null);
    const [loadingNlp, setLoadingNlp] = useState(!initialNlpData);
    const [loadingLlm, setLoadingLlm] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        if (sessionId) {
            fetchFeedback();
        }
    }, [sessionId]);

    const fetchFeedback = async () => {
        // Step 1: Get NLP evaluation if not provided
        if (!nlpEvaluation) {
            try {
                setLoadingNlp(true);
                const nlpData = await apiFetch(`/roleplay/sessions/${sessionId}/evaluation/nlp`, 'GET', null, token);
                setNlpEvaluation(nlpData);
            } catch (err) {
                if (err.message && err.message.includes('not long enough')) {
                    setError('Conversation is too short for analysis. Please have at least 3-4 message exchanges.');
                } else {
                    setError(err.message || 'Failed to load NLP evaluation');
                }
                setLoadingNlp(false);
                setLoadingLlm(false);
                return;
            } finally {
                setLoadingNlp(false);
            }
        }

        // Step 2: Trigger LLM evaluation in background
        try {
            setLoadingLlm(true);
            await apiFetch(`/roleplay/sessions/${sessionId}/evaluate`, 'POST', null, token);

            // Step 3: Fetch LLM feedback
            const fullData = await apiFetch(`/roleplay/sessions/${sessionId}/evaluation`, 'GET', null, token);
            setLlmFeedback(fullData);
        } catch (err) {
            console.error('LLM evaluation failed:', err);
            // Non-critical - NLP scores still visible
        } finally {
            setLoadingLlm(false);
        }
    };

    const getScoreColor = (score) => {
        if (score >= 80) return 'from-emerald-500 to-green-600';
        if (score >= 60) return 'from-blue-500 to-cyan-600';
        if (score >= 40) return 'from-amber-500 to-orange-600';
        return 'from-rose-500 to-red-600';
    };

    const getScoreLabel = (score) => {
        if (score >= 80) return 'Excellent';
        if (score >= 60) return 'Good';
        if (score >= 40) return 'Fair';
        return 'Needs Improvement';
    };

    const categoryLabels = {
        rapport_building: 'Rapport Building',
        needs_discovery: 'Needs Discovery',
        product_presentation: 'Product Presentation',
        objection_handling: 'Objection Handling',
        closing: 'Closing'
    };

    if (loadingNlp) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center">
                    <Loader2 className="animate-spin h-12 w-12 text-cyan-500 mx-auto mb-4" />
                    <p className="text-slate-700 font-bold text-lg">Loading analysis...</p>
                    <p className="text-slate-500 text-sm mt-2">Please wait</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center p-16">
                <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-rose-500 to-red-600 rounded-3xl mb-6 shadow-2xl">
                    <AlertCircle className="h-10 w-10 text-white" />
                </div>
                <p className="mt-4 text-rose-700 text-xl font-bold">{error}</p>
                <button
                    onClick={onBack}
                    className="mt-6 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-2xl font-bold hover:from-cyan-600 hover:to-blue-700 transition-all shadow-lg"
                >
                    Go Back
                </button>
            </div>
        );
    }

    if (!nlpEvaluation) return null;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-gradient-to-r from-cyan-50 via-blue-50 to-indigo-50 p-6 rounded-3xl border-2 border-cyan-100">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                        <div className="p-3 bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-2xl shadow-lg">
                            <Award size={28} />
                        </div>
                        <div>
                            <h3 className="text-3xl font-black bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-700 bg-clip-text text-transparent">
                                Performance Feedback
                            </h3>
                            <p className="text-slate-500 text-sm font-semibold">
                                NLP Analysis + AI Coach Feedback
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onBack}
                        className="flex items-center space-x-2 px-4 py-2 bg-white hover:bg-slate-50 rounded-xl border-2 border-slate-200 font-bold text-slate-700 transition-all"
                    >
                        <ArrowLeft size={16} />
                        <span>Back</span>
                    </button>
                </div>
            </div>

            {/* LLM Analysis Loading Banner */}
            {loadingLlm && (
                <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-4 rounded-2xl border-2 border-blue-200 shadow-lg">
                    <div className="flex items-center space-x-3">
                        <Loader2 className="animate-spin h-5 w-5 text-blue-600" />
                        <div>
                            <p className="text-blue-800 font-bold text-sm">AI Coach is analyzing your conversation...</p>
                            <p className="text-blue-600 text-xs">Detailed qualitative feedback will appear below (1-2 minutes)</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Overall Score (from NLP) */}
            <div className="bg-gradient-to-br from-white to-slate-50 p-8 rounded-3xl border-2 border-slate-200 shadow-xl">
                <div className="text-center">
                    <p className="text-slate-600 font-bold text-sm uppercase tracking-wide mb-4">Overall Score (NLP Analysis)</p>
                    <div className={`inline-flex items-center justify-center w-32 h-32 rounded-full bg-gradient-to-br ${getScoreColor(nlpEvaluation.overall_score)} shadow-2xl mb-4`}>
                        <div className="text-center">
                            <p className="text-5xl font-black text-white">{nlpEvaluation.overall_score}</p>
                            <p className="text-xs text-white/80 font-bold">out of 100</p>
                        </div>
                    </div>
                    <p className={`text-2xl font-black ${nlpEvaluation.overall_score >= 60 ? 'text-emerald-600' : 'text-amber-600'}`}>
                        {getScoreLabel(nlpEvaluation.overall_score)}
                    </p>
                </div>
            </div>

            {/* Category Breakdown (from NLP) */}
            <div className="bg-gradient-to-br from-white to-slate-50 p-6 rounded-3xl border-2 border-slate-200 shadow-xl">
                <div className="flex items-center space-x-2 mb-6">
                    <BarChart3 className="h-6 w-6 text-cyan-600" />
                    <h4 className="text-xl font-black text-slate-800">Category Breakdown</h4>
                </div>
                <div className="space-y-4">
                    {Object.entries(nlpEvaluation.category_scores).map(([key, score]) => (
                        <div key={key}>
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-bold text-slate-700">{categoryLabels[key]}</span>
                                <span className="text-sm font-black text-slate-800">{score}/20</span>
                            </div>
                            <div className="w-full bg-slate-200 rounded-full h-3">
                                <div
                                    className={`h-3 rounded-full bg-gradient-to-r ${getScoreColor(score * 5)} transition-all duration-500`}
                                    style={{ width: `${(score / 20) * 100}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* LLM Summary - Only show when LLM is done */}
            {!loadingLlm && llmFeedback && llmFeedback.summary && (
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-6 rounded-3xl border-2 border-blue-200 shadow-xl">
                    <div className="flex items-center space-x-2 mb-4">
                        <FileText className="h-6 w-6 text-blue-600" />
                        <h4 className="text-xl font-black text-blue-800">AI Coach Summary</h4>
                    </div>
                    <p className="text-slate-700 leading-relaxed">{llmFeedback.summary}</p>
                </div>
            )}

            {/* Strengths - Only show when LLM is done */}
            {!loadingLlm && llmFeedback && llmFeedback.strengths && (
                <div className="bg-gradient-to-br from-emerald-50 to-green-50 p-6 rounded-3xl border-2 border-emerald-200 shadow-xl">
                    <div className="flex items-center space-x-2 mb-4">
                        <CheckCircle className="h-6 w-6 text-emerald-600" />
                        <h4 className="text-xl font-black text-emerald-800">Strengths</h4>
                    </div>
                    <div className="space-y-3">
                        {llmFeedback.strengths.map((strength, index) => (
                            <div key={index} className="flex items-start space-x-3 bg-white/60 p-4 rounded-2xl">
                                <div className="flex-shrink-0 w-6 h-6 bg-emerald-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
                                    ✓
                                </div>
                                <p className="text-slate-700 font-medium">{strength}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Areas for Improvement - Only show when LLM is done */}
            {!loadingLlm && llmFeedback && llmFeedback.improvement_areas && (
                <div className="bg-gradient-to-br from-amber-50 to-orange-50 p-6 rounded-3xl border-2 border-amber-200 shadow-xl">
                    <div className="flex items-center space-x-2 mb-4">
                        <TrendingUp className="h-6 w-6 text-amber-600" />
                        <h4 className="text-xl font-black text-amber-800">Areas for Improvement</h4>
                    </div>
                    <div className="space-y-3">
                        {llmFeedback.improvement_areas.map((improvement, index) => (
                            <div key={index} className="flex items-start space-x-3 bg-white/60 p-4 rounded-2xl">
                                <div className="flex-shrink-0 w-6 h-6 bg-amber-500 rounded-full flex items-center justify-center text-white text-xs font-bold">
                                    {index + 1}
                                </div>
                                <p className="text-slate-700 font-medium">{improvement}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Coaching Tip - Only show when LLM is done */}
            {!loadingLlm && llmFeedback && llmFeedback.coaching_tip && (
                <div className="bg-gradient-to-br from-violet-50 to-purple-50 p-6 rounded-3xl border-2 border-violet-200 shadow-xl">
                    <div className="flex items-center space-x-2 mb-4">
                        <Award className="h-6 w-6 text-violet-600" />
                        <h4 className="text-xl font-black text-violet-800">💡 Coaching Tip</h4>
                    </div>
                    <p className="text-slate-700 leading-relaxed font-medium bg-white/60 p-4 rounded-2xl">
                        {llmFeedback.coaching_tip}
                    </p>
                </div>
            )}

            {/* Per-Category AI Feedback - Only show when LLM is done */}
            {!loadingLlm && llmFeedback && llmFeedback.category_feedback && Object.keys(llmFeedback.category_feedback).length > 0 && (
                <div className="bg-gradient-to-br from-slate-50 to-gray-50 p-6 rounded-3xl border-2 border-slate-200 shadow-xl">
                    <div className="flex items-center space-x-2 mb-4">
                        <BarChart3 className="h-6 w-6 text-slate-600" />
                        <h4 className="text-xl font-black text-slate-800">Detailed Category Feedback</h4>
                    </div>
                    <div className="space-y-3">
                        {Object.entries(llmFeedback.category_feedback).map(([key, comment]) => (
                            <div key={key} className="bg-white/80 p-4 rounded-2xl border border-slate-100">
                                <p className="text-sm font-black text-cyan-700 uppercase tracking-wide mb-1">
                                    {categoryLabels[key] || key.replace(/_/g, ' ')}
                                </p>
                                <p className="text-slate-700 text-sm leading-relaxed">{comment}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
