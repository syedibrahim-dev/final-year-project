import React, { useState, useEffect, useRef } from 'react';
import { BarChart2, TrendingDown, Users, Trophy, Clock, CheckCircle, XCircle, Award } from 'lucide-react';
import * as d3 from 'd3';
import { mcq as mcqApi } from '../utils/api';
import { Button } from '../App';

export default function PerformanceDashboard({ orgId, token }) {
    const [tests, setTests] = useState([]);
    const [selectedTest, setSelectedTest] = useState(null);
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    
    const scoreDistributionRef = useRef(null);
    const progressChartRef = useRef(null);
    const timeChartRef = useRef(null);

    useEffect(() => {
        fetchTests();
    }, []);

    useEffect(() => {
        if (results.length > 0) {
            createScoreDistributionChart();
            createProgressChart();
            createTimeAnalysisChart();
        }
    }, [results]);

    const fetchTests = async () => {
        setLoading(true);
        try {
            // ✅ FIXED: Extract tests array from response
            const response = await mcqApi.listTests(orgId, token);
            const testsList = response.tests || [];
            
            setTests(testsList);
            if (testsList.length > 0) {
                setSelectedTest(testsList[0].id);
                fetchTestResults(testsList[0].id);
            }
        } catch (err) {
            setError(`Error loading tests: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const fetchTestResults = async (testId) => {
        setLoading(true);
        setError('');
        try {
            // ✅ FIXED: API returns array directly
            const data = await mcqApi.listAttempts(orgId, testId, token);
            setResults(Array.isArray(data) ? data : []);
        } catch (err) {
            setError(`Error loading results: ${err.message}`);
            setResults([]);
        } finally {
            setLoading(false);
        }
    };

    const handleTestChange = (testId) => {
        setSelectedTest(testId);
        fetchTestResults(testId);
    };

    const createScoreDistributionChart = () => {
        const container = scoreDistributionRef.current;
        if (!container || results.length === 0) return;

        d3.select(container).selectAll("*").remove();

        const margin = { top: 20, right: 30, bottom: 40, left: 50 };
        const width = container.offsetWidth - margin.left - margin.right;
        const height = 300 - margin.top - margin.bottom;

        const ranges = [
            { range: '0-20', min: 0, max: 20, color: '#ef4444' },
            { range: '20-40', min: 20, max: 40, color: '#f97316' },
            { range: '40-60', min: 40, max: 60, color: '#eab308' },
            { range: '60-80', min: 60, max: 80, color: '#84cc16' },
            { range: '80-100', min: 80, max: 100, color: '#22c55e' }
        ];

        const distribution = ranges.map(r => ({
            ...r,
            count: results.filter(res => res.score >= r.min && res.score < r.max).length
        }));

        const svg = d3.select(container)
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        const x = d3.scaleBand()
            .domain(distribution.map(d => d.range))
            .range([0, width])
            .padding(0.2);

        const y = d3.scaleLinear()
            .domain([0, d3.max(distribution, d => d.count) || 1])
            .nice()
            .range([height, 0]);

        svg.selectAll(".bar")
            .data(distribution)
            .enter()
            .append("rect")
            .attr("class", "bar")
            .attr("x", d => x(d.range))
            .attr("width", x.bandwidth())
            .attr("y", height)
            .attr("height", 0)
            .attr("fill", d => d.color)
            .attr("rx", 4)
            .transition()
            .duration(800)
            .delay((d, i) => i * 100)
            .attr("y", d => y(d.count))
            .attr("height", d => height - y(d.count));

        svg.selectAll(".label")
            .data(distribution)
            .enter()
            .append("text")
            .attr("class", "label")
            .attr("x", d => x(d.range) + x.bandwidth() / 2)
            .attr("y", d => y(d.count) - 5)
            .attr("text-anchor", "middle")
            .attr("font-size", "12px")
            .attr("font-weight", "bold")
            .attr("fill", "#374151")
            .style("opacity", 0)
            .text(d => d.count)
            .transition()
            .duration(800)
            .delay((d, i) => i * 100 + 400)
            .style("opacity", 1);

        svg.append("g")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x));

        svg.append("g")
            .call(d3.axisLeft(y).ticks(5));

        svg.append("text")
            .attr("x", width / 2)
            .attr("y", -5)
            .attr("text-anchor", "middle")
            .attr("font-size", "14px")
            .attr("font-weight", "bold")
            .text("Score Distribution");
    };

    const createProgressChart = () => {
        const container = progressChartRef.current;
        if (!container || results.length === 0) return;

        d3.select(container).selectAll("*").remove();

        const margin = { top: 20, right: 30, bottom: 40, left: 50 };
        const width = container.offsetWidth - margin.left - margin.right;
        const height = 300 - margin.top - margin.bottom;

        const sortedResults = [...results].sort((a, b) => 
            new Date(a.completed_at) - new Date(b.completed_at)
        );

        const svg = d3.select(container)
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        const x = d3.scalePoint()
            .domain(sortedResults.map((_, i) => i))
            .range([0, width]);

        const y = d3.scaleLinear()
            .domain([0, 100])
            .range([height, 0]);

        const line = d3.line()
            .x((d, i) => x(i))
            .y(d => y(d.score))
            .curve(d3.curveMonotoneX);

        const path = svg.append("path")
            .datum(sortedResults)
            .attr("fill", "none")
            .attr("stroke", "#6366f1")
            .attr("stroke-width", 3)
            .attr("d", line);

        const pathLength = path.node().getTotalLength();
        path.attr("stroke-dasharray", pathLength)
            .attr("stroke-dashoffset", pathLength)
            .transition()
            .duration(2000)
            .attr("stroke-dashoffset", 0);

        svg.selectAll(".dot")
            .data(sortedResults)
            .enter()
            .append("circle")
            .attr("cx", (d, i) => x(i))
            .attr("cy", d => y(d.score))
            .attr("r", 0)
            .attr("fill", d => d.score >= 70 ? "#22c55e" : "#ef4444")
            .attr("stroke", "white")
            .attr("stroke-width", 2)
            .transition()
            .duration(500)
            .delay((d, i) => 2000 + i * 50)
            .attr("r", 5);

        svg.append("g")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x).tickFormat((d, i) => i + 1));

        svg.append("g")
            .call(d3.axisLeft(y).ticks(5));

        svg.append("text")
            .attr("x", width / 2)
            .attr("y", -5)
            .attr("text-anchor", "middle")
            .attr("font-size", "14px")
            .attr("font-weight", "bold")
            .text("Performance Trend");
    };

    const createTimeAnalysisChart = () => {
        const container = timeChartRef.current;
        if (!container || results.length === 0) return;

        d3.select(container).selectAll("*").remove();

        const margin = { top: 20, right: 30, bottom: 60, left: 50 };
        const width = container.offsetWidth - margin.left - margin.right;
        const height = 300 - margin.top - margin.bottom;

        const data = results
            .filter(r => r.time_taken_seconds)
            .map(r => ({
                user: r.user_id,
                time: r.time_taken_seconds / 60,
                score: r.score
            }));

        if (data.length === 0) return;

        const svg = d3.select(container)
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        const x = d3.scaleBand()
            .domain(data.map((d, i) => `User ${i + 1}`))
            .range([0, width])
            .padding(0.3);

        const y = d3.scaleLinear()
            .domain([0, d3.max(data, d => d.time) || 1])
            .nice()
            .range([height, 0]);

        const colorScale = d3.scaleLinear()
            .domain([0, 50, 100])
            .range(["#ef4444", "#eab308", "#22c55e"]);

        svg.selectAll(".bar")
            .data(data)
            .enter()
            .append("rect")
            .attr("x", (d, i) => x(`User ${i + 1}`))
            .attr("width", x.bandwidth())
            .attr("y", height)
            .attr("height", 0)
            .attr("fill", d => colorScale(d.score))
            .attr("rx", 4)
            .transition()
            .duration(800)
            .delay((d, i) => i * 100)
            .attr("y", d => y(d.time))
            .attr("height", d => height - y(d.time));

        svg.append("g")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x))
            .selectAll("text")
            .attr("transform", "rotate(-45)")
            .style("text-anchor", "end");

        svg.append("g")
            .call(d3.axisLeft(y).ticks(5));

        svg.append("text")
            .attr("transform", "rotate(-90)")
            .attr("y", -40)
            .attr("x", -height / 2)
            .attr("text-anchor", "middle")
            .attr("font-size", "12px")
            .text("Time (minutes)");

        svg.append("text")
            .attr("x", width / 2)
            .attr("y", -5)
            .attr("text-anchor", "middle")
            .attr("font-size", "14px")
            .attr("font-weight", "bold")
            .text("Time Analysis");
    };

    const getScoreColor = (score) => {
        if (score >= 80) return 'text-green-600 bg-green-50';
        if (score >= 60) return 'text-yellow-600 bg-yellow-50';
        return 'text-red-600 bg-red-50';
    };

    const getPerformanceBadge = (score) => {
        if (score >= 80) return { text: 'Excellent', color: 'bg-green-500' };
        if (score >= 60) return { text: 'Good', color: 'bg-yellow-500' };
        return { text: 'Needs Improvement', color: 'bg-red-500' };
    };

    const stats = results.length > 0 ? {
        totalAttempts: results.length,
        averageScore: (results.reduce((sum, r) => sum + r.score, 0) / results.length).toFixed(1),
        passedCount: results.filter(r => r.score >= 70).length,
        failedCount: results.filter(r => r.score < 70).length
    } : null;

    if (loading && tests.length === 0) {
        return (
            <div className="flex items-center justify-center p-12">
                <div className="text-gray-600">Loading performance data...</div>
            </div>
        );
    }

    if (tests.length === 0) {
        return (
            <div className="text-center p-12">
                <BarChart2 className="mx-auto h-16 w-16 text-gray-400 mb-4" />
                <h3 className="text-xl font-semibold text-gray-700 mb-2">No MCQ Tests Yet</h3>
                <p className="text-gray-500 mb-6">Create MCQ tests first to track trainee performance.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="border-b pb-4">
                <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                    <BarChart2 className="mr-2 text-indigo-600" size={28} />
                    Trainee Performance Dashboard
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                    Monitor trainee progress and identify areas for improvement
                </p>
            </div>

            {/* Test Selector */}
            <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Select MCQ Test
                </label>
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

            {/* Statistics Cards */}
            {stats && (
                <div className="grid grid-cols-4 gap-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-xs text-gray-600 mb-1">Total Attempts</p>
                                <p className="text-2xl font-bold text-blue-600">{stats.totalAttempts}</p>
                            </div>
                            <Users className="text-blue-400" size={32} />
                        </div>
                    </div>

                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-xs text-gray-600 mb-1">Average Score</p>
                                <p className="text-2xl font-bold text-purple-600">{stats.averageScore}%</p>
                            </div>
                            <TrendingDown className="text-purple-400" size={32} />
                        </div>
                    </div>

                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-xs text-gray-600 mb-1">Passed (≥70%)</p>
                                <p className="text-2xl font-bold text-green-600">{stats.passedCount}</p>
                            </div>
                            <CheckCircle className="text-green-400" size={32} />
                        </div>
                    </div>

                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-xs text-gray-600 mb-1">Failed (&lt;70%)</p>
                                <p className="text-2xl font-bold text-red-600">{stats.failedCount}</p>
                            </div>
                            <XCircle className="text-red-400" size={32} />
                        </div>
                    </div>
                </div>
            )}

            {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
                    {error}
                </div>
            )}

            {/* D3 Visualizations */}
            {results.length > 0 && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div className="bg-white border rounded-lg p-4 shadow-sm">
                        <div ref={scoreDistributionRef} className="w-full"></div>
                    </div>
                    <div className="bg-white border rounded-lg p-4 shadow-sm">
                        <div ref={progressChartRef} className="w-full"></div>
                    </div>
                    <div className="bg-white border rounded-lg p-4 shadow-sm lg:col-span-2">
                        <div ref={timeChartRef} className="w-full"></div>
                    </div>
                </div>
            )}

            {/* Results Table */}
            {results.length === 0 ? (
                <div className="text-center p-12 bg-gray-50 rounded-lg border">
                    <Trophy className="mx-auto h-12 w-12 text-gray-400 mb-3" />
                    <p className="text-gray-600">No attempts yet for this test.</p>
                </div>
            ) : (
                <div className="bg-white border rounded-lg overflow-hidden">
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
                                {results
                                    .sort((a, b) => b.score - a.score)
                                    .map((result, index) => {
                                        const badge = getPerformanceBadge(result.score);
                                        const timeTaken = result.time_taken_seconds 
                                            ? `${Math.floor(result.time_taken_seconds / 60)}m ${result.time_taken_seconds % 60}s`
                                            : 'N/A';
                                        
                                        return (
                                            <tr key={result.id} className="hover:bg-gray-50">
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className="text-sm font-medium text-gray-900">#{index + 1}</span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(result.score)}`}>
                                                        {result.score.toFixed(1)}%
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                    {result.correct_answers} / {result.total_questions}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                    <Clock size={14} className="inline mr-1" />
                                                    {timeTaken}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    <span className={`px-2 py-1 text-xs font-medium rounded-full text-white ${badge.color}`}>
                                                        {badge.text}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                    {new Date(result.completed_at).toLocaleString()}
                                                </td>
                                            </tr>
                                        );
                                    })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}