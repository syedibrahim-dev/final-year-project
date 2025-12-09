import React, { useState, useEffect } from 'react';
import { mcq as mcqApi, conceptMap as conceptMapApi } from '../utils/api';
import { Sparkles, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '../App';

export default function MCQGenerator({ orgId, token }) {
    const [topic, setTopic] = useState('');
    const [numQuestions, setNumQuestions] = useState(5);
    const [difficulty, setDifficulty] = useState('medium');
    const [conceptId, setConceptId] = useState(''); // ✅ NEW
    const [stage, setStage] = useState(''); // ✅ NEW
    const [concepts, setConcepts] = useState([]); // ✅ NEW
    const [stages, setStages] = useState([]); // ✅ NEW
    const [generating, setGenerating] = useState(false);
    const [questions, setQuestions] = useState([]);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    // ✅ Fetch concepts on mount
    useEffect(() => {
        fetchConcepts();
    }, [orgId, token]);

    const fetchConcepts = async () => {
        try {
            const allConcepts = await conceptMapApi.listConcepts(orgId, null, token);
            setConcepts(allConcepts);
            
            // Extract sales stages
            const stageNodes = allConcepts.filter(c => c.node_type === 'sales_stage');
            setStages(stageNodes);
        } catch (err) {
            console.error('Failed to fetch concepts:', err);
        }
    };

    const handleGenerate = async () => {
        if (!topic.trim()) {
            setError('Please enter a topic');
            return;
        }

        setGenerating(true);
        setError('');
        setSuccess('');
        setQuestions([]);

        try {
            const result = await mcqApi.generate(orgId, {
                topic,
                num_questions: numQuestions,
                difficulty,
                concept_id: conceptId || undefined, // ✅ NEW
                stage: stage || undefined // ✅ NEW
            }, token);

            setQuestions(result.questions);
            setSuccess(`Generated ${result.questions.length} high-quality questions!`);
        } catch (err) {
            setError(err.message || 'Failed to generate MCQs');
        } finally {
            setGenerating(false);
        }
    };

    const handleCreateTest = async () => {
        if (questions.length === 0) {
            setError('Generate questions first');
            return;
        }

        try {
            await mcqApi.createTest(orgId, {
                title: `${topic} - ${difficulty}`,
                description: `MCQ test on ${topic}`,
                topic,
                difficulty,
                num_questions: questions.length,
                concept_id: conceptId || undefined,
                stage: stage || undefined
            }, token);

            setSuccess('Test created successfully!');
            setQuestions([]);
            setTopic('');
        } catch (err) {
            setError(err.message || 'Failed to create test');
        }
    };

    return (
        <div className="space-y-6">
            <div className="border-b pb-4">
                <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                    <Sparkles className="mr-2 text-indigo-600" size={28} />
                    MCQ Generator (AI-Powered)
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                    Generate scenario-based questions with concept map integration & quality evaluation
                </p>
            </div>

            {/* Configuration Form */}
            <div className="bg-white border rounded-lg p-6">
                <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2">
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Topic *
                        </label>
                        <input
                            type="text"
                            value={topic}
                            onChange={(e) => setTopic(e.target.value)}
                            placeholder="e.g., Handling budget objections"
                            className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>

                    {/* ✅ NEW: Concept Selection */}
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Target Concept (Optional)
                        </label>
                        <select
                            value={conceptId}
                            onChange={(e) => setConceptId(e.target.value)}
                            className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                        >
                            <option value="">All Concepts</option>
                            {concepts.map(c => (
                                <option key={c.node_id} value={c.node_id}>
                                    {c.name} ({c.node_type})
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* ✅ NEW: Sales Stage Selection */}
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Sales Stage (Optional)
                        </label>
                        <select
                            value={stage}
                            onChange={(e) => setStage(e.target.value)}
                            className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                        >
                            <option value="">All Stages</option>
                            {stages.map(s => (
                                <option key={s.node_id} value={s.node_id}>
                                    {s.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Number of Questions
                        </label>
                        <input
                            type="number"
                            min="1"
                            max="20"
                            value={numQuestions}
                            onChange={(e) => setNumQuestions(parseInt(e.target.value))}
                            className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Difficulty
                        </label>
                        <select
                            value={difficulty}
                            onChange={(e) => setDifficulty(e.target.value)}
                            className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                        >
                            <option value="easy">Easy</option>
                            <option value="medium">Medium</option>
                            <option value="hard">Hard</option>
                        </select>
                    </div>
                </div>

                {error && (
                    <div className="mt-4 flex items-center p-3 bg-red-50 border border-red-200 rounded-lg text-red-800">
                        <AlertCircle size={20} className="mr-2" />
                        {error}
                    </div>
                )}

                {success && (
                    <div className="mt-4 flex items-center p-3 bg-green-50 border border-green-200 rounded-lg text-green-800">
                        <CheckCircle size={20} className="mr-2" />
                        {success}
                    </div>
                )}

                <Button
                    onClick={handleGenerate}
                    disabled={generating}
                    loading={generating}
                    className="w-full mt-4 bg-indigo-600 hover:bg-indigo-700"
                >
                    {generating ? (
                        <>
                            <Loader2 className="animate-spin mr-2" size={18} />
                            Generating with AI...
                        </>
                    ) : (
                        <>
                            <Sparkles className="mr-2" size={18} />
                            Generate MCQs
                        </>
                    )}
                </Button>
            </div>

            {/* Generated Questions */}
            {questions.length > 0 && (
                <div className="bg-white border rounded-lg p-6">
                    <div className="flex justify-between items-center mb-4">
                        <h4 className="text-lg font-semibold text-gray-800">
                            Generated Questions ({questions.length})
                        </h4>
                        <Button
                            onClick={handleCreateTest}
                            className="bg-green-600 hover:bg-green-700"
                        >
                            Create Test
                        </Button>
                    </div>

                    <div className="space-y-6">
                        {questions.map((q, idx) => (
                            <div key={idx} className="p-4 border rounded-lg bg-gray-50">
                                <p className="font-semibold text-gray-800 mb-3">
                                    {idx + 1}. {q.question}
                                </p>
                                <div className="space-y-2">
                                    {q.options.map((opt, optIdx) => (
                                        <div
                                            key={optIdx}
                                            className={`p-3 rounded-lg ${
                                                opt.is_correct
                                                    ? 'bg-green-100 border-green-500 border-2'
                                                    : 'bg-white border'
                                            }`}
                                        >
                                            <p className="text-sm font-medium text-gray-800">
                                                {String.fromCharCode(65 + optIdx)}. {opt.text}
                                                {opt.is_correct && (
                                                    <span className="ml-2 text-green-600 font-bold">✓ Correct</span>
                                                )}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                                <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                                    <p className="text-sm text-blue-900">
                                        <strong>Explanation:</strong> {q.explanation}
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}