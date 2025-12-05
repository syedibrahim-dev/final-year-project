import React, { useState } from 'react';
import { FileText, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Button, Input } from '../App';

export default function MCQTestCreator({ orgId, token }) {
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        topic: '',
        difficulty: 'medium',
        num_questions: 5
    });
    const [creating, setCreating] = useState(false);
    const [message, setMessage] = useState('');
    const [createdTest, setCreatedTest] = useState(null);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: name === 'num_questions' ? parseInt(value) : value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setCreating(true);
        setMessage('');
        setCreatedTest(null);

        try {
            const response = await apiFetch(
                `/orgs/${orgId}/mcq/tests`,
                'POST',
                formData,
                token
            );

            setCreatedTest(response);
            setMessage(`Success! Created test "${response.title}" with ${response.total_questions} questions.`);
            
            // Reset form
            setFormData({
                title: '',
                description: '',
                topic: '',
                difficulty: 'medium',
                num_questions: 5
            });
        } catch (err) {
            setMessage(`Error: ${err.message}`);
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="border-b pb-4">
                <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                    <FileText className="mr-2 text-indigo-600" size={28} />
                    Create MCQ Test
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                    Generate and save MCQ tests for trainees to attempt
                </p>
            </div>

            {/* Info Box */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start">
                    <AlertCircle className="text-blue-600 mr-3 flex-shrink-0" size={20} />
                    <div className="text-sm text-blue-800">
                        <p className="font-semibold mb-1">How it works:</p>
                        <ul className="list-disc list-inside space-y-1">
                            <li>MCQs are generated from your uploaded training content</li>
                            <li>Tests are saved and can be assigned to trainees</li>
                            <li>Trainee performance is automatically tracked</li>
                            <li>View results in the Performance Dashboard</li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
                {/* Test Title */}
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Test Title *
                    </label>
                    <input
                        type="text"
                        name="title"
                        value={formData.title}
                        onChange={handleChange}
                        placeholder="e.g., Week 1 Sales Fundamentals Assessment"
                        required
                        disabled={creating}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                    />
                </div>

                {/* Description */}
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Description (Optional)
                    </label>
                    <textarea
                        name="description"
                        value={formData.description}
                        onChange={handleChange}
                        placeholder="Brief description of what this test covers..."
                        rows="3"
                        disabled={creating}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                    />
                </div>

                {/* Topic */}
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Topic *
                    </label>
                    <input
                        type="text"
                        name="topic"
                        value={formData.topic}
                        onChange={handleChange}
                        placeholder="e.g., sales objections, BANT qualification, closing techniques"
                        required
                        disabled={creating}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                        MCQs will be generated from training content related to this topic
                    </p>
                </div>

                {/* Difficulty */}
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Difficulty Level *
                    </label>
                    <div className="grid grid-cols-3 gap-3">
                        {['easy', 'medium', 'hard'].map(level => (
                            <button
                                key={level}
                                type="button"
                                onClick={() => setFormData(prev => ({ ...prev, difficulty: level }))}
                                disabled={creating}
                                className={`p-3 rounded-lg border-2 font-medium transition-all ${
                                    formData.difficulty === level
                                        ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                                        : 'border-gray-200 text-gray-600 hover:border-indigo-300'
                                } ${creating ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                {level.charAt(0).toUpperCase() + level.slice(1)}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Number of Questions */}
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Number of Questions *
                    </label>
                    <input
                        type="number"
                        name="num_questions"
                        value={formData.num_questions}
                        onChange={handleChange}
                        min="3"
                        max="20"
                        required
                        disabled={creating}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                        Recommended: 5-10 questions per test
                    </p>
                </div>

                {/* Submit Button */}
                <Button
                    type="submit"
                    loading={creating}
                    className="w-full"
                    disabled={!formData.title || !formData.topic}
                >
                    {creating ? (
                        <>
                            <Loader2 className="animate-spin mr-2" size={18} />
                            Creating Test... (30-60 seconds)
                        </>
                    ) : (
                        <>
                            <FileText className="mr-2" size={18} />
                            Create MCQ Test
                        </>
                    )}
                </Button>
            </form>

            {/* Result Message */}
            {message && (
                <div className={`p-4 rounded-lg border ${
                    message.startsWith('Success')
                        ? 'bg-green-50 border-green-200'
                        : 'bg-red-50 border-red-200'
                }`}>
                    <div className="flex items-start">
                        {message.startsWith('Success') ? (
                            <CheckCircle className="text-green-600 mr-3 flex-shrink-0" size={20} />
                        ) : (
                            <AlertCircle className="text-red-600 mr-3 flex-shrink-0" size={20} />
                        )}
                        <div className="flex-1">
                            <p className={`font-semibold ${
                                message.startsWith('Success') ? 'text-green-900' : 'text-red-900'
                            }`}>
                                {message.startsWith('Success') ? 'Test Created!' : 'Creation Failed'}
                            </p>
                            <p className={`text-sm mt-1 ${
                                message.startsWith('Success') ? 'text-green-800' : 'text-red-800'
                            }`}>
                                {message}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Created Test Info */}
            {createdTest && (
                <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg p-6 border border-indigo-200">
                    <h4 className="font-semibold text-indigo-900 mb-3 flex items-center">
                        <CheckCircle className="mr-2 text-green-600" size={20} />
                        Test Details
                    </h4>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <span className="text-gray-600">Title:</span>
                            <p className="font-medium text-gray-900">{createdTest.title}</p>
                        </div>
                        <div>
                            <span className="text-gray-600">Topic:</span>
                            <p className="font-medium text-gray-900">{createdTest.topic}</p>
                        </div>
                        <div>
                            <span className="text-gray-600">Difficulty:</span>
                            <p className="font-medium text-gray-900">{createdTest.difficulty}</p>
                        </div>
                        <div>
                            <span className="text-gray-600">Questions:</span>
                            <p className="font-medium text-gray-900">{createdTest.total_questions}</p>
                        </div>
                    </div>
                    <p className="text-sm text-indigo-700 mt-4">
                        ✅ Test is now available for trainees to attempt. View results in the Performance Dashboard.
                    </p>
                </div>
            )}
        </div>
    );
}