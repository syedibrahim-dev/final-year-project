import React, { useState, useEffect, useRef } from 'react';
import { BarChart2, TrendingUp, TrendingDown, Users, Clock, CheckCircle, XCircle, Award, Target, Activity, MessageCircle, Zap, Star } from 'lucide-react';
import * as d3 from 'd3';
import { mcq as mcqApi, roleplay as roleplayApi } from '../utils/api';

// ===== Reusable Stat Card Component =====
function StatCard({ icon: Icon, label, value, subtitle, color = 'blue' }) {
    const colors = {
        blue: 'bg-blue-50 border-blue-200 text-blue-600',
        cyan: 'bg-cyan-50 border-cyan-200 text-cyan-600',
        purple: 'bg-purple-50 border-purple-200 text-purple-600',
        green: 'bg-green-50 border-green-200 text-green-600',
        red: 'bg-red-50 border-red-200 text-red-600',
        amber: 'bg-amber-50 border-amber-200 text-amber-600',
        gray: 'bg-gray-50 border-gray-200 text-gray-600',
    };
    const iconColors = {
        blue: 'text-blue-400', cyan: 'text-cyan-400', purple: 'text-purple-400',
        green: 'text-green-400', red: 'text-red-400', amber: 'text-amber-400', gray: 'text-gray-400'
    };
    return (
        <div className={`${colors[color]} border rounded-xl p-4`}>
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs text-gray-600 mb-1">{label}</p>
                    <p className={`text-2xl font-bold ${colors[color].split(' ')[2]}`}>{value}</p>
                    {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
                </div>
                <Icon className={iconColors[color]} size={28} />
            </div>
        </div>
    );
}

export default function PerformanceDashboard({ orgId, token, userId }) {
    // Tab state
    const [activeTab, setActiveTab] = useState('overview');

    // MCQ state
    const [tests, setTests] = useState([]);
    const [selectedTest, setSelectedTest] = useState(null);
    const [results, setResults] = useState([]);

    // Roleplay state
    const [roleplayAnalytics, setRoleplayAnalytics] = useState(null);
    const [sessionHistory, setSessionHistory] = useState([]);

    // Common state
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Chart refs
    const scoreDistributionRef = useRef(null);
    const progressChartRef = useRef(null);
    const roleplayTrendRef = useRef(null);
    const categoryRadarRef = useRef(null);

    useEffect(() => {
        loadAllData();
    }, []);

    useEffect(() => {
        if (activeTab === 'mcq' && results.length > 0) {
            setTimeout(() => {
                createScoreDistributionChart();
                createProgressChart();
            }, 100);
        }
        if (activeTab === 'roleplay' && roleplayAnalytics?.score_trend?.length > 0) {
            setTimeout(() => {
                createRoleplayTrendChart();
                createCategoryRadarChart();
            }, 100);
        }
    }, [activeTab, results, roleplayAnalytics]);

    const loadAllData = async () => {
        setLoading(true);
        try {
            const [mcqData, rpAnalytics, rpSessions] = await Promise.allSettled([
                mcqApi.listTests(orgId, token),
                roleplayApi.getUserAnalytics(token),
                roleplayApi.listSessions(token, 10, 0, 'completed')
            ]);

            if (mcqData.status === 'fulfilled') {
                const testsList = mcqData.value.tests || [];
                setTests(testsList);
                if (testsList.length > 0) {
                    setSelectedTest(testsList[0].id);
                    await fetchTestResults(testsList[0].id);
                }
            }
            if (rpAnalytics.status === 'fulfilled') {
                setRoleplayAnalytics(rpAnalytics.value);
            }
            if (rpSessions.status === 'fulfilled') {
                setSessionHistory(rpSessions.value.sessions || []);
            }
        } catch (err) {
            setError(err.message || 'Failed to load data');
        } finally {
            setLoading(false);
        }
    };

    const fetchTestResults = async (testId) => {
        try {
            const data = await mcqApi.listAttempts(orgId, testId, token);
            setResults(Array.isArray(data) ? data : []);
        } catch (err) {
            setResults([]);
        }
    };

    const handleTestChange = (testId) => {
        setSelectedTest(testId);
        fetchTestResults(testId);
    };

    // ===== D3 Charts =====

    const createScoreDistributionChart = () => {
        const container = scoreDistributionRef.current;
        if (!container || results.length === 0) return;
        d3.select(container).selectAll("*").remove();

        const margin = { top: 20, right: 30, bottom: 40, left: 50 };
        const width = container.offsetWidth - margin.left - margin.right;
        const height = 280 - margin.top - margin.bottom;

        const ranges = [
            { range: '0-20', min: 0, max: 20, color: '#ef4444' },
            { range: '20-40', min: 20, max: 40, color: '#f97316' },
            { range: '40-60', min: 40, max: 60, color: '#eab308' },
            { range: '60-80', min: 60, max: 80, color: '#84cc16' },
            { range: '80-100', min: 80, max: 101, color: '#22c55e' }
        ];
        const distribution = ranges.map(r => ({
            ...r, count: results.filter(res => res.score >= r.min && res.score < r.max).length
        }));

        const svg = d3.select(container).append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g").attr("transform", `translate(${margin.left},${margin.top})`);

        const x = d3.scaleBand().domain(distribution.map(d => d.range)).range([0, width]).padding(0.2);
        const y = d3.scaleLinear().domain([0, d3.max(distribution, d => d.count) || 1]).nice().range([height, 0]);

        svg.selectAll(".bar").data(distribution).enter().append("rect")
            .attr("x", d => x(d.range)).attr("width", x.bandwidth())
            .attr("y", height).attr("height", 0).attr("fill", d => d.color).attr("rx", 6)
            .transition().duration(800).delay((d, i) => i * 100)
            .attr("y", d => y(d.count)).attr("height", d => height - y(d.count));

        svg.selectAll(".label").data(distribution).enter().append("text")
            .attr("x", d => x(d.range) + x.bandwidth() / 2).attr("y", d => y(d.count) - 5)
            .attr("text-anchor", "middle").attr("font-size", "12px").attr("font-weight", "bold")
            .attr("fill", "#374151").text(d => d.count);

        svg.append("g").attr("transform", `translate(0,${height})`).call(d3.axisBottom(x));
        svg.append("g").call(d3.axisLeft(y).ticks(5));
    };

    const createProgressChart = () => {
        const container = progressChartRef.current;
        if (!container || results.length === 0) return;
        d3.select(container).selectAll("*").remove();

        const margin = { top: 20, right: 30, bottom: 40, left: 50 };
        const width = container.offsetWidth - margin.left - margin.right;
        const height = 280 - margin.top - margin.bottom;
        const sortedResults = [...results].sort((a, b) => new Date(a.completed_at) - new Date(b.completed_at));

        const svg = d3.select(container).append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g").attr("transform", `translate(${margin.left},${margin.top})`);

        const x = d3.scalePoint().domain(sortedResults.map((_, i) => i)).range([0, width]);
        const y = d3.scaleLinear().domain([0, 100]).range([height, 0]);

        // Pass line
        svg.append("line").attr("x1", 0).attr("x2", width).attr("y1", y(70)).attr("y2", y(70))
            .attr("stroke", "#22c55e").attr("stroke-dasharray", "5,5").attr("stroke-width", 1).attr("opacity", 0.5);
        svg.append("text").attr("x", width - 5).attr("y", y(70) - 5).attr("text-anchor", "end")
            .attr("font-size", "10px").attr("fill", "#22c55e").text("Pass: 70%");

        const line = d3.line().x((d, i) => x(i)).y(d => y(d.score)).curve(d3.curveMonotoneX);
        const path = svg.append("path").datum(sortedResults).attr("fill", "none")
            .attr("stroke", "#6366f1").attr("stroke-width", 3).attr("d", line);
        const pathLength = path.node().getTotalLength();
        path.attr("stroke-dasharray", pathLength).attr("stroke-dashoffset", pathLength)
            .transition().duration(1500).attr("stroke-dashoffset", 0);

        svg.selectAll(".dot").data(sortedResults).enter().append("circle")
            .attr("cx", (d, i) => x(i)).attr("cy", d => y(d.score)).attr("r", 0)
            .attr("fill", d => d.score >= 70 ? "#22c55e" : "#ef4444")
            .attr("stroke", "white").attr("stroke-width", 2)
            .transition().duration(500).delay((d, i) => 1500 + i * 50).attr("r", 5);

        svg.append("g").attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x).tickFormat((d, i) => `#${i + 1}`));
        svg.append("g").call(d3.axisLeft(y).ticks(5));
    };

    const createRoleplayTrendChart = () => {
        const container = roleplayTrendRef.current;
        if (!container || !roleplayAnalytics?.score_trend?.length) return;
        d3.select(container).selectAll("*").remove();

        const data = roleplayAnalytics.score_trend;
        const margin = { top: 20, right: 30, bottom: 40, left: 50 };
        const width = container.offsetWidth - margin.left - margin.right;
        const height = 280 - margin.top - margin.bottom;

        const svg = d3.select(container).append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g").attr("transform", `translate(${margin.left},${margin.top})`);

        const x = d3.scalePoint().domain(data.map((_, i) => i)).range([0, width]);
        const y = d3.scaleLinear().domain([0, 100]).range([height, 0]);

        // Area gradient
        const defs = svg.append("defs");
        const gradient = defs.append("linearGradient").attr("id", "rp-gradient")
            .attr("x1", "0%").attr("y1", "0%").attr("x2", "0%").attr("y2", "100%");
        gradient.append("stop").attr("offset", "0%").attr("stop-color", "#06b6d4").attr("stop-opacity", 0.3);
        gradient.append("stop").attr("offset", "100%").attr("stop-color", "#06b6d4").attr("stop-opacity", 0.02);

        const area = d3.area().x((d, i) => x(i)).y0(height).y1(d => y(d.score)).curve(d3.curveMonotoneX);
        svg.append("path").datum(data).attr("fill", "url(#rp-gradient)").attr("d", area);

        const line = d3.line().x((d, i) => x(i)).y(d => y(d.score)).curve(d3.curveMonotoneX);
        svg.append("path").datum(data).attr("fill", "none").attr("stroke", "#06b6d4").attr("stroke-width", 3).attr("d", line);

        const diffColors = { beginner: '#22c55e', intermediate: '#eab308', advanced: '#ef4444' };
        svg.selectAll(".dot").data(data).enter().append("circle")
            .attr("cx", (d, i) => x(i)).attr("cy", d => y(d.score)).attr("r", 6)
            .attr("fill", d => diffColors[d.difficulty] || '#6366f1')
            .attr("stroke", "white").attr("stroke-width", 2);

        svg.selectAll(".score-label").data(data).enter().append("text")
            .attr("x", (d, i) => x(i)).attr("y", d => y(d.score) - 12)
            .attr("text-anchor", "middle").attr("font-size", "10px").attr("font-weight", "bold")
            .attr("fill", "#475569").text(d => d.score);

        svg.append("g").attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x).tickFormat((d, i) => data[i]?.persona?.substring(0, 8) || `#${i+1}`))
            .selectAll("text").attr("transform", "rotate(-20)").style("text-anchor", "end");
        svg.append("g").call(d3.axisLeft(y).ticks(5));
    };

    const createCategoryRadarChart = () => {
        const container = categoryRadarRef.current;
        if (!container || !roleplayAnalytics?.category_averages) return;
        d3.select(container).selectAll("*").remove();

        const categories = roleplayAnalytics.category_averages;
        const labels = {
            rapport_building: 'Rapport', needs_discovery: 'Discovery',
            product_presentation: 'Presentation', objection_handling: 'Objection Handling', closing: 'Closing'
        };
        const data = Object.entries(categories).map(([key, val]) => ({ axis: labels[key] || key, value: val / 20 }));

        const width = container.offsetWidth;
        const height = 300;
        const radius = Math.min(width, height) / 2 - 40;
        const levels = 5;
        const angleSlice = (Math.PI * 2) / data.length;

        const svg = d3.select(container).append("svg").attr("width", width).attr("height", height);
        const g = svg.append("g").attr("transform", `translate(${width / 2}, ${height / 2})`);

        for (let level = 1; level <= levels; level++) {
            const r = (radius / levels) * level;
            g.append("circle").attr("r", r).attr("fill", "none").attr("stroke", "#e2e8f0").attr("stroke-width", 1);
            g.append("text").attr("x", 4).attr("y", -r).attr("font-size", "9px").attr("fill", "#94a3b8").text(`${level * 4}`);
        }

        data.forEach((d, i) => {
            const angle = angleSlice * i - Math.PI / 2;
            g.append("line").attr("x1", 0).attr("y1", 0)
                .attr("x2", radius * Math.cos(angle)).attr("y2", radius * Math.sin(angle))
                .attr("stroke", "#cbd5e1").attr("stroke-width", 1);
            g.append("text")
                .attr("x", (radius + 25) * Math.cos(angle)).attr("y", (radius + 25) * Math.sin(angle))
                .attr("text-anchor", "middle").attr("dominant-baseline", "middle")
                .attr("font-size", "11px").attr("font-weight", "bold").attr("fill", "#475569").text(d.axis);
        });

        const radarLine = d3.lineRadial().radius(d => d.value * radius).angle((d, i) => i * angleSlice).curve(d3.curveLinearClosed);
        g.append("path").datum(data).attr("d", radarLine)
            .attr("fill", "#06b6d4").attr("fill-opacity", 0.2).attr("stroke", "#06b6d4").attr("stroke-width", 2);

        data.forEach((d, i) => {
            const angle = angleSlice * i - Math.PI / 2;
            g.append("circle")
                .attr("cx", d.value * radius * Math.cos(angle)).attr("cy", d.value * radius * Math.sin(angle))
                .attr("r", 5).attr("fill", "#06b6d4").attr("stroke", "white").attr("stroke-width", 2);
        });
    };

    // ===== Utility =====
    const getScoreColor = (score) => {
        if (score >= 80) return 'text-green-600 bg-green-50';
        if (score >= 60) return 'text-yellow-600 bg-yellow-50';
        return 'text-red-600 bg-red-50';
    };
    const getPerformanceBadge = (score) => {
        if (score >= 80) return { text: 'Excellent', color: 'bg-green-500' };
        if (score >= 60) return { text: 'Good', color: 'bg-yellow-500' };
        return { text: 'Needs Work', color: 'bg-red-500' };
    };
    const formatDuration = (seconds) => {
        if (!seconds) return 'N/A';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
    };

    const mcqStats = results.length > 0 ? {
        totalAttempts: results.length,
        averageScore: (results.reduce((sum, r) => sum + r.score, 0) / results.length).toFixed(1),
        passedCount: results.filter(r => r.score >= 70).length,
        failedCount: results.filter(r => r.score < 70).length
    } : null;
    const rpStats = roleplayAnalytics || {};

    if (loading) {
        return (
            <div className="flex items-center justify-center p-12">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-indigo-600"></div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="border-b pb-4">
                <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                    <BarChart2 className="mr-2 text-indigo-600" size={28} />
                    Performance Dashboard
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                    Track your progress across MCQ tests and roleplay sessions
                </p>
            </div>

            {/* Tab Navigation */}
            <div className="flex space-x-1 bg-gray-100 rounded-xl p-1">
                {[
                    { id: 'overview', label: 'Overview', icon: Activity },
                    { id: 'mcq', label: 'MCQ Performance', icon: Target },
                    { id: 'roleplay', label: 'Roleplay Performance', icon: MessageCircle },
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex-1 flex items-center justify-center space-x-2 py-2.5 px-4 rounded-lg text-sm font-semibold transition-all ${
                            activeTab === tab.id
                                ? 'bg-white text-indigo-700 shadow-sm'
                                : 'text-gray-500 hover:text-gray-700'
                        }`}
                    >
                        <tab.icon size={16} />
                        <span>{tab.label}</span>
                    </button>
                ))}
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">{error}</div>
            )}

            {/* ===== OVERVIEW TAB ===== */}
            {activeTab === 'overview' && (
                <div className="space-y-6">
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard icon={Target} label="MCQ Avg Score" value={mcqStats ? `${mcqStats.averageScore}%` : 'N/A'} color="blue" />
                        <StatCard icon={MessageCircle} label="Roleplay Avg Score" value={rpStats.average_score != null ? `${rpStats.average_score}` : 'N/A'} subtitle="out of 100" color="cyan" />
                        <StatCard icon={Clock} label="Total Practice Time" value={formatDuration(rpStats.total_practice_time || 0)} color="purple" />
                        <StatCard
                            icon={rpStats.improvement_direction === 'improving' ? TrendingUp : Activity}
                            label="Roleplay Trend"
                            value={rpStats.improvement_direction || 'N/A'}
                            subtitle={rpStats.improvement_velocity ? `${rpStats.improvement_velocity > 0 ? '+' : ''}${rpStats.improvement_velocity} pts` : ''}
                            color={rpStats.improvement_direction === 'improving' ? 'green' : rpStats.improvement_direction === 'declining' ? 'red' : 'gray'}
                        />
                    </div>

                    {rpStats.strongest_category && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="bg-green-50 border border-green-200 rounded-xl p-5">
                                <div className="flex items-center space-x-2 mb-2">
                                    <Star className="text-green-600" size={20} />
                                    <h4 className="font-bold text-green-800">Strongest Skill</h4>
                                </div>
                                <p className="text-green-700 text-lg font-semibold capitalize">{rpStats.strongest_category?.replace(/_/g, ' ')}</p>
                                <p className="text-green-600 text-sm">Avg: {rpStats.category_averages?.[rpStats.strongest_category]}/20</p>
                            </div>
                            <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
                                <div className="flex items-center space-x-2 mb-2">
                                    <Zap className="text-amber-600" size={20} />
                                    <h4 className="font-bold text-amber-800">Focus Area</h4>
                                </div>
                                <p className="text-amber-700 text-lg font-semibold capitalize">{rpStats.weakest_category?.replace(/_/g, ' ')}</p>
                                <p className="text-amber-600 text-sm">Avg: {rpStats.category_averages?.[rpStats.weakest_category]}/20</p>
                            </div>
                        </div>
                    )}

                    {sessionHistory.length > 0 && (
                        <div className="bg-white border rounded-xl overflow-hidden">
                            <div className="px-5 py-4 border-b bg-gray-50">
                                <h4 className="font-bold text-gray-800 flex items-center">
                                    <MessageCircle size={18} className="mr-2 text-cyan-600" />
                                    Recent Roleplay Sessions
                                </h4>
                            </div>
                            <div className="divide-y">
                                {sessionHistory.slice(0, 5).map((session) => (
                                    <div key={session.id} className="px-5 py-3 flex items-center justify-between hover:bg-gray-50">
                                        <div className="flex items-center space-x-3">
                                            <div className={`w-2 h-2 rounded-full ${
                                                session.overall_score >= 70 ? 'bg-green-500' :
                                                session.overall_score >= 50 ? 'bg-yellow-500' : 'bg-red-500'
                                            }`} />
                                            <div>
                                                <p className="text-sm font-semibold text-gray-800">{session.persona_name}</p>
                                                <p className="text-xs text-gray-500">
                                                    {session.persona_difficulty} • {formatDuration(session.duration_seconds)} • {session.total_messages} msgs
                                                </p>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            {session.overall_score != null ? (
                                                <span className={`text-sm font-bold ${
                                                    session.overall_score >= 70 ? 'text-green-600' :
                                                    session.overall_score >= 50 ? 'text-yellow-600' : 'text-red-600'
                                                }`}>{session.overall_score}/100</span>
                                            ) : (
                                                <span className="text-xs text-gray-400">Not evaluated</span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {tests.length === 0 && !roleplayAnalytics?.total_sessions && (
                        <div className="text-center p-12 bg-gray-50 rounded-xl border">
                            <Activity className="mx-auto h-16 w-16 text-gray-400 mb-4" />
                            <h3 className="text-xl font-semibold text-gray-700 mb-2">No Activity Yet</h3>
                            <p className="text-gray-500">Complete MCQ tests or roleplay sessions to see your performance here.</p>
                        </div>
                    )}
                </div>
            )}

            {/* ===== MCQ TAB ===== */}
            {activeTab === 'mcq' && (
                <div className="space-y-6">
                    {tests.length === 0 ? (
                        <div className="text-center p-12">
                            <Target className="mx-auto h-16 w-16 text-gray-400 mb-4" />
                            <h3 className="text-xl font-semibold text-gray-700 mb-2">No MCQ Tests Yet</h3>
                            <p className="text-gray-500">Create MCQ tests to track trainee performance.</p>
                        </div>
                    ) : (
                        <>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Select MCQ Test</label>
                                <select
                                    value={selectedTest || ''}
                                    onChange={(e) => handleTestChange(parseInt(e.target.value))}
                                    className="w-full p-3 border border-gray-300 rounded-lg bg-white focus:ring-indigo-500 focus:border-indigo-500"
                                >
                                    {tests.map(test => (
                                        <option key={test.id} value={test.id}>
                                            {test.title} - {test.topic} ({test.difficulty})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {mcqStats && (
                                <div className="grid grid-cols-4 gap-4">
                                    <StatCard icon={Users} label="Total Attempts" value={mcqStats.totalAttempts} color="blue" />
                                    <StatCard icon={TrendingUp} label="Average Score" value={`${mcqStats.averageScore}%`} color="purple" />
                                    <StatCard icon={CheckCircle} label="Passed (≥70%)" value={mcqStats.passedCount} color="green" />
                                    <StatCard icon={XCircle} label="Failed (<70%)" value={mcqStats.failedCount} color="red" />
                                </div>
                            )}

                            {results.length > 0 && (
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    <div className="bg-white border rounded-xl p-5 shadow-sm">
                                        <h5 className="text-sm font-bold text-gray-600 mb-3">Score Distribution</h5>
                                        <div ref={scoreDistributionRef} className="w-full"></div>
                                    </div>
                                    <div className="bg-white border rounded-xl p-5 shadow-sm">
                                        <h5 className="text-sm font-bold text-gray-600 mb-3">Performance Trend</h5>
                                        <div ref={progressChartRef} className="w-full"></div>
                                    </div>
                                </div>
                            )}

                            {results.length > 0 && (
                                <div className="bg-white border rounded-xl overflow-hidden">
                                    <div className="overflow-x-auto">
                                        <table className="min-w-full divide-y divide-gray-200">
                                            <thead className="bg-gray-50">
                                                <tr>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rank</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Correct/Total</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Completed</th>
                                                </tr>
                                            </thead>
                                            <tbody className="bg-white divide-y divide-gray-200">
                                                {results.sort((a, b) => b.score - a.score).map((result, index) => {
                                                    const badge = getPerformanceBadge(result.score);
                                                    return (
                                                        <tr key={result.id} className="hover:bg-gray-50">
                                                            <td className="px-6 py-4 text-sm font-medium text-gray-900">#{index + 1}</td>
                                                            <td className="px-6 py-4">
                                                                <span className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(result.score)}`}>
                                                                    {result.score.toFixed(1)}%
                                                                </span>
                                                            </td>
                                                            <td className="px-6 py-4 text-sm text-gray-500">{result.correct_answers} / {result.total_questions}</td>
                                                            <td className="px-6 py-4 text-sm text-gray-500">
                                                                <Clock size={14} className="inline mr-1" />{formatDuration(result.time_taken_seconds)}
                                                            </td>
                                                            <td className="px-6 py-4">
                                                                <span className={`px-2 py-1 text-xs font-medium rounded-full text-white ${badge.color}`}>{badge.text}</span>
                                                            </td>
                                                            <td className="px-6 py-4 text-sm text-gray-500">{new Date(result.completed_at).toLocaleString()}</td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* ===== ROLEPLAY TAB ===== */}
            {activeTab === 'roleplay' && (
                <div className="space-y-6">
                    {!roleplayAnalytics || roleplayAnalytics.total_sessions === 0 ? (
                        <div className="text-center p-12">
                            <MessageCircle className="mx-auto h-16 w-16 text-gray-400 mb-4" />
                            <h3 className="text-xl font-semibold text-gray-700 mb-2">No Roleplay Sessions Yet</h3>
                            <p className="text-gray-500">Practice with AI personas to see your sales skill analytics here.</p>
                        </div>
                    ) : (
                        <>
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                <StatCard icon={MessageCircle} label="Total Sessions" value={rpStats.total_sessions} color="cyan" />
                                <StatCard icon={Award} label="Average Score" value={`${rpStats.average_score}/100`} color="purple" />
                                <StatCard icon={Clock} label="Practice Time" value={formatDuration(rpStats.total_practice_time)} color="blue" />
                                <StatCard
                                    icon={rpStats.improvement_direction === 'improving' ? TrendingUp : TrendingDown}
                                    label="Improvement"
                                    value={`${rpStats.improvement_velocity > 0 ? '+' : ''}${rpStats.improvement_velocity} pts`}
                                    color={rpStats.improvement_direction === 'improving' ? 'green' : 'amber'}
                                />
                            </div>

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <div className="bg-white border rounded-xl p-5 shadow-sm">
                                    <h5 className="text-sm font-bold text-gray-600 mb-3">Score Trend Over Sessions</h5>
                                    <div className="flex items-center space-x-4 mb-2 text-xs">
                                        <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-green-500 mr-1"></span>Beginner</span>
                                        <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-yellow-500 mr-1"></span>Intermediate</span>
                                        <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-red-500 mr-1"></span>Advanced</span>
                                    </div>
                                    <div ref={roleplayTrendRef} className="w-full"></div>
                                </div>
                                <div className="bg-white border rounded-xl p-5 shadow-sm">
                                    <h5 className="text-sm font-bold text-gray-600 mb-3">Skill Radar</h5>
                                    <div ref={categoryRadarRef} className="w-full"></div>
                                </div>
                            </div>

                            {rpStats.persona_performance?.length > 0 && (
                                <div className="bg-white border rounded-xl overflow-hidden">
                                    <div className="px-5 py-4 border-b bg-gray-50">
                                        <h4 className="font-bold text-gray-800">Performance by Persona</h4>
                                    </div>
                                    <div className="overflow-x-auto">
                                        <table className="min-w-full divide-y divide-gray-200">
                                            <thead className="bg-gray-50">
                                                <tr>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Persona</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Difficulty</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Attempts</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Avg Score</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Best Score</th>
                                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Latest</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-200">
                                                {rpStats.persona_performance.map((pp, idx) => (
                                                    <tr key={idx} className="hover:bg-gray-50">
                                                        <td className="px-6 py-4 text-sm font-semibold text-gray-800">{pp.persona}</td>
                                                        <td className="px-6 py-4">
                                                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                                                                pp.difficulty === 'beginner' ? 'bg-green-100 text-green-700' :
                                                                pp.difficulty === 'intermediate' ? 'bg-yellow-100 text-yellow-700' :
                                                                'bg-red-100 text-red-700'
                                                            }`}>{pp.difficulty}</span>
                                                        </td>
                                                        <td className="px-6 py-4 text-sm text-gray-600">{pp.attempts}</td>
                                                        <td className="px-6 py-4 text-sm font-bold text-gray-800">{pp.avg_score}</td>
                                                        <td className="px-6 py-4 text-sm text-green-600 font-bold">{pp.best_score}</td>
                                                        <td className="px-6 py-4">
                                                            <span className={`text-sm font-bold ${pp.latest_score >= 70 ? 'text-green-600' : 'text-amber-600'}`}>
                                                                {pp.latest_score}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}

                            {rpStats.category_averages && (
                                <div className="bg-white border rounded-xl p-5">
                                    <h4 className="font-bold text-gray-800 mb-4">Category Averages</h4>
                                    <div className="space-y-3">
                                        {Object.entries(rpStats.category_averages).map(([key, val]) => {
                                            const percentage = (val / 20) * 100;
                                            const isStrong = key === rpStats.strongest_category;
                                            const isWeak = key === rpStats.weakest_category;
                                            return (
                                                <div key={key}>
                                                    <div className="flex justify-between mb-1">
                                                        <span className="text-sm font-semibold text-gray-700 capitalize flex items-center">
                                                            {key.replace(/_/g, ' ')}
                                                            {isStrong && <Star size={14} className="ml-1 text-green-500" />}
                                                            {isWeak && <Zap size={14} className="ml-1 text-amber-500" />}
                                                        </span>
                                                        <span className="text-sm font-bold text-gray-800">{val}/20</span>
                                                    </div>
                                                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                                                        <div className={`h-2.5 rounded-full transition-all ${
                                                            percentage >= 75 ? 'bg-green-500' :
                                                            percentage >= 50 ? 'bg-cyan-500' :
                                                            percentage >= 30 ? 'bg-amber-500' : 'bg-red-500'
                                                        }`} style={{ width: `${percentage}%` }} />
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}