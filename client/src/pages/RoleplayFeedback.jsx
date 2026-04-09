import React, { useState, useEffect, useRef } from 'react';
import { Loader2, Award, TrendingUp, AlertCircle, CheckCircle, ArrowLeft, BarChart3, FileText, Target, Lightbulb, Heart, MessageCircle, RefreshCw, Activity } from 'lucide-react';
import * as d3 from 'd3';
import { apiFetch } from '../utils/api';

// ── D3 Conversion Trajectory Chart ──────────────────────────────────
function ConversionTrajectoryChart({ probabilities, turningPoints = [] }) {
    const containerRef = useRef(null);
    const svgRef = useRef(null);

    useEffect(() => {
        if (!probabilities || probabilities.length < 2 || !svgRef.current) return;

        const width = containerRef.current?.clientWidth || 500;
        const height = 200;
        const margin = { top: 20, right: 24, bottom: 30, left: 40 };
        const inner = { w: width - margin.left - margin.right, h: height - margin.top - margin.bottom };

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();
        svg.attr('width', width).attr('height', height);

        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear().domain([1, probabilities.length]).range([0, inner.w]);
        const y = d3.scaleLinear().domain([0, 1]).range([inner.h, 0]);

        // Zone fills
        const zones = [
            { y0: 0, y1: 0.3, color: '#fef2f2', label: 'Low' },
            { y0: 0.3, y1: 0.6, color: '#fffbeb', label: 'Medium' },
            { y0: 0.6, y1: 1.0, color: '#f0fdf4', label: 'High' },
        ];
        zones.forEach(z => {
            g.append('rect')
                .attr('x', 0).attr('width', inner.w)
                .attr('y', y(z.y1)).attr('height', y(z.y0) - y(z.y1))
                .attr('fill', z.color).attr('opacity', 0.8);
            g.append('text')
                .attr('x', inner.w + 4).attr('y', y((z.y0 + z.y1) / 2) + 3)
                .attr('font-size', '9px').attr('fill', '#94a3b8').attr('font-weight', '600')
                .text(z.label);
        });

        // Grid
        [0.3, 0.6].forEach(v => {
            g.append('line').attr('x1', 0).attr('x2', inner.w)
                .attr('y1', y(v)).attr('y2', y(v))
                .attr('stroke', '#cbd5e1').attr('stroke-dasharray', '4,4').attr('stroke-width', 0.5);
        });

        // Gradient definition
        const defs = svg.append('defs');
        const grad = defs.append('linearGradient').attr('id', 'trajGrad')
            .attr('x1', '0').attr('y1', '0').attr('x2', '0').attr('y2', '1');
        grad.append('stop').attr('offset', '0%').attr('stop-color', '#6366f1').attr('stop-opacity', 0.35);
        grad.append('stop').attr('offset', '100%').attr('stop-color', '#6366f1').attr('stop-opacity', 0.03);

        // Glow filter
        const filter = defs.append('filter').attr('id', 'glow');
        filter.append('feGaussianBlur').attr('stdDeviation', '2').attr('result', 'blur');
        filter.append('feMerge').selectAll('feMergeNode')
            .data(['blur', 'SourceGraphic']).join('feMergeNode').attr('in', d => d);

        // Area
        const area = d3.area()
            .x((d, i) => x(i + 1)).y0(inner.h).y1(d => y(d))
            .curve(d3.curveMonotoneX);
        g.append('path').datum(probabilities).attr('d', area).attr('fill', 'url(#trajGrad)');

        // Line with glow
        const line = d3.line().x((d, i) => x(i + 1)).y(d => y(d)).curve(d3.curveMonotoneX);
        g.append('path').datum(probabilities).attr('d', line)
            .attr('fill', 'none').attr('stroke', '#6366f1').attr('stroke-width', 3)
            .attr('stroke-linecap', 'round').attr('filter', 'url(#glow)');

        // Data points with color coding
        probabilities.forEach((prob, i) => {
            const cx = x(i + 1), cy = y(prob);
            const color = prob >= 0.6 ? '#10b981' : prob >= 0.3 ? '#f59e0b' : '#ef4444';

            // Outer ring
            g.append('circle').attr('cx', cx).attr('cy', cy).attr('r', 7)
                .attr('fill', 'white').attr('stroke', color).attr('stroke-width', 2.5)
                .attr('opacity', 0.9);

            // Inner dot
            g.append('circle').attr('cx', cx).attr('cy', cy).attr('r', 3)
                .attr('fill', color);

            // Value label
            g.append('text').attr('x', cx).attr('y', cy - 12)
                .attr('text-anchor', 'middle').attr('font-size', '10px')
                .attr('font-weight', '700').attr('fill', '#334155')
                .text(`${Math.round(prob * 100)}%`);
        });

        // Turning point annotations
        turningPoints.forEach(tp => {
            const turnIdx = (tp.turn || 1) - 1;
            if (turnIdx >= 0 && turnIdx < probabilities.length) {
                const cx = x(turnIdx + 1), cy = y(probabilities[turnIdx]);
                const isPositive = tp.direction === 'positive';
                const delta = tp.delta || 0;

                // Diamond marker
                g.append('path')
                    .attr('d', `M${cx},${cy - 16} L${cx + 6},${cy - 10} L${cx},${cy - 4} L${cx - 6},${cy - 10} Z`)
                    .attr('fill', isPositive ? '#10b981' : '#ef4444')
                    .attr('opacity', 0.8);

                // Delta label
                g.append('text').attr('x', cx).attr('y', cy - 22)
                    .attr('text-anchor', 'middle').attr('font-size', '9px')
                    .attr('font-weight', '700')
                    .attr('fill', isPositive ? '#059669' : '#dc2626')
                    .text(`${delta > 0 ? '+' : ''}${Math.round(delta * 100)}%`);
            }
        });

        // X axis
        g.append('line').attr('x1', 0).attr('x2', inner.w)
            .attr('y1', inner.h).attr('y2', inner.h)
            .attr('stroke', '#e2e8f0').attr('stroke-width', 1);

        probabilities.forEach((_, i) => {
            g.append('text').attr('x', x(i + 1)).attr('y', inner.h + 16)
                .attr('text-anchor', 'middle').attr('font-size', '10px').attr('fill', '#64748b')
                .text(`Turn ${i + 1}`);
        });

        // Y axis
        [0, 25, 50, 75, 100].forEach(v => {
            g.append('text').attr('x', -8).attr('y', y(v / 100) + 4)
                .attr('text-anchor', 'end').attr('font-size', '9px').attr('fill', '#94a3b8')
                .text(`${v}%`);
        });

    }, [probabilities, turningPoints]);

    if (!probabilities || probabilities.length < 2) return null;

    return (
        <div ref={containerRef} className="w-full">
            <svg ref={svgRef} className="w-full" />
        </div>
    );
}

export default function RoleplayFeedback({ sessionId, token, onBack, initialNlpData, conversionHistory }) {
    const [nlpEvaluation, setNlpEvaluation] = useState(initialNlpData || null);
    const [llmFeedback, setLlmFeedback] = useState(null);
    const [loadingNlp, setLoadingNlp] = useState(!initialNlpData);
    const [loadingLlm, setLoadingLlm] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => { if (sessionId) fetchFeedback(); }, [sessionId]);

    const fetchFeedback = async () => {
        if (!nlpEvaluation) {
            try {
                setLoadingNlp(true);
                const nlpData = await apiFetch(`/roleplay/sessions/${sessionId}/evaluation/nlp`, 'GET', null, token);
                setNlpEvaluation(nlpData);
            } catch (err) {
                if (err.message && err.message.includes('not long enough')) {
                    setError('Conversation too short for analysis. Need at least 3-4 exchanges.');
                } else {
                    setError(err.message || 'Failed to load evaluation');
                }
                setLoadingNlp(false);
                setLoadingLlm(false);
                return;
            } finally { setLoadingNlp(false); }
        }

        try {
            setLoadingLlm(true);
            await apiFetch(`/roleplay/sessions/${sessionId}/evaluate`, 'POST', null, token);
            const fullData = await apiFetch(`/roleplay/sessions/${sessionId}/evaluation`, 'GET', null, token);
            setLlmFeedback(fullData);
        } catch (err) {
            console.error('LLM evaluation failed:', err);
        } finally { setLoadingLlm(false); }
    };

    const getScoreColor = (score) => {
        if (score >= 80) return 'from-emerald-500 to-teal-600';
        if (score >= 60) return 'from-indigo-500 to-violet-600';
        if (score >= 40) return 'from-amber-500 to-orange-600';
        return 'from-rose-500 to-red-600';
    };

    const getScoreLabel = (score) => {
        if (score >= 80) return 'Excellent';
        if (score >= 60) return 'Good';
        if (score >= 40) return 'Fair';
        return 'Needs Work';
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
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <Loader2 className="animate-spin h-10 w-10 text-indigo-500 mx-auto mb-3" />
                    <p className="text-slate-500 font-medium">Analyzing performance...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <div className="w-14 h-14 bg-red-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <AlertCircle className="h-7 w-7 text-red-500" />
                    </div>
                    <p className="text-red-600 font-semibold mb-3">{error}</p>
                    <button onClick={onBack} className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors">
                        Go Back
                    </button>
                </div>
            </div>
        );
    }

    if (!nlpEvaluation) return null;

    return (
        <div className="space-y-5 animate-fadeInUp">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-2xl font-bold text-slate-800">Performance Feedback</h3>
                    <p className="text-slate-500 text-sm">NLP Analysis + AI Coach Insights</p>
                </div>
                <button
                    onClick={onBack}
                    className="flex items-center space-x-1.5 px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-sm font-medium text-slate-600 transition-colors"
                >
                    <ArrowLeft size={14} />
                    <span>Back</span>
                </button>
            </div>

            {/* LLM Loading Banner */}
            {loadingLlm && (
                <div className="flex items-center space-x-3 p-4 bg-indigo-50 border border-indigo-200 rounded-xl">
                    <Loader2 className="animate-spin h-4 w-4 text-indigo-600 flex-shrink-0" />
                    <div>
                        <p className="text-indigo-800 font-semibold text-sm">AI Coach is analyzing your conversation...</p>
                        <p className="text-indigo-600 text-xs">Detailed feedback will appear below (1-2 min)</p>
                    </div>
                </div>
            )}

            {/* Overall Score */}
            <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm text-center">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Overall Score</p>
                <div className={`inline-flex items-center justify-center w-28 h-28 rounded-full bg-gradient-to-br ${getScoreColor(nlpEvaluation.overall_score)} shadow-xl mb-3`}>
                    <div className="text-center">
                        <p className="text-4xl font-bold text-white">{nlpEvaluation.overall_score}</p>
                        <p className="text-[10px] text-white/70 font-medium">/ 100</p>
                    </div>
                </div>
                <p className={`text-lg font-bold ${nlpEvaluation.overall_score >= 60 ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {getScoreLabel(nlpEvaluation.overall_score)}
                </p>
            </div>

            {/* Category Breakdown */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="flex items-center space-x-2 mb-5">
                    <BarChart3 className="h-5 w-5 text-indigo-600" />
                    <h4 className="text-base font-bold text-slate-800">Category Breakdown</h4>
                </div>
                <div className="space-y-4">
                    {Object.entries(nlpEvaluation.category_scores).map(([key, score]) => (
                        <div key={key}>
                            <div className="flex items-center justify-between mb-1.5">
                                <span className="text-sm font-medium text-slate-600">{categoryLabels[key]}</span>
                                <span className="text-sm font-bold text-slate-800">{score}/20</span>
                            </div>
                            <div className="w-full bg-slate-100 rounded-full h-2">
                                <div
                                    className={`h-2 rounded-full bg-gradient-to-r ${getScoreColor(score * 5)} transition-all duration-700`}
                                    style={{ width: `${(score / 20) * 100}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Conversation Analytics */}
            {nlpEvaluation.detailed_metrics?.tier1 && (
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <div className="flex items-center space-x-2 mb-5">
                        <BarChart3 className="h-5 w-5 text-cyan-600" />
                        <h4 className="text-base font-bold text-slate-800">Conversation Analytics</h4>
                        <span className="text-[9px] font-semibold text-cyan-500 bg-cyan-50 px-2 py-0.5 rounded-full border border-cyan-200">Gong Labs Research</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
                        {/* Talk Ratio */}
                        <div className="bg-slate-50 p-4 rounded-xl text-center">
                            <p className="text-3xl font-bold text-slate-800">
                                {Math.round((nlpEvaluation.detailed_metrics.tier1.dynamics?.trainee_speaking_ratio || 0) * 100)}%
                            </p>
                            <p className="text-[10px] text-slate-500 font-semibold uppercase mt-1">Talk Ratio (Target: 43%)</p>
                            <p className="text-xs text-slate-400 mt-1">{nlpEvaluation.detailed_metrics.tier1.dynamics?.talk_ratio_assessment || ''}</p>
                        </div>
                        {/* Longest Monologue */}
                        <div className="bg-slate-50 p-4 rounded-xl text-center">
                            <p className={`text-3xl font-bold ${(nlpEvaluation.detailed_metrics.tier1.dynamics?.longest_monologue_words || 0) > 120 ? 'text-red-500' : 'text-emerald-600'}`}>
                                {nlpEvaluation.detailed_metrics.tier1.dynamics?.longest_monologue_words || 0}
                            </p>
                            <p className="text-[10px] text-slate-500 font-semibold uppercase mt-1">Longest Monologue (words)</p>
                            {(nlpEvaluation.detailed_metrics.tier1.dynamics?.longest_monologue_words || 0) > 120 && (
                                <p className="text-xs text-red-400 mt-1">Exceeds 120-word threshold</p>
                            )}
                        </div>
                        {/* Question Count */}
                        <div className="bg-slate-50 p-4 rounded-xl text-center">
                            <p className="text-3xl font-bold text-indigo-600">
                                {nlpEvaluation.detailed_metrics.tier1.questions?.total_questions || 0}
                            </p>
                            <p className="text-[10px] text-slate-500 font-semibold uppercase mt-1">Questions Asked</p>
                            <p className="text-xs text-slate-400 mt-1">
                                {nlpEvaluation.detailed_metrics.tier1.questions?.open_questions || 0} open, {nlpEvaluation.detailed_metrics.tier1.questions?.closed_questions || 0} closed
                            </p>
                        </div>
                    </div>

                    {/* SPIN Analysis */}
                    {nlpEvaluation.detailed_metrics.tier1.questions?.spin_analysis && (
                        <div className="mt-4">
                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-3">SPIN Question Analysis (Rackham, 1988)</p>
                            <div className="grid grid-cols-4 gap-2 mb-3">
                                {[
                                    { key: 'situation', label: 'Situation', color: 'bg-blue-100 text-blue-700' },
                                    { key: 'problem', label: 'Problem', color: 'bg-amber-100 text-amber-700' },
                                    { key: 'implication', label: 'Implication', color: 'bg-orange-100 text-orange-700' },
                                    { key: 'need_payoff', label: 'Need-Payoff', color: 'bg-emerald-100 text-emerald-700' },
                                ].map(({ key, label, color }) => (
                                    <div key={key} className={`${color} rounded-lg p-3 text-center`}>
                                        <p className="text-2xl font-bold">{nlpEvaluation.detailed_metrics.tier1.questions.spin_analysis[key] || 0}</p>
                                        <p className="text-[10px] font-semibold uppercase">{label}</p>
                                    </div>
                                ))}
                            </div>
                            <p className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg">
                                {nlpEvaluation.detailed_metrics.tier1.questions.spin_analysis.spin_quality}
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* AI Coach Summary */}
            {!loadingLlm && llmFeedback && llmFeedback.summary && (
                <div className="bg-indigo-50 rounded-2xl border border-indigo-200 p-5">
                    <div className="flex items-center space-x-2 mb-3">
                        <FileText className="h-4 w-4 text-indigo-600" />
                        <h4 className="text-sm font-bold text-indigo-800">AI Coach Summary</h4>
                    </div>
                    <p className="text-slate-700 text-sm leading-relaxed">{llmFeedback.summary}</p>
                </div>
            )}

            {/* Strengths & Improvements side by side */}
            {!loadingLlm && llmFeedback && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Strengths */}
                    {llmFeedback.strengths && (
                        <div className="bg-emerald-50 rounded-2xl border border-emerald-200 p-5">
                            <div className="flex items-center space-x-2 mb-3">
                                <CheckCircle className="h-4 w-4 text-emerald-600" />
                                <h4 className="text-sm font-bold text-emerald-800">Strengths</h4>
                            </div>
                            <div className="space-y-2">
                                {llmFeedback.strengths.map((s, i) => (
                                    <div key={i} className="flex items-start space-x-2 text-sm">
                                        <span className="text-emerald-500 mt-0.5 flex-shrink-0">✓</span>
                                        <p className="text-slate-700">{s}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Improvements */}
                    {llmFeedback.improvement_areas && (
                        <div className="bg-amber-50 rounded-2xl border border-amber-200 p-5">
                            <div className="flex items-center space-x-2 mb-3">
                                <TrendingUp className="h-4 w-4 text-amber-600" />
                                <h4 className="text-sm font-bold text-amber-800">Improve</h4>
                            </div>
                            <div className="space-y-2">
                                {llmFeedback.improvement_areas.map((item, i) => (
                                    <div key={i} className="flex items-start space-x-2 text-sm">
                                        <span className="w-5 h-5 bg-amber-400 rounded-full flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0 mt-0.5">{i + 1}</span>
                                        <p className="text-slate-700">{item}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Stage Performance */}
            {!loadingLlm && llmFeedback && llmFeedback.stage_performance && Object.keys(llmFeedback.stage_performance).length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                    <div className="flex items-center space-x-2 mb-4">
                        <Target className="h-4 w-4 text-indigo-600" />
                        <h4 className="text-sm font-bold text-slate-800">Per-Stage Performance</h4>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {Object.entries(llmFeedback.stage_performance).map(([key, comment]) => (
                            <div key={key} className="bg-slate-50 p-3 rounded-xl">
                                <p className="text-[10px] font-bold text-indigo-600 uppercase tracking-wide mb-1">
                                    {key.replace(/_/g, ' ')}
                                </p>
                                <p className="text-slate-600 text-xs leading-relaxed">{comment}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Coaching Tip */}
            {!loadingLlm && llmFeedback && llmFeedback.coaching_tip && (
                <div className="bg-violet-50 rounded-2xl border border-violet-200 p-5">
                    <div className="flex items-center space-x-2 mb-2">
                        <Lightbulb className="h-4 w-4 text-violet-600" />
                        <h4 className="text-sm font-bold text-violet-800">Key Coaching Tip</h4>
                    </div>
                    <p className="text-slate-700 text-sm leading-relaxed">{llmFeedback.coaching_tip}</p>
                </div>
            )}

            {/* Practice Recommendations (Ericsson's Deliberate Practice) */}
            {!loadingLlm && llmFeedback && llmFeedback.practice_recommendations && llmFeedback.practice_recommendations.weakest_area && (
                <div className="bg-cyan-50 rounded-2xl border border-cyan-200 p-5">
                    <div className="flex items-center space-x-2 mb-3">
                        <Target className="h-4 w-4 text-cyan-600" />
                        <h4 className="text-sm font-bold text-cyan-800">Next Session Recommendation</h4>
                        <span className="text-[9px] font-semibold text-cyan-500 bg-white px-2 py-0.5 rounded-full border border-cyan-200">Deliberate Practice</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div className="bg-white rounded-xl p-3">
                            <p className="text-[10px] font-bold text-red-500 uppercase tracking-wide mb-1">Weakest Area</p>
                            <p className="text-sm font-semibold text-slate-800">{(llmFeedback.practice_recommendations.weakest_area || '').replace(/_/g, ' ')}</p>
                        </div>
                        <div className="bg-white rounded-xl p-3">
                            <p className="text-[10px] font-bold text-amber-500 uppercase tracking-wide mb-1">Focus On</p>
                            <p className="text-sm text-slate-700">{llmFeedback.practice_recommendations.recommended_focus}</p>
                        </div>
                        <div className="bg-white rounded-xl p-3">
                            <p className="text-[10px] font-bold text-emerald-500 uppercase tracking-wide mb-1">Try Persona</p>
                            <p className="text-sm text-slate-700">{llmFeedback.practice_recommendations.suggested_persona_type}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Detailed Category Feedback */}
            {!loadingLlm && llmFeedback && llmFeedback.category_feedback && Object.keys(llmFeedback.category_feedback).length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                    <div className="flex items-center space-x-2 mb-4">
                        <BarChart3 className="h-4 w-4 text-slate-600" />
                        <h4 className="text-sm font-bold text-slate-800">Detailed Category Feedback</h4>
                    </div>
                    <div className="space-y-3">
                        {Object.entries(llmFeedback.category_feedback).map(([key, comment]) => (
                            <div key={key} className="bg-slate-50 p-4 rounded-xl">
                                <p className="text-[10px] font-bold text-indigo-600 uppercase tracking-wide mb-1">
                                    {categoryLabels[key] || key.replace(/_/g, ' ')}
                                </p>
                                <p className="text-slate-600 text-sm leading-relaxed">{comment}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* EQ Summary */}
            {!loadingLlm && llmFeedback && llmFeedback.eq_summary && llmFeedback.eq_summary.average_score > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                    <div className="flex items-center space-x-2 mb-4">
                        <Heart className="h-4 w-4 text-rose-500" />
                        <h4 className="text-sm font-bold text-slate-800">Emotional Intelligence Score</h4>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                        <div className="text-center p-4 bg-rose-50 rounded-xl">
                            <p className="text-3xl font-bold text-rose-600">{llmFeedback.eq_summary.average_score}</p>
                            <p className="text-[10px] text-rose-500 font-semibold uppercase mt-1">Average EQ</p>
                        </div>
                        <div className="text-center p-4 bg-indigo-50 rounded-xl">
                            <p className="text-3xl font-bold text-indigo-600">{llmFeedback.eq_summary.final_score}</p>
                            <p className="text-[10px] text-indigo-500 font-semibold uppercase mt-1">Final EQ</p>
                        </div>
                        <div className="text-center p-4 bg-slate-50 rounded-xl">
                            <p className={`text-lg font-bold ${llmFeedback.eq_summary.trend === 'improving' ? 'text-emerald-600' :
                                llmFeedback.eq_summary.trend === 'declining' ? 'text-red-600' : 'text-slate-600'
                                }`}>
                                {llmFeedback.eq_summary.trend === 'improving' ? '↗ Improving' :
                                    llmFeedback.eq_summary.trend === 'declining' ? '↘ Declining' : '→ Stable'}
                            </p>
                            <p className="text-[10px] text-slate-500 font-semibold uppercase mt-1">
                                Over {llmFeedback.eq_summary.total_messages_scored} messages
                            </p>
                        </div>
                    </div>

                    {/* LAER Assessment */}
                    {llmFeedback.eq_summary?.laer_assessment?.applicable && (
                        <div className="mt-5 pt-4 border-t border-slate-100">
                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-3">LAER Objection Handling (Carew International)</p>
                            <div className="grid grid-cols-4 gap-2">
                                {['listen', 'acknowledge', 'explore', 'respond'].map((step) => {
                                    const detected = llmFeedback.eq_summary.laer_assessment.steps_detected?.includes(step);
                                    return (
                                        <div key={step} className={`rounded-lg p-3 text-center ${detected ? 'bg-emerald-50 border border-emerald-200' : 'bg-red-50 border border-red-200'}`}>
                                            <p className={`text-lg font-bold ${detected ? 'text-emerald-600' : 'text-red-400'}`}>
                                                {detected ? 'Yes' : 'No'}
                                            </p>
                                            <p className="text-[10px] font-semibold uppercase text-slate-500">{step}</p>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {/* WLEIS Dimensions */}
                    {llmFeedback.eq_summary?.wleis_dimensions && (
                        <div className="mt-4 pt-4 border-t border-slate-100">
                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-3">EQ Dimensions (Wong & Law WLEIS, 2002)</p>
                            <div className="space-y-2">
                                {[
                                    { key: 'others_emotion_appraisal', label: 'Reading Prospect Emotions', abbr: 'OEA' },
                                    { key: 'regulation_of_emotion', label: 'Managing Own Composure', abbr: 'ROE' },
                                    { key: 'use_of_emotion', label: 'Active Listening', abbr: 'UOE' },
                                    { key: 'self_emotion_appraisal', label: 'Self-Awareness', abbr: 'SEA' },
                                ].map(({ key, label, abbr }) => {
                                    const val = llmFeedback.eq_summary.wleis_dimensions[key] || 0;
                                    return (
                                        <div key={key}>
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="text-xs text-slate-600"><span className="font-semibold text-indigo-600">{abbr}</span> {label}</span>
                                                <span className="text-xs font-bold text-slate-800">{Math.round(val)}</span>
                                            </div>
                                            <div className="w-full bg-slate-100 rounded-full h-1.5">
                                                <div className={`h-1.5 rounded-full ${val >= 70 ? 'bg-emerald-500' : val >= 40 ? 'bg-amber-400' : 'bg-red-400'}`}
                                                    style={{ width: `${Math.min(100, val)}%` }} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Conversion Trajectory (SalesRLAgent) — D3 Chart */}
            {(() => {
                // Use conversionHistory from live session, or fallback to llmFeedback.conversion_trajectory
                const liveProbs = conversionHistory && conversionHistory.length >= 2 ? conversionHistory : null;
                const traj = llmFeedback?.conversion_trajectory || {};
                const probs = liveProbs || (traj.probabilities && traj.probabilities.length >= 2 ? traj.probabilities : null);

                if (!probs) return null;

                const finalProb = Math.round(probs[probs.length - 1] * 100);
                const firstProb = Math.round(probs[0] * 100);
                const trend = finalProb > firstProb + 5 ? 'improving' : finalProb < firstProb - 5 ? 'declining' : 'stable';

                // Compute turning points from the probability array
                const turningPoints = [];
                for (let i = 1; i < probs.length; i++) {
                    const delta = probs[i] - probs[i - 1];
                    if (Math.abs(delta) > 0.08) {
                        turningPoints.push({
                            turn: i + 1,
                            delta,
                            direction: delta > 0 ? 'positive' : 'negative',
                        });
                    }
                }

                const getProbColor = (p) => {
                    if (p >= 60) return 'from-emerald-500 to-teal-600';
                    if (p >= 35) return 'from-amber-400 to-yellow-500';
                    return 'from-rose-500 to-red-500';
                };

                return (
                    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                        <div className="flex items-center space-x-2 mb-4">
                            <Activity className="h-4 w-4 text-indigo-600" />
                            <h4 className="text-sm font-bold text-slate-800">Conversion Probability Trajectory</h4>
                            <span className="text-[9px] font-semibold text-indigo-400 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200">SalesRL Agent</span>
                        </div>

                        {/* Summary row */}
                        <div className="grid grid-cols-3 gap-4 mb-5">
                            <div className="text-center p-4 bg-slate-50 rounded-xl">
                                <div className={`inline-flex items-center justify-center w-14 h-14 rounded-full bg-gradient-to-br ${getProbColor(finalProb)} shadow-md mb-2`}>
                                    <span className="text-white font-bold text-lg">{finalProb}%</span>
                                </div>
                                <p className="text-[10px] text-slate-500 font-semibold uppercase">Final Probability</p>
                            </div>
                            <div className="text-center p-4 bg-slate-50 rounded-xl flex flex-col items-center justify-center">
                                <p className={`text-lg font-bold ${trend === 'improving' ? 'text-emerald-600' :
                                    trend === 'declining' ? 'text-red-600' : 'text-slate-600'
                                    }`}>
                                    {trend === 'improving' ? '↗ Improving' :
                                        trend === 'declining' ? '↘ Declining' : '→ Stable'}
                                </p>
                                <p className="text-[10px] text-slate-500 font-semibold uppercase mt-1">Overall Trend</p>
                            </div>
                            <div className="text-center p-4 bg-slate-50 rounded-xl flex flex-col items-center justify-center">
                                <p className="text-2xl font-bold text-indigo-600">{probs.length}</p>
                                <p className="text-[10px] text-slate-500 font-semibold uppercase mt-1">Turns Analyzed</p>
                            </div>
                        </div>

                        {/* D3 Trend Chart */}
                        <div className="mb-4">
                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">Conversation Trend Visualization</p>
                            <ConversionTrajectoryChart probabilities={probs} turningPoints={turningPoints} />
                        </div>

                        {/* Turning points list */}
                        {turningPoints.length > 0 && (
                            <div>
                                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">Turning Points</p>
                                <div className="space-y-1.5">
                                    {turningPoints.map((tp, i) => (
                                        <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs ${tp.direction === 'positive'
                                                ? 'bg-emerald-50 border border-emerald-200'
                                                : 'bg-rose-50 border border-rose-200'
                                            }`}>
                                            <span className={`font-semibold ${tp.direction === 'positive' ? 'text-emerald-700' : 'text-rose-700'}`}>
                                                Turn {tp.turn} — {tp.direction === 'positive' ? '↑' : '↓'} {Math.abs(Math.round(tp.delta * 100))}% shift
                                            </span>
                                            <span className="text-slate-500">
                                                {Math.round(probs[tp.turn - 2] * 100)}% → {Math.round(probs[tp.turn - 1] * 100)}%
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                );
            })()}

            {/* Key Moments (Replay) */}
            {!loadingLlm && llmFeedback && llmFeedback.replay && llmFeedback.replay.key_moments && llmFeedback.replay.key_moments.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                    <div className="flex items-center space-x-2 mb-4">
                        <MessageCircle className="h-4 w-4 text-violet-600" />
                        <h4 className="text-sm font-bold text-slate-800">Key Moments</h4>
                    </div>
                    <div className="space-y-3">
                        {llmFeedback.replay.annotations?.map((a, i) => {
                            const typeConfig = {
                                turning_point: { bg: 'bg-indigo-50 border-indigo-200', text: 'text-indigo-700', badge: 'bg-indigo-500', label: 'Turning Point' },
                                missed_signal: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', badge: 'bg-amber-500', label: 'Missed Signal' },
                                strong_moment: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', badge: 'bg-emerald-500', label: 'Strong' },
                                weak_moment: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', badge: 'bg-red-500', label: 'Needs Work' },
                            };
                            const cfg = typeConfig[a.type] || typeConfig.turning_point;
                            return (
                                <div key={i} className={`p-3 rounded-xl border ${cfg.bg} flex items-start space-x-3`}>
                                    <span className={`text-[9px] font-bold text-white px-2 py-0.5 rounded-full ${cfg.badge} flex-shrink-0 mt-0.5`}>
                                        #{a.message_index}
                                    </span>
                                    <div>
                                        <span className={`text-[10px] font-bold uppercase tracking-wide ${cfg.text}`}>
                                            {cfg.label} • {a.speaker}
                                        </span>
                                        <p className="text-slate-700 text-xs mt-0.5 leading-relaxed">{a.comment}</p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Alternative Responses */}
            {!loadingLlm && llmFeedback && llmFeedback.replay && llmFeedback.replay.alternative_responses && llmFeedback.replay.alternative_responses.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                    <div className="flex items-center space-x-2 mb-4">
                        <RefreshCw className="h-4 w-4 text-cyan-600" />
                        <h4 className="text-sm font-bold text-slate-800">What You Could Have Said</h4>
                    </div>
                    <div className="space-y-4">
                        {llmFeedback.replay.alternative_responses.map((alt, i) => (
                            <div key={i} className="bg-slate-50 rounded-xl p-4 space-y-2">
                                <div className="flex items-start space-x-2">
                                    <span className="text-red-400 text-xs font-bold mt-0.5">✕</span>
                                    <div>
                                        <p className="text-[10px] font-bold text-red-500 uppercase">You said</p>
                                        <p className="text-slate-600 text-sm italic">"{alt.original}"</p>
                                    </div>
                                </div>
                                <div className="flex items-start space-x-2">
                                    <span className="text-emerald-500 text-xs font-bold mt-0.5">✓</span>
                                    <div>
                                        <p className="text-[10px] font-bold text-emerald-600 uppercase">Try instead</p>
                                        <p className="text-slate-700 text-sm font-medium">"{alt.suggested}"</p>
                                        {alt.reasoning && (
                                            <p className="text-slate-500 text-xs mt-1">{alt.reasoning}</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
