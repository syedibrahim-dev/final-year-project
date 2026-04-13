import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Loader2, Send, X, User, Bot, Clock, Lightbulb, TrendingUp, TrendingDown, ChevronRight, Heart, AlertTriangle, Shield, CheckCircle, Mic, MicOff, VolumeX, MessageCircle, Activity } from 'lucide-react';
import * as d3 from 'd3';
import { apiFetch } from '../utils/api';
const AnimatedAvatar3D = React.lazy(() => import('../components/AnimatedAvatar3D'));

// ── Stage definitions ──
const STAGES = [
    { key: 'opening', label: 'Opening', icon: '👋' },
    { key: 'discovery', label: 'Discovery', icon: '🔍' },
    { key: 'presentation', label: 'Presenting', icon: '💡' },
    { key: 'objection', label: 'Objections', icon: '🛡️' },
    { key: 'closing', label: 'Closing', icon: '🤝' },
];

// ── Stage Progress Bar ──
function StageProgressBar({ stageInfo }) {
    const currentIdx = stageInfo ? STAGES.findIndex(s => s.key === stageInfo.current_stage) : -1;
    const progressPct = stageInfo?.progress_pct || 0;

    return (
        <div className="px-4 py-1.5 bg-white border-b border-slate-100 flex items-center space-x-3">
            <span className="text-[10px] font-semibold text-slate-400 whitespace-nowrap">{progressPct}%</span>
            <div className="flex items-center flex-1 justify-between">
                {STAGES.map((stage, idx) => {
                    const isActive = idx === currentIdx;
                    const isPast = idx < currentIdx;
                    return (
                        <div key={stage.key} className="flex items-center">
                            <div className="flex flex-col items-center">
                                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] transition-all duration-300 ${isActive
                                    ? 'bg-indigo-600 text-white ring-1 ring-indigo-200 scale-110'
                                    : isPast ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-400'
                                }`}>{stage.icon}</div>
                                <span className={`text-[8px] mt-0.5 font-semibold ${isActive ? 'text-indigo-600' : isPast ? 'text-emerald-600' : 'text-slate-400'}`}>
                                    {stage.label}
                                </span>
                            </div>
                            {idx < STAGES.length - 1 && <div className={`w-4 h-px mx-0.5 ${isPast ? 'bg-emerald-300' : 'bg-slate-200'}`} />}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ── Coaching Hint ──
function CoachingHintPanel({ hint }) {
    return (
        <div className={`mx-3 mt-1.5 px-3 py-1.5 rounded-lg flex items-center space-x-2 transition-all duration-500 ${hint ? 'bg-amber-50 border border-amber-200' : 'bg-slate-50 border border-slate-100'}`}>
            <Lightbulb size={11} className={hint ? 'text-amber-500' : 'text-slate-300'} />
            <p className={`text-[10px] leading-snug truncate ${hint ? 'text-amber-700' : 'text-slate-300 italic'}`}>
                {hint || 'Coaching tips will appear here...'}
            </p>
        </div>
    );
}

// ── EQ Badge (Transformer-powered) ──
function EQBadge({ eqData }) {
    if (!eqData) return null;

    const empathy = eqData.empathy_score ?? 0.5;
    const pressure = eqData.pressure_level || 'consultative';
    const score = eqData.eq_score ?? 50;

    // Determine badge style from empathy + pressure
    let config;
    if (pressure === 'demanding') {
        config = { color: 'text-red-600 bg-red-50 border-red-200', icon: <AlertTriangle size={10} />, label: 'Pushy' };
    } else if (empathy >= 0.7) {
        config = { color: 'text-emerald-600 bg-emerald-50 border-emerald-200', icon: <Heart size={10} />, label: 'Empathetic' };
    } else if (empathy < 0.35) {
        config = { color: 'text-orange-600 bg-orange-50 border-orange-200', icon: <AlertTriangle size={10} />, label: 'Low Empathy' };
    } else {
        config = { color: 'text-slate-500 bg-slate-50 border-slate-200', icon: <Shield size={10} />, label: 'Neutral' };
    }

    return (
        <div className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${config.color} animate-fadeIn`}>
            {config.icon}
            <span>{config.label}</span>
            <span className="opacity-60">• EQ {score?.toFixed(0)}</span>
        </div>
    );
}

// ── Accuracy Warning ──
function AccuracyWarning({ accuracyData }) {
    const hasWarning = accuracyData?.accuracy_flag === 'unverified';

    return (
        <div className={`mx-3 mt-1 px-3 py-1 rounded-lg flex items-center space-x-2 transition-all duration-500 ${hasWarning ? 'bg-red-50 border border-red-200' : 'bg-emerald-50/50 border border-emerald-100'}`}>
            {hasWarning ? (
                <>
                    <AlertTriangle size={11} className="text-red-500 flex-shrink-0" />
                    <p className="text-[10px] text-red-600 truncate">
                        Unverified: {accuracyData.flagged_claims?.[0]?.claim?.substring(0, 60)}...
                    </p>
                </>
            ) : (
                <>
                    <CheckCircle size={11} className="text-emerald-400 flex-shrink-0" />
                    <p className="text-[10px] text-emerald-500">All claims verified</p>
                </>
            )}
        </div>
    );
}

// ── Deal Intelligence Card (complementary signals) ──
function DealIntelligenceCard({ dealIntelligence, lstmRisk }) {
    const dc = dealIntelligence?.deal_confidence;
    const cm = dealIntelligence?.conversation_momentum;
    const bs = dealIntelligence?.buyer_state;
    const bw = dealIntelligence?.buyer_willingness;
    const cr = lstmRisk || dealIntelligence?.conversation_risk;

    const getColor = (prob) => {
        if (prob >= 0.7) return { ring: 'ring-emerald-300', text: 'text-emerald-600', bg: 'from-emerald-500 to-teal-500', label: 'Strong' };
        if (prob >= 0.45) return { ring: 'ring-amber-300', text: 'text-amber-600', bg: 'from-amber-400 to-yellow-500', label: 'Mixed' };
        return { ring: 'ring-rose-300', text: 'text-rose-600', bg: 'from-rose-500 to-red-500', label: 'Weak' };
    };

    const stateEmoji = {
        interest: '🔍', trust: '🤝', objection: '🛡️', evaluation: '⚖️',
        comparison: '📊', decision: '✅', drop_off_risk: '⚠️', neutral: '😐',
    };
    const willEmoji = { engaged: '🟢', neutral: '🟡', disengaged: '🔴' };

    return (
        <div className="px-3 py-1.5 bg-white border-b border-slate-100">
            {/* Compact: 4 metrics in a single row */}
            <div className="flex items-center space-x-3">
                {/* Deal Confidence */}
                <div className="flex items-center space-x-1.5">
                    <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${dc ? getColor(dc.probability).bg : 'from-slate-200 to-slate-300'} flex items-center justify-center shadow-sm`}>
                        <span className="text-white font-bold text-[10px]">{dc ? Math.round(dc.probability * 100) : '--'}%</span>
                    </div>
                    <div>
                        <p className="text-[9px] font-bold text-slate-500 leading-none">Deal</p>
                        <p className={`text-[9px] ${dc?.label === 'converted' ? 'text-emerald-500' : dc ? 'text-rose-500' : 'text-slate-300'}`}>
                            {dc ? (dc.label === 'converted' ? '↑ likely' : '↓ unlikely') : 'awaiting'}
                        </p>
                    </div>
                </div>

                <div className="h-6 w-px bg-slate-200" />

                {/* Momentum */}
                <div className="flex items-center space-x-1.5">
                    <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${cm ? 'from-violet-500 to-purple-500' : 'from-slate-200 to-slate-300'} flex items-center justify-center shadow-sm`}>
                        <span className="text-white font-bold text-[10px]">{cm ? Math.round(cm.probability * 100) : '--'}%</span>
                    </div>
                    <div>
                        <p className="text-[9px] font-bold text-slate-500 leading-none">Momentum</p>
                        <p className={`text-[9px] flex items-center space-x-0.5 ${cm?.trend === 'improving' ? 'text-emerald-500' : cm?.trend === 'declining' ? 'text-rose-500' : 'text-slate-300'}`}>
                            {cm ? <>{cm.trend === 'improving' ? <TrendingUp size={8} /> : cm.trend === 'declining' ? <TrendingDown size={8} /> : <Activity size={8} />}<span>{cm.trend}</span></> : 'awaiting'}
                        </p>
                    </div>
                </div>

                <div className="h-6 w-px bg-slate-200" />

                {/* Buyer State */}
                <div className="flex items-center space-x-1 text-[10px]">
                    <span>{bs ? (stateEmoji[bs.state] || '❓') : '🔘'}</span>
                    <div>
                        <p className="text-[9px] font-bold text-slate-500 leading-none">State</p>
                        <p className={`text-[9px] capitalize ${bs ? 'text-slate-700' : 'text-slate-300'}`}>
                            {bs ? bs.state?.replace('_', ' ') : 'awaiting'}
                        </p>
                    </div>
                </div>

                <div className="h-6 w-px bg-slate-200" />

                {/* Willingness */}
                <div className="flex items-center space-x-1 text-[10px]">
                    <span>{bw ? (willEmoji[bw.level] || '❓') : '🔘'}</span>
                    <div>
                        <p className="text-[9px] font-bold text-slate-500 leading-none">Willingness</p>
                        <p className={`text-[9px] capitalize ${bw ? 'text-slate-700' : 'text-slate-300'}`}>
                            {bw ? bw.level : 'awaiting'}
                        </p>
                    </div>
                </div>

                <div className="h-6 w-px bg-slate-200" />

                {/* LSTM Risk */}
                <div className="flex items-center space-x-1.5">
                    <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${cr ? (cr.risk_label === 'low' ? 'from-emerald-500 to-teal-500' : cr.risk_label === 'medium' ? 'from-amber-400 to-yellow-500' : 'from-rose-500 to-red-500') : 'from-slate-200 to-slate-300'} flex items-center justify-center shadow-sm`}>
                        <span className="text-white font-bold text-[10px]">{cr ? Math.round(cr.risk_score * 100) : '--'}%</span>
                    </div>
                    <div>
                        <p className="text-[9px] font-bold text-slate-500 leading-none">Risk</p>
                        <p className={`text-[9px] flex items-center space-x-0.5 ${cr?.trend === 'falling' ? 'text-emerald-500' : cr?.trend === 'rising' ? 'text-rose-500' : cr ? 'text-slate-500' : 'text-slate-300'}`}>
                            {cr ? <>{cr.trend === 'rising' ? <TrendingUp size={8} /> : cr.trend === 'falling' ? <TrendingDown size={8} /> : <Activity size={8} />}<span>{cr.risk_label}</span></> : 'awaiting'}
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

// ── Conversion Probability Gauge ──
function ConversionGauge({ conversionData }) {
    const hasData = conversionData && !conversionData.model_not_loaded;
    const prob = hasData ? Math.round((conversionData?.probability || 0.5) * 100) : 50;
    const conf = Math.round((conversionData?.confidence || 0) * 100);
    const trend = conversionData?.trend || 'stable';
    const momentum = conversionData?.momentum || 0;
    const turningPoints = conversionData?.turning_points || [];
    const latestTP = turningPoints.length > 0 ? turningPoints[turningPoints.length - 1] : null;

    // Color based on probability
    const getColor = (p) => {
        if (p >= 70) return { bg: 'from-emerald-500 to-teal-500', text: 'text-emerald-600', bar: 'bg-emerald-500', label: 'High' };
        if (p >= 45) return { bg: 'from-amber-400 to-yellow-500', text: 'text-amber-600', bar: 'bg-amber-400', label: 'Medium' };
        return { bg: 'from-rose-500 to-red-500', text: 'text-rose-600', bar: 'bg-rose-500', label: 'Low' };
    };
    const color = getColor(prob);

    const trendConfig = {
        improving: { icon: <TrendingUp size={11} />, color: 'text-emerald-500', label: 'Improving' },
        declining: { icon: <TrendingDown size={11} />, color: 'text-rose-500', label: 'Declining' },
        stable: { icon: <Activity size={11} />, color: 'text-slate-400', label: 'Stable' },
        neutral: { icon: <Activity size={11} />, color: 'text-slate-400', label: 'Neutral' },
    };
    const trendCfg = trendConfig[trend] || trendConfig.stable;

    return (
        <div className="px-3 py-1 bg-white border-b border-slate-100">
            <div className="flex items-center space-x-2">
                <span className="text-[9px] font-bold text-slate-400 whitespace-nowrap">SalesRL</span>
                <div className="flex-1 bg-slate-100 rounded-full h-1.5">
                    <div className={`${color.bar} h-1.5 rounded-full transition-all duration-700 ease-out`}
                        style={{ width: `${Math.min(prob, 100)}%` }} />
                </div>
                <span className={`text-[10px] font-bold ${color.text}`}>{prob}%</span>
                <span className={`flex items-center space-x-0.5 text-[9px] font-semibold ${trendCfg.color}`}>
                    {trendCfg.icon}<span>{trendCfg.label}</span>
                </span>
                {latestTP && (
                    <span className={`text-[9px] font-semibold ${latestTP.direction === 'positive' ? 'text-emerald-500' : 'text-rose-500'}`}>
                        {latestTP.direction === 'positive' ? '↑' : '↓'}{Math.abs(Math.round(latestTP.delta * 100))}%
                    </span>
                )}
            </div>
        </div>
    );
}

// ── Live Conversion Trend Chart (D3) ──
function ConversionTrendChart({ history }) {
    const svgRef = useRef(null);

    useEffect(() => {
        if (!history || history.length < 2 || !svgRef.current) return;

        const container = svgRef.current.parentElement;
        const width = container.clientWidth;
        const height = 60;
        const margin = { top: 12, right: 16, bottom: 20, left: 32 };
        const inner = { w: width - margin.left - margin.right, h: height - margin.top - margin.bottom };

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();
        svg.attr('width', width).attr('height', height);

        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear().domain([1, Math.max(history.length, 3)]).range([0, inner.w]);
        const y = d3.scaleLinear().domain([0, 1]).range([inner.h, 0]);

        // Zone backgrounds
        const zones = [
            { y0: 0, y1: 0.3, color: '#fef2f2' },
            { y0: 0.3, y1: 0.6, color: '#fffbeb' },
            { y0: 0.6, y1: 1.0, color: '#f0fdf4' },
        ];
        zones.forEach(z => {
            g.append('rect')
                .attr('x', 0).attr('width', inner.w)
                .attr('y', y(z.y1)).attr('height', y(z.y0) - y(z.y1))
                .attr('fill', z.color).attr('opacity', 0.7);
        });

        // Zone labels
        g.append('text').attr('x', inner.w - 4).attr('y', y(0.8)).attr('text-anchor', 'end')
            .attr('font-size', '8px').attr('fill', '#86efac').text('High');
        g.append('text').attr('x', inner.w - 4).attr('y', y(0.45)).attr('text-anchor', 'end')
            .attr('font-size', '8px').attr('fill', '#fcd34d').text('Medium');
        g.append('text').attr('x', inner.w - 4).attr('y', y(0.12)).attr('text-anchor', 'end')
            .attr('font-size', '8px').attr('fill', '#fca5a5').text('Low');

        // Grid lines
        [0.3, 0.6].forEach(v => {
            g.append('line')
                .attr('x1', 0).attr('x2', inner.w)
                .attr('y1', y(v)).attr('y2', y(v))
                .attr('stroke', '#e2e8f0').attr('stroke-dasharray', '3,3');
        });

        // Area fill
        const area = d3.area()
            .x((d, i) => x(i + 1)).y0(inner.h).y1(d => y(d))
            .curve(d3.curveMonotoneX);

        const gradient = svg.append('defs').append('linearGradient')
            .attr('id', 'areaGrad').attr('x1', '0').attr('y1', '0').attr('x2', '0').attr('y2', '1');
        gradient.append('stop').attr('offset', '0%').attr('stop-color', '#6366f1').attr('stop-opacity', 0.3);
        gradient.append('stop').attr('offset', '100%').attr('stop-color', '#6366f1').attr('stop-opacity', 0.02);

        g.append('path').datum(history).attr('d', area)
            .attr('fill', 'url(#areaGrad)');

        // Line
        const line = d3.line().x((d, i) => x(i + 1)).y(d => y(d)).curve(d3.curveMonotoneX);
        g.append('path').datum(history).attr('d', line)
            .attr('fill', 'none').attr('stroke', '#6366f1').attr('stroke-width', 2.5)
            .attr('stroke-linecap', 'round');

        // Data points
        history.forEach((prob, i) => {
            const cx = x(i + 1), cy = y(prob);
            const color = prob >= 0.6 ? '#10b981' : prob >= 0.3 ? '#f59e0b' : '#ef4444';

            g.append('circle').attr('cx', cx).attr('cy', cy).attr('r', 4)
                .attr('fill', 'white').attr('stroke', color).attr('stroke-width', 2);

            // Tooltip-style label on each point
            g.append('text').attr('x', cx).attr('y', cy - 8)
                .attr('text-anchor', 'middle').attr('font-size', '9px')
                .attr('font-weight', '700').attr('fill', '#475569')
                .text(`${Math.round(prob * 100)}%`);

            // Turning point arrow between consecutive points
            if (i > 0) {
                const delta = prob - history[i - 1];
                if (Math.abs(delta) > 0.08) {
                    const midX = (x(i) + cx) / 2;
                    const midY = (y(history[i - 1]) + cy) / 2;
                    g.append('text').attr('x', midX).attr('y', midY + 3)
                        .attr('text-anchor', 'middle').attr('font-size', '10px')
                        .attr('font-weight', '700')
                        .attr('fill', delta > 0 ? '#10b981' : '#ef4444')
                        .text(delta > 0 ? '▲' : '▼');
                }
            }
        });

        // X axis labels
        history.forEach((_, i) => {
            g.append('text').attr('x', x(i + 1)).attr('y', inner.h + 14)
                .attr('text-anchor', 'middle').attr('font-size', '9px').attr('fill', '#94a3b8')
                .text(`T${i + 1}`);
        });

        // Y axis
        [0, 0.5, 1].forEach(v => {
            g.append('text').attr('x', -6).attr('y', y(v) + 3)
                .attr('text-anchor', 'end').attr('font-size', '8px').attr('fill', '#94a3b8')
                .text(`${Math.round(v * 100)}%`);
        });

    }, [history]);

    if (!history || history.length < 2) {
        return (
            <div className="px-3 py-1 bg-white border-b border-slate-100 flex items-center space-x-2">
                <span className="text-[9px] font-bold text-slate-300">Trend</span>
                <div className="flex-1 h-6 bg-slate-50 rounded flex items-center justify-center">
                    <p className="text-[9px] text-slate-300 italic">Chart after 2+ messages</p>
                </div>
            </div>
        );
    }

    return (
        <div className="px-3 py-1 bg-white border-b border-slate-100">
            <svg ref={svgRef} className="w-full" />
        </div>
    );
}

// ── Main Chat Component ──
export default function RoleplayChat({ sessionId, token, onEnd, mode = 'text' }) {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [sessionInfo, setSessionInfo] = useState(null);
    const [loadingSession, setLoadingSession] = useState(true);
    const [stageInfo, setStageInfo] = useState(null);
    const [coachingHint, setCoachingHint] = useState(null);
    const [latestEQ, setLatestEQ] = useState(null);
    const [latestAccuracy, setLatestAccuracy] = useState(null);
    const [conversionData, setConversionData] = useState(null);
    const [conversionHistory, setConversionHistory] = useState([]); // probability per turn for trend chart
    const [dealIntelligence, setDealIntelligence] = useState(null);
    const [lstmRisk, setLstmRisk] = useState(null);
    const messagesEndRef = useRef(null);

    // 3 modes: 'chat' (traditional), 'avatar' (face-to-face), 'voice' (conversation + mic)
    // mode prop from RoleplayPersonas is 'text' or 'voice' — map 'text' to 'chat'
    const [activeMode, setActiveMode] = useState(mode === 'voice' ? 'voice' : 'chat');
    const [voiceState, setVoiceState] = useState('idle'); // 'idle' | 'listening' | 'processing' | 'ai-speaking'
    const [interimTranscript, setInterimTranscript] = useState('');
    const [voiceMetrics, setVoiceMetrics] = useState(null);
    const [voiceCoaching, setVoiceCoaching] = useState(null);
    const recognitionRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const ttsAudioRef = useRef(null);   // HTML5 Audio element for Edge TTS playback
    // Cumulative speaking time tracker (for talk-to-listen ratio)
    const voiceTimeRef = useRef({ trainee: 0, ai: 0 });
    const [talkListenRatio, setTalkListenRatio] = useState(null);

    // Show EQ badge only on the latest trainee message
    const isLastTrainee = (msg, index) => {
        if (msg.sender !== 'trainee') return false;
        const laterTrainee = messages.slice(index + 1).some(m => m.sender === 'trainee');
        return !laterTrainee;
    };

    useEffect(() => {
        if (sessionId) { fetchSessionInfo(); fetchMessages(); }
    }, [sessionId]);

    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const fetchSessionInfo = async () => {
        try {
            const data = await apiFetch(`/roleplay/sessions/${sessionId}`, 'GET', null, token);
            setSessionInfo(data);
        } catch (err) { console.error('Failed to load session info:', err); }
    };

    const fetchMessages = async () => {
        try {
            setLoadingSession(true);
            const data = await apiFetch(`/roleplay/sessions/${sessionId}/messages`, 'GET', null, token);
            setMessages(data.messages || []);
        } catch (err) { console.error('Failed to load messages:', err); }
        finally { setLoadingSession(false); }
    };

    const sendMessage = async (e) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userMessage = input.trim();
        setInput('');

        const tempUserMsg = { id: Date.now(), sender: 'trainee', text: userMessage, timestamp: new Date().toISOString() };
        setMessages(prev => [...prev, tempUserMsg]);
        setLoading(true);

        try {
            const response = await apiFetch(`/roleplay/sessions/${sessionId}/message`, 'POST', { message: userMessage }, token);
            const aiMsg = { id: response.ai_message_id, sender: 'ai_customer', text: response.ai_response, timestamp: new Date().toISOString() };
            setMessages(prev => [...prev, aiMsg]);
            if (response.stage_info) setStageInfo(response.stage_info);
            if (response.coaching_hint) setCoachingHint(response.coaching_hint);
            setLatestEQ(response.eq_data || null);
            setLatestAccuracy(response.accuracy_data || null);
            setConversionData(response.conversion_data || null);
            setDealIntelligence(response.deal_intelligence || null);
            setLstmRisk(response.lstm_risk || null);
            // Accumulate conversion history for trend chart
            if (response.conversion_data?.probability != null) {
                setConversionHistory(prev => [...prev, response.conversion_data.probability]);
            }
        } catch (err) {
            alert(`Failed to send message: ${err.message}`);
            setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
        } finally { setLoading(false); }
    };

    const endSession = async () => {
        try {
            const response = await apiFetch(`/roleplay/sessions/${sessionId}/end`, 'POST', null, token);
            onEnd?.(response.nlp_evaluation, sessionId, conversionHistory);
        } catch (err) { alert(`Failed to end session: ${err.message}`); }
    };

    // ── Voice helpers (Whisper backend STT + voice analytics) ─────────

    const startListening = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) audioChunksRef.current.push(event.data);
            };

            mediaRecorder.onstop = () => {
                stream.getTracks().forEach(t => t.stop());
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                sendVoiceMessage(audioBlob);
            };

            mediaRecorderRef.current = mediaRecorder;
            mediaRecorder.start();
            setVoiceState('listening');
            setInterimTranscript('');
        } catch (err) {
            alert('Microphone access denied. Please allow microphone access and try again.');
        }
    };

    const stopListening = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            mediaRecorderRef.current.stop();
        }
        setVoiceState('processing');
    };

    const speakResponse = async (text) => {
        try {
            setVoiceState('ai-speaking');
            const res = await apiFetch('/roleplay/tts', 'POST', { text, voice: 'male' }, token);
            const blob = res instanceof Blob ? res : await res.blob?.() || res;
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            ttsAudioRef.current = audio;
            audio.onloadedmetadata = () => {
                // Track AI speaking time for talk-to-listen ratio
                if (audio.duration && isFinite(audio.duration)) {
                    voiceTimeRef.current.ai += audio.duration;
                    updateTalkListenRatio();
                }
            };
            audio.onended = () => { setVoiceState('idle'); URL.revokeObjectURL(url); };
            audio.onerror = () => { setVoiceState('idle'); URL.revokeObjectURL(url); };
            audio.play();
        } catch (err) {
            console.warn('Edge TTS failed, falling back to browser TTS:', err);
            // Fallback to Web Speech API if Edge TTS is unavailable
            if (window.speechSynthesis) {
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = 'en-US';
                utterance.rate = 0.95;
                utterance.onstart = () => setVoiceState('ai-speaking');
                utterance.onend = () => setVoiceState('idle');
                utterance.onerror = () => setVoiceState('idle');
                window.speechSynthesis.speak(utterance);
            } else {
                setVoiceState('idle');
            }
        }
    };

    const stopSpeaking = () => {
        if (ttsAudioRef.current) {
            ttsAudioRef.current.pause();
            ttsAudioRef.current = null;
        }
        window.speechSynthesis?.cancel();
        setVoiceState('idle');
    };

    const updateTalkListenRatio = () => {
        const { trainee, ai } = voiceTimeRef.current;
        const total = trainee + ai;
        if (total > 0) {
            setTalkListenRatio({
                trainee_pct: Math.round((trainee / total) * 100),
                ai_pct: Math.round((ai / total) * 100),
                trainee_seconds: Math.round(trainee),
                ai_seconds: Math.round(ai),
            });
        }
    };

    const sendVoiceMessage = async (audioBlob) => {
        if (loading) return;
        setVoiceState('processing');
        setInterimTranscript('Transcribing with Whisper...');
        setLoading(true);

        try {
            // Send audio to backend for Whisper transcription + voice analytics
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            const response = await apiFetch(`/roleplay/sessions/${sessionId}/voice-message`, 'POST', formData, token);

            if (!response.success) {
                alert(response.error || 'Transcription failed');
                setVoiceState('idle');
                setInterimTranscript('');
                setLoading(false);
                return;
            }

            const text = response.transcribed_text;
            const tempUserMsg = { id: response.trainee_message_id || Date.now(), sender: 'trainee', text, timestamp: new Date().toISOString() };
            setMessages(prev => [...prev, tempUserMsg]);

            const aiMsg = { id: response.ai_message_id, sender: 'ai_customer', text: response.ai_response, timestamp: new Date().toISOString() };
            setMessages(prev => [...prev, aiMsg]);

            if (response.stage_info) setStageInfo(response.stage_info);
            if (response.coaching_hint) setCoachingHint(response.coaching_hint);
            setLatestEQ(response.eq_data || null);
            setLatestAccuracy(response.accuracy_data || null);
            setConversionData(response.conversion_data || null);
            setDealIntelligence(response.deal_intelligence || null);
            setLstmRisk(response.lstm_risk || null);
            if (response.voice_metrics) {
                setVoiceMetrics(response.voice_metrics);
                // Track trainee speaking duration for talk-to-listen ratio
                if (response.voice_metrics.duration_seconds) {
                    voiceTimeRef.current.trainee += response.voice_metrics.duration_seconds;
                    updateTalkListenRatio();
                }
            }
            if (response.voice_coaching) setVoiceCoaching(response.voice_coaching);
            if (response.conversion_data?.probability != null) {
                setConversionHistory(prev => [...prev, response.conversion_data.probability]);
            }
            setInterimTranscript('');
            speakResponse(response.ai_response);
        } catch (err) {
            alert(`Voice message failed: ${err.message}`);
            setVoiceState('idle');
            setInterimTranscript('');
        } finally {
            setLoading(false);
        }
    };

    if (loadingSession) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <Loader2 className="animate-spin h-10 w-10 text-indigo-500 mx-auto mb-3" />
                    <p className="text-slate-500 font-medium text-sm">Loading conversation...</p>
                </div>
            </div>
        );
    }

    // Shared avatar props
    const avatarEmotion = dealIntelligence?.buyer_state?.state === 'objection' ? 'negative' : (latestEQ?.emotion || 'neutral');
    const avatarState = dealIntelligence?.buyer_state?.state || 'interest';
    const avatarRisk = lstmRisk?.risk_label || (dealIntelligence?.deal_confidence?.probability >= 0.6 ? 'low' : dealIntelligence?.deal_confidence?.probability >= 0.35 ? 'medium' : 'high');
    const avatarDifficulty = sessionInfo?.difficulty || 'intermediate';
    const lastAiMessage = [...messages].reverse().find(m => m.sender === 'ai_customer');
    const lastTraineeMessage = [...messages].reverse().find(m => m.sender === 'trainee');

    // ── Text input form (reused in chat + voice modes) ──
    const TextInput = (
        <form onSubmit={sendMessage} className="px-4 py-3 bg-white border-t border-slate-100">
            <div className="flex items-center space-x-2">
                <input type="text" value={input} onChange={(e) => setInput(e.target.value)}
                    placeholder="Type your message..." disabled={loading}
                    className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all disabled:opacity-50 placeholder:text-slate-400"
                />
                <button type="submit" disabled={loading || !input.trim()}
                    className="p-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl disabled:opacity-40 transition-colors shadow-md">
                    {loading ? <Loader2 className="animate-spin h-5 w-5" /> : <Send size={18} />}
                </button>
            </div>
        </form>
    );

    // ── Chat message list (reused in chat + voice modes) ──
    const MessageList = (
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 bg-slate-50/50">
            {messages.length === 0 && (
                <div className="text-center py-16">
                    <img src="/avatars/customer.png" alt="AI Customer"
                        className="h-20 w-20 rounded-full object-cover mx-auto mb-4 shadow-xl ring-4 ring-violet-100" />
                    <p className="text-slate-600 font-semibold text-base">
                        Meet {sessionInfo?.persona_name || 'your AI Customer'}
                    </p>
                    <p className="text-slate-400 text-sm mt-1">Start the conversation — introduce yourself and begin your pitch</p>
                </div>
            )}
            {messages.map((msg, index) => (
                <ChatMessage key={msg.id || index} message={msg} persona={sessionInfo?.persona_name}
                    eqData={isLastTrainee(msg, index) ? latestEQ : null} />
            ))}
            {loading && (
                <div className="flex items-start space-x-2.5">
                    <div className="relative flex-shrink-0">
                        <img src="/avatars/customer.png" alt="AI" className="w-9 h-9 rounded-full object-cover shadow-sm" />
                        <div className="absolute inset-0 rounded-full border-2 border-violet-400 animate-ping opacity-40" />
                    </div>
                    <div className="bg-white p-3 rounded-2xl rounded-tl-sm shadow-sm border border-slate-100">
                        <div className="flex space-x-1">
                            <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                    </div>
                </div>
            )}
            <div ref={messagesEndRef} />
        </div>
    );

    // ── All analytics panels ──
    const AnalyticsPanels = (
        <>
            <DealIntelligenceCard dealIntelligence={dealIntelligence} lstmRisk={lstmRisk} />
            <ConversionGauge conversionData={conversionData} />
            <ConversionTrendChart history={conversionHistory} />
            <CoachingHintPanel hint={coachingHint} />
            <AccuracyWarning accuracyData={latestAccuracy} />
        </>
    );

    return (
        <div className="flex flex-col h-[calc(100vh-8rem)] -m-6 md:-m-8">
            {/* ═══ Header ═══ */}
            <div className="flex items-center justify-between px-5 py-2.5 bg-white/80 backdrop-blur-sm border-b border-slate-100">
                <div>
                    <h3 className="font-bold text-slate-800 text-sm">{sessionInfo?.persona_name || 'AI Customer'}</h3>
                    <p className="text-[11px] text-slate-400 flex items-center space-x-1">
                        <span className="inline-block w-1.5 h-1.5 bg-emerald-400 rounded-full"></span>
                        <span>Online • {messages.length} messages</span>
                    </p>
                </div>
                <div className="flex items-center space-x-1.5">
                    {/* 3 mode buttons */}
                    {[
                        { key: 'chat', icon: <MessageCircle size={13} />, label: 'Chat' },
                        { key: 'avatar', icon: <User size={13} />, label: 'Avatar' },
                        { key: 'voice', icon: <Mic size={13} />, label: 'Voice' },
                    ].map(m => (
                        <button key={m.key}
                            onClick={() => { stopSpeaking(); setActiveMode(m.key); }}
                            className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${activeMode === m.key
                                ? 'bg-indigo-50 border-indigo-200 text-indigo-600'
                                : 'bg-slate-50 border-slate-200 text-slate-400 hover:text-slate-600 hover:bg-slate-100'
                            }`}
                        >
                            {m.icon}<span>{m.label}</span>
                        </button>
                    ))}
                    <button onClick={endSession}
                        className="flex items-center space-x-1 px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg text-xs font-semibold border border-red-200 ml-1">
                        <X size={13} /><span>End</span>
                    </button>
                </div>
            </div>

            <StageProgressBar stageInfo={stageInfo} />

            {/* ═══════════════════════════════════════════════════
                MODE 1: CHAT — Traditional chat with all analytics
               ═══════════════════════════════════════════════════ */}
            {activeMode === 'chat' && (
                <>
                    {AnalyticsPanels}
                    {MessageList}
                    {TextInput}
                </>
            )}

            {/* ═══════════════════════════════════════════════════
                MODE 2: AVATAR — Face-to-face, classifiers in avatar
               ═══════════════════════════════════════════════════ */}
            {activeMode === 'avatar' && (
                <>
                    <div className="flex-1 flex flex-col bg-gradient-to-b from-slate-50 to-slate-100 overflow-y-auto">
                        <div className="flex-1 flex flex-col items-center justify-center px-6">
                            {/* 3D Avatar (lazy-loaded — Three.js only fetched when avatar mode is active) */}
                            <div className="mb-4 mt-2">
                                <React.Suspense fallback={
                                    <div className="w-56 h-64 rounded-2xl bg-slate-100 flex items-center justify-center">
                                        <div className="w-8 h-8 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
                                    </div>
                                }>
                                    <AnimatedAvatar3D
                                        isTyping={loading}
                                        isSpeaking={voiceState === 'ai-speaking'}
                                        isListening={voiceState === 'listening'}
                                        emotion={avatarEmotion}
                                        salesState={avatarState}
                                        riskLevel={avatarRisk}
                                        difficulty={avatarDifficulty}
                                    />
                                </React.Suspense>
                            </div>

                            {/* AI Speech Bubble */}
                            {loading ? (
                                <div className="relative bg-white px-5 py-3 rounded-2xl shadow-lg border border-slate-200 max-w-sm mb-4">
                                    <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-white border-l border-t border-slate-200 rotate-45" />
                                    <div className="flex space-x-1.5 justify-center">
                                        <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                        <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                        <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                    </div>
                                </div>
                            ) : lastAiMessage ? (
                                <div className="relative bg-white px-5 py-3.5 rounded-2xl shadow-lg border border-slate-200 max-w-sm mb-4">
                                    <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-white border-l border-t border-slate-200 rotate-45" />
                                    <p className="text-sm text-slate-700 leading-relaxed">{lastAiMessage.text}</p>
                                </div>
                            ) : (
                                <div className="relative bg-white/80 px-5 py-3.5 rounded-2xl shadow-md border border-slate-200 max-w-sm mb-4">
                                    <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-white/80 border-l border-t border-slate-200 rotate-45" />
                                    <p className="text-sm text-slate-400 italic text-center">Start the conversation — introduce yourself</p>
                                </div>
                            )}

                            {/* Your last message */}
                            {lastTraineeMessage && (
                                <div className="self-end mr-4 mb-3 max-w-xs">
                                    <div className="bg-indigo-500 text-white px-4 py-2.5 rounded-2xl rounded-br-sm shadow-md">
                                        <p className="text-sm">{lastTraineeMessage.text}</p>
                                    </div>
                                    <p className="text-[10px] text-slate-400 mt-1 text-right">You</p>
                                </div>
                            )}

                            {messages.length > 2 && (
                                <button onClick={() => setActiveMode('chat')}
                                    className="text-[10px] text-indigo-500 hover:text-indigo-700 font-medium mb-2">
                                    View full conversation ({messages.length} messages)
                                </button>
                            )}
                        </div>
                    </div>
                    {TextInput}
                </>
            )}

            {/* ═══════════════════════════════════════════════════
                MODE 3: VOICE — Chat conversation + mic input
               ═══════════════════════════════════════════════════ */}
            {activeMode === 'voice' && (
                <>
                    {AnalyticsPanels}
                    {MessageList}
                    <VoiceInput
                        voiceState={voiceState} interimTranscript={interimTranscript} loading={loading}
                        onStartListening={startListening} onStopListening={stopListening} onStopSpeaking={stopSpeaking}
                        voiceMetrics={voiceMetrics} voiceCoaching={voiceCoaching} talkListenRatio={talkListenRatio}
                    />
                </>
            )}
        </div>
    );
}

// ── Voice Input Panel ────────────────────────────────────────────────

function VoiceInput({ voiceState, interimTranscript, loading, onStartListening, onStopListening, onStopSpeaking, voiceMetrics, voiceCoaching, talkListenRatio }) {
    const isListening = voiceState === 'listening';
    const isSpeaking = voiceState === 'ai-speaking';
    const isProcessing = voiceState === 'processing' || loading;

    // Pick the most actionable coaching tip to display
    const getCoachingTip = () => {
        if (!voiceCoaching) return null;
        if (voiceMetrics?.filler_ratio >= 0.06) return voiceCoaching.filler_feedback;
        if (voiceMetrics?.pace_variability === 'flat') return voiceCoaching.variability_feedback;
        return voiceCoaching.pace_feedback;
    };

    return (
        <div className="px-4 py-4 bg-white border-t border-slate-100">
            {/* Voice Metrics */}
            {voiceMetrics && voiceMetrics.word_count > 0 && (
                <div className="mb-3 p-2 bg-slate-50 rounded-lg border border-slate-100">
                    <div className="text-[10px] font-semibold text-slate-600 mb-1">Voice Analytics</div>
                    <div className="grid grid-cols-3 gap-2 text-center">
                        <div>
                            <div className={`text-sm font-bold ${voiceMetrics.words_per_minute >= 130 && voiceMetrics.words_per_minute <= 160 ? 'text-emerald-600' : voiceMetrics.words_per_minute < 110 || voiceMetrics.words_per_minute > 180 ? 'text-red-500' : 'text-amber-500'}`}>
                                {Math.round(voiceMetrics.words_per_minute)}
                            </div>
                            <div className="text-[9px] text-slate-400">WPM</div>
                        </div>
                        <div>
                            <div className={`text-sm font-bold ${voiceMetrics.filler_ratio < 0.03 ? 'text-emerald-600' : voiceMetrics.filler_ratio < 0.06 ? 'text-amber-500' : 'text-red-500'}`}>
                                {(voiceMetrics.filler_ratio * 100).toFixed(1)}%
                            </div>
                            <div className="text-[9px] text-slate-400">Fillers</div>
                        </div>
                        <div>
                            <div className={`text-sm font-bold ${voiceMetrics.confidence_avg >= 0.85 ? 'text-emerald-600' : voiceMetrics.confidence_avg >= 0.7 ? 'text-amber-500' : 'text-red-500'}`}>
                                {Math.round(voiceMetrics.confidence_avg * 100)}%
                            </div>
                            <div className="text-[9px] text-slate-400">Clarity</div>
                        </div>
                        <div>
                            <div className="text-sm font-bold text-slate-600">{voiceMetrics.pause_count}</div>
                            <div className="text-[9px] text-slate-400">Pauses</div>
                        </div>
                        <div>
                            <div className={`text-sm font-bold ${voiceMetrics.pace_variability === 'good' ? 'text-emerald-600' : voiceMetrics.pace_variability === 'flat' ? 'text-red-500' : 'text-amber-500'}`}>
                                {voiceMetrics.pace_variability === 'good' ? 'Dynamic' : voiceMetrics.pace_variability === 'flat' ? 'Flat' : voiceMetrics.pace_variability === 'moderate' ? 'Moderate' : '--'}
                            </div>
                            <div className="text-[9px] text-slate-400">Pace Var.</div>
                        </div>
                        {talkListenRatio && (
                            <div>
                                <div className={`text-sm font-bold ${talkListenRatio.trainee_pct >= 35 && talkListenRatio.trainee_pct <= 45 ? 'text-emerald-600' : talkListenRatio.trainee_pct > 55 ? 'text-red-500' : 'text-amber-500'}`}>
                                    {talkListenRatio.trainee_pct}/{talkListenRatio.ai_pct}
                                </div>
                                <div className="text-[9px] text-slate-400">Talk/Listen</div>
                            </div>
                        )}
                    </div>
                    {voiceCoaching && (
                        <div className="mt-2 pt-2 border-t border-slate-100">
                            <p className="text-[10px] text-indigo-600">
                                {getCoachingTip()}
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Status */}
            <div className="text-center mb-3 min-h-[36px] flex flex-col items-center justify-center">
                {!isListening && !isSpeaking && !isProcessing && (
                    <p className="text-xs text-slate-400">Tap the mic to speak</p>
                )}
                {isListening && <p className="text-xs font-semibold text-red-500 animate-pulse">Listening — tap to send</p>}
                {isProcessing && <p className="text-xs text-slate-500">{interimTranscript || 'Processing...'}</p>}
                {isSpeaking && <p className="text-xs font-semibold text-violet-600">AI speaking — tap to stop</p>}
            </div>

            {/* Mic button */}
            <div className="flex justify-center">
                <div className="relative">
                    {isListening && (
                        <div className="absolute inset-0 rounded-full animate-pulse-ring pointer-events-none" />
                    )}
                    <button
                        onClick={isSpeaking ? onStopSpeaking : isListening ? onStopListening : onStartListening}
                        disabled={isProcessing}
                        className={`w-16 h-16 rounded-full flex items-center justify-center shadow-lg transition-all duration-200 relative z-10 disabled:opacity-40 ${
                            isSpeaking ? 'bg-violet-500 hover:bg-violet-600 text-white'
                            : isListening ? 'bg-red-500 hover:bg-red-600 text-white scale-110'
                            : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                        }`}
                    >
                        {isProcessing ? <Loader2 className="animate-spin h-7 w-7" />
                            : isSpeaking ? <VolumeX size={26} />
                            : isListening ? <MicOff size={26} />
                            : <Mic size={26} />
                        }
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Chat Message ─────────────────────────────────────────────────────

function ChatMessage({ message, persona, eqData }) {
    const isTrainee = message.sender === 'trainee';
    const avatarSrc = isTrainee ? '/avatars/trainee.png' : '/avatars/customer.png';
    const avatarAlt = isTrainee ? 'You' : (persona || 'AI Customer');

    return (
        <motion.div
            initial={{ opacity: 0, x: isTrainee ? 30 : -30, y: 8 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
            className={`flex items-end space-x-2.5 ${isTrainee ? 'flex-row-reverse space-x-reverse' : ''}`}
        >
            {/* Avatar */}
            <div className="flex-shrink-0 mb-5">
                <img
                    src={avatarSrc}
                    alt={avatarAlt}
                    className={`w-9 h-9 rounded-full object-cover shadow-md ring-2 ${isTrainee ? 'ring-indigo-200' : 'ring-violet-200'
                        }`}
                />
            </div>

            <div className={`max-w-[70%]`}>
                {/* Sender name */}
                <p className={`text-[10px] font-semibold mb-1 px-1 ${isTrainee ? 'text-right text-indigo-400' : 'text-violet-400'
                    }`}>
                    {isTrainee ? 'You' : (persona || 'AI Customer')}
                </p>

                {/* Message bubble */}
                <div className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed shadow-sm ${isTrainee
                    ? 'bg-gradient-to-br from-indigo-500 to-indigo-600 text-white rounded-br-sm'
                    : 'bg-white text-slate-700 border border-slate-100 rounded-bl-sm'
                    }`}>
                    {message.text}
                </div>

                {/* Timestamp + EQ badge */}
                <div className={`flex items-center space-x-2 mt-1 px-1 ${isTrainee ? 'justify-end' : ''}`}>
                    <p className="text-[10px] text-slate-400 flex items-center space-x-1">
                        <Clock size={9} />
                        <span>{new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </p>
                    {isTrainee && eqData && (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.5 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ type: 'spring', stiffness: 400, damping: 15, delay: 0.3 }}
                        >
                            <EQBadge eqData={eqData} />
                        </motion.div>
                    )}
                </div>
            </div>
        </motion.div>
    );
}
