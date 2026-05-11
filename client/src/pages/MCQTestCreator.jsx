import React, { useState } from 'react';
import { FileText, Loader2, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { mcq as mcqApi } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { Button, PageHeader, RelatedLinks } from '../components/ui';

export default function MCQTestCreator() {
    const { token, user } = useAuth();
    const orgId = user?.organization_id;
    const [formData, setFormData] = useState({
        topic: '',
        difficulty: 'medium',
        num_questions: 5
    });
    const [generating, setGenerating] = useState(false);
    const [generatedQuestions, setGeneratedQuestions] = useState(null);
    const [testData, setTestData] = useState({
        title: '',
        description: ''
    });
    const [creating, setCreating] = useState(false);
    const [message, setMessage] = useState('');
    const [createdTest, setCreatedTest] = useState(null);
    const [estimatedTime, setEstimatedTime] = useState(0);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: name === 'num_questions' ? parseInt(value) : value
        }));
    };

    const handleTestDataChange = (e) => {
        const { name, value } = e.target;
        setTestData(prev => ({ ...prev, [name]: value }));
    };

    // ✅ OPTIMIZED: Calculate estimated time
    const calculateEstimatedTime = (numQuestions) => {
        // Rough estimate: ~5-8 seconds per question
        return Math.ceil(numQuestions * 7);
    };

    // Step 1: Generate MCQs
    const handleGenerate = async (e) => {
        e.preventDefault();
        setGenerating(true);
        setMessage('');
        setGeneratedQuestions(null);
        
        // ✅ Show estimated time
        const estimated = calculateEstimatedTime(formData.num_questions);
        setEstimatedTime(estimated);

        try {
            const response = await mcqApi.generate(orgId, formData, token);
            setGeneratedQuestions(response.questions);
            setMessage(`✅ Generated ${response.questions.length} questions successfully!`);
            
            // Auto-fill test title
            setTestData(prev => ({
                ...prev,
                title: `${formData.topic} - ${formData.difficulty} Test`
            }));
        } catch (err) {
            setMessage(`❌ Error: ${err.message}`);
        } finally {
            setGenerating(false);
            setEstimatedTime(0);
        }
    };

    // Step 2: Create test from generated questions
    const handleCreateTest = async () => {
        if (!testData.title.trim()) {
            setMessage('❌ Please enter a test title');
            return;
        }

        setCreating(true);
        setMessage('');

        try {
            const payload = {
                title: testData.title,
                description: testData.description,
                topic: formData.topic,
                difficulty: formData.difficulty,
                questions: generatedQuestions
            };

            const response = await mcqApi.createTest(orgId, payload, token);
            setCreatedTest(response);
            setMessage(`✅ Test "${response.title}" created successfully!`);
            
            // Reset form after 3 seconds
            setTimeout(() => {
                setFormData({ topic: '', difficulty: 'medium', num_questions: 5 });
                setTestData({ title: '', description: '' });
                setGeneratedQuestions(null);
                setCreatedTest(null);
            }, 3000);
        } catch (err) {
            setMessage(`❌ Error creating test: ${err.message}`);
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Create MCQ Test"
                subtitle="Generate AI-powered questions from your training content and publish tests for your team"
                backTo="/dashboard"
                backLabel="Dashboard"
            />

            {/* Info Box */}
            <div className="bg-gradient-to-r from-blue-50 to-cyan-50 border-2 border-blue-200 rounded-2xl p-5">
                <div className="flex items-start">
                    <AlertCircle className="text-blue-600 mr-3 flex-shrink-0 mt-0.5" size={22} />
                    <div className="text-sm text-blue-800">
                        <p className="font-bold mb-2 text-base">📋 2-Step Process:</p>
                        <ol className="list-decimal list-inside space-y-1.5 ml-1">
                            <li className="font-medium">Generate MCQs from your training content (~30-60 seconds)</li>
                            <li className="font-medium">Review and save the test for trainees</li>
                        </ol>
                    </div>
                </div>
            </div>

            {/* Step 1: Generate MCQs */}
            {!generatedQuestions && (
                <form onSubmit={handleGenerate} className="space-y-6 max-w-2xl">
                    <h4 className="font-bold text-slate-700 text-lg flex items-center">
                        <span className="w-8 h-8 bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-full flex items-center justify-center mr-3 font-black">1</span>
                        Generate Questions
                    </h4>

                    {/* Topic */}
                    <div>
                        <label className="block text-sm font-bold text-slate-700 mb-2 flex items-center">
                            <span className="w-1 h-4 bg-gradient-to-b from-cyan-500 to-blue-600 rounded-full mr-2"></span>
                            Topic *
                        </label>
                        <input
                            type="text"
                            name="topic"
                            value={formData.topic}
                            onChange={handleChange}
                            placeholder="e.g., SSL certificates, DigiCert products"
                            required
                            disabled={generating}
                            className="w-full p-3.5 border-2 border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white/80 transition-all hover:border-slate-300"
                        />
                    </div>

                    {/* Difficulty */}
                    <div>
                        <label className="block text-sm font-bold text-slate-700 mb-2 flex items-center">
                            <span className="w-1 h-4 bg-gradient-to-b from-cyan-500 to-blue-600 rounded-full mr-2"></span>
                            Difficulty Level *
                        </label>
                        <div className="grid grid-cols-3 gap-3">
                            {['easy', 'medium', 'hard'].map(level => (
                                <button
                                    key={level}
                                    type="button"
                                    onClick={() => setFormData(prev => ({ ...prev, difficulty: level }))}
                                    disabled={generating}
                                    className={`p-3.5 rounded-2xl border-2 font-bold transition-all ${
                                        formData.difficulty === level
                                            ? 'border-cyan-500 bg-gradient-to-r from-cyan-50 to-blue-50 text-cyan-700 shadow-md'
                                            : 'border-slate-200 text-slate-600 hover:border-cyan-300 hover:bg-slate-50'
                                    }`}
                                >
                                    {level.charAt(0).toUpperCase() + level.slice(1)}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Number of Questions */}
                    <div>
                        <label className="block text-sm font-bold text-slate-700 mb-2 flex items-center">
                            <span className="w-1 h-4 bg-gradient-to-b from-cyan-500 to-blue-600 rounded-full mr-2"></span>
                            Number of Questions *
                        </label>
                        <input
                            type="number"
                            name="num_questions"
                            value={formData.num_questions}
                            onChange={handleChange}
                            min="3"
                            max="10"
                            required
                            disabled={generating}
                            className="w-full p-3.5 border-2 border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white/80 transition-all hover:border-slate-300"
                        />
                        <p className="text-xs text-slate-500 mt-2 flex items-center">
                            <Clock size={12} className="mr-1" />
                            Estimated time: ~{calculateEstimatedTime(formData.num_questions)} seconds
                        </p>
                    </div>

                    <Button
                        type="submit"
                        loading={generating}
                        className="w-full"
                        disabled={!formData.topic}
                    >
                        {generating ? (
                            <>
                                <Loader2 className="animate-spin mr-2" size={18} />
                                Generating... ({estimatedTime}s estimated)
                            </>
                        ) : (
                            <>
                                <FileText size={18} className="mr-2" />
                                Generate MCQs
                            </>
                        )}
                    </Button>
                </form>
            )}

            {/* Step 2: Review and Create Test */}
            {generatedQuestions && !createdTest && (
                <div className="space-y-6">
                    <h4 className="font-bold text-slate-700 text-lg flex items-center">
                        <span className="w-8 h-8 bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-full flex items-center justify-center mr-3 font-black">2</span>
                        Review & Create Test
                    </h4>

                    {/* Test Title */}
                    <div>
                        <label className="block text-sm font-bold text-slate-700 mb-2 flex items-center">
                            <span className="w-1 h-4 bg-gradient-to-b from-cyan-500 to-blue-600 rounded-full mr-2"></span>
                            Test Title *
                        </label>
                        <input
                            type="text"
                            name="title"
                            value={testData.title}
                            onChange={handleTestDataChange}
                            placeholder="Enter test title"
                            required
                            className="w-full p-3.5 border-2 border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white/80"
                        />
                    </div>

                    {/* Description */}
                    <div>
                        <label className="block text-sm font-bold text-slate-700 mb-2 flex items-center">
                            <span className="w-1 h-4 bg-gradient-to-b from-cyan-500 to-blue-600 rounded-full mr-2"></span>
                            Description (Optional)
                        </label>
                        <textarea
                            name="description"
                            value={testData.description}
                            onChange={handleTestDataChange}
                            rows="3"
                            placeholder="Add a description for this test"
                            className="w-full p-3.5 border-2 border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white/80"
                        />
                    </div>

                    {/* Preview Questions */}
                    <div className="bg-gradient-to-br from-slate-50 to-white border-2 border-slate-200 rounded-2xl p-6">
                        <h5 className="font-black text-slate-800 mb-4 flex items-center">
                            <CheckCircle className="mr-2 text-cyan-600" size={20} />
                            Generated Questions Preview ({generatedQuestions.length})
                        </h5>
                        <div className="space-y-4">
                            {generatedQuestions.slice(0, 2).map((q, idx) => (
                                <div key={idx} className="bg-white p-4 rounded-xl border-2 border-slate-100 shadow-sm">
                                    <p className="font-bold text-slate-900 mb-3">
                                        Q{idx + 1}: {q.question_text}
                                    </p>
                                    <div className="text-sm text-slate-600 space-y-1.5">
                                        {q.options.map((opt, i) => (
                                            <div 
                                                key={i} 
                                                className={`p-2 rounded-lg ${
                                                    opt.is_correct 
                                                        ? 'bg-emerald-50 text-emerald-700 font-bold border-2 border-emerald-200' 
                                                        : 'bg-slate-50'
                                                }`}
                                            >
                                                {['A', 'B', 'C', 'D'][i]}) {opt.option_text}
                                                {opt.is_correct && <span className="ml-2">✓</span>}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                            {generatedQuestions.length > 2 && (
                                <p className="text-sm text-slate-500 text-center font-medium py-3 bg-slate-50 rounded-xl">
                                    ... and {generatedQuestions.length - 2} more questions
                                </p>
                            )}
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex space-x-3">
                        <Button
                            onClick={handleCreateTest}
                            loading={creating}
                            className="flex-1 bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-600 hover:to-green-700"
                        >
                            {creating ? (
                                <>
                                    <Loader2 className="animate-spin mr-2" size={18} />
                                    Creating Test...
                                </>
                            ) : (
                                <>
                                    <CheckCircle size={18} className="mr-2" />
                                    Create Test
                                </>
                            )}
                        </Button>
                        <Button
                            onClick={() => {
                                setGeneratedQuestions(null);
                                setMessage('');
                            }}
                            className="flex-1 bg-gradient-to-r from-slate-500 to-gray-600 hover:from-slate-600 hover:to-gray-700"
                        >
                            🔄 Regenerate
                        </Button>
                    </div>
                </div>
            )}

            {/* Result Message */}
            {message && (
                <div className={`p-5 rounded-2xl border-2 font-bold shadow-lg ${
                    message.startsWith('✅')
                        ? 'bg-gradient-to-r from-emerald-50 to-green-50 border-emerald-300 text-emerald-700'
                        : 'bg-gradient-to-r from-rose-50 to-red-50 border-rose-300 text-rose-700'
                }`}>
                    {message}
                </div>
            )}

            {/* Created Test Info */}
            {createdTest && (
                <div className="bg-gradient-to-r from-emerald-50 via-green-50 to-cyan-50 rounded-2xl p-6 border-2 border-emerald-200 shadow-xl">
                    <h4 className="font-black text-emerald-900 mb-4 flex items-center text-lg">
                        <CheckCircle className="mr-2 text-emerald-600" size={24} />
                        Test Created Successfully! 🎉
                    </h4>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="bg-white/60 p-3 rounded-xl">
                            <span className="text-slate-600 font-bold block mb-1">Title:</span>
                            <p className="font-black text-slate-900">{createdTest.title}</p>
                        </div>
                        <div className="bg-white/60 p-3 rounded-xl">
                            <span className="text-slate-600 font-bold block mb-1">Topic:</span>
                            <p className="font-black text-slate-900">{createdTest.topic}</p>
                        </div>
                        <div className="bg-white/60 p-3 rounded-xl">
                            <span className="text-slate-600 font-bold block mb-1">Difficulty:</span>
                            <p className="font-black text-slate-900 capitalize">{createdTest.difficulty}</p>
                        </div>
                        <div className="bg-white/60 p-3 rounded-xl">
                            <span className="text-slate-600 font-bold block mb-1">Questions:</span>
                            <p className="font-black text-slate-900">
                                {createdTest.questions_json?.length || 0}
                            </p>
                        </div>
                    </div>
                </div>
            )}
            <RelatedLinks links={[
                { label: 'MCQ Practice',          to: '/mcq' },
                { label: 'Performance Dashboard', to: '/performance' },
            ]} />
        </div>
    );
}