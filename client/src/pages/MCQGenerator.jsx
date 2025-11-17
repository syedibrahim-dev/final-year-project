import React, { useState, useEffect } from 'react';
import { Wand2, FileText, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Button, Select } from '../App';

export default function MCQGeneratorView({ orgId, token }) {
    const [contents, setContents] = useState([]);
    const [selectedContent, setSelectedContent] = useState('');
    const [numQuestions, setNumQuestions] = useState(5);
    const [difficulty, setDifficulty] = useState('medium');
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [message, setMessage] = useState('');
    const [generatedCount, setGeneratedCount] = useState(0);

    useEffect(() => {
        fetchContents();
    }, []);

    const fetchContents = async () => {
        setLoading(true);
        try {
            const data = await apiFetch(`/orgs/${orgId}/content`, 'GET', null, token);
            setContents(data);
            if (data.length > 0) {
                setSelectedContent(data[0].id.toString());
            }
        } catch (err) {
            setMessage(`Error: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleGenerate = async (e) => {
        e.preventDefault();
        if (!selectedContent) {
            setMessage('Error: Please select content first');
            return;
        }

        setGenerating(true);
        setMessage('');
        setGeneratedCount(0);

        try {
            const response = await apiFetch(`/orgs/${orgId}/mcq/generate`, 'POST', {
                content_id: parseInt(selectedContent),
                num_questions: numQuestions,
                difficulty: difficulty
            }, token);

            setMessage(`Success! Generated ${response.count} MCQ questions from "${response.source_content}"`);
            setGeneratedCount(response.count);
        } catch (err) {
            setMessage(`Error: ${err.message || 'Failed to generate MCQs. Make sure Ollama is running.'}`);
        } finally {
            setGenerating(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-12">
                <Loader2 className="animate-spin h-8 w-8 text-indigo-600" />
                <span className="ml-3 text-gray-600">Loading content...</span>
            </div>
        );
    }

    if (contents.length === 0) {
        return (
            <div className="text-center p-12">
                <FileText className="mx-auto h-16 w-16 text-gray-400 mb-4" />
                <h3 className="text-xl font-semibold text-gray-700 mb-2">No Content Available</h3>
                <p className="text-gray-500 mb-6">Upload training content first to generate MCQ questions.</p>
                <Button onClick={() => window.location.reload()}>
                    Refresh Page
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="border-b pb-4">
                <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                    <Wand2 className="mr-2 text-indigo-600" size={28} />
                    Generate MCQ Questions
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                    Use AI to automatically create multiple choice questions from your training content
                </p>
            </div>

            {/* Info Box */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start">
                    <AlertCircle className="text-blue-600 mr-3 flex-shrink-0" size={20} />
                    <div className="text-sm text-blue-800">
                        <p className="font-semibold mb-1">Requirements:</p>
                        <ul className="list-disc list-inside space-y-1">
                            <li>Ollama must be running (check: <code>ollama list</code>)</li>
                            <li>Model should be pulled (recommend: llama3.1:8b-instruct-q4_K_M)</li>
                            <li>Training content must be uploaded and indexed</li>
                            <li>Generation takes ~30 seconds per 5 questions</li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* Generation Form */}
            <form onSubmit={handleGenerate} className="space-y-6 max-w-2xl">
                {/* Select Content */}
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Select Training Content
                    </label>
                    <select
                        value={selectedContent}
                        onChange={(e) => setSelectedContent(e.target.value)}
                        required
                        disabled={generating}
                        className="w-full p-3 border border-gray-300 rounded-lg bg-white focus:ring-indigo-500 focus:border-indigo-500 transition duration-150"
                    >
                        {contents.map(content => (
                            <option key={content.id} value={content.id}>
                                {content.file_name} (v{content.version}) - {content.chunk_count} chunks
                            </option>
                        ))}
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                        MCQs will be generated from the selected document
                    </p>
                </div>

                {/* Number of Questions */}
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
                        required
                        disabled={generating}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 transition duration-150"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                        Recommended: 5-10 questions per session (max 20)
                    </p>
                </div>

                {/* Difficulty Level */}
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Difficulty Level
                    </label>
                    <div className="grid grid-cols-3 gap-3">
                        {['easy', 'medium', 'hard'].map(level => (
                            <button
                                key={level}
                                type="button"
                                onClick={() => setDifficulty(level)}
                                disabled={generating}
                                className={`p-3 rounded-lg border-2 font-medium transition-all ${
                                    difficulty === level
                                        ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                                        : 'border-gray-200 text-gray-600 hover:border-indigo-300'
                                } ${generating ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                {level.charAt(0).toUpperCase() + level.slice(1)}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Generate Button */}
                <Button 
                    type="submit" 
                    loading={generating}
                    className="w-full"
                    disabled={!selectedContent}
                >
                    {generating ? (
                        <>
                            <Loader2 className="animate-spin mr-2" size={18} />
                            Generating Questions... (This may take 30-60 seconds)
                        </>
                    ) : (
                        <>
                            <Wand2 className="mr-2" size={18} />
                            Generate {numQuestions} MCQ Questions
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
                        <div>
                            <p className={`font-semibold ${
                                message.startsWith('Success') ? 'text-green-900' : 'text-red-900'
                            }`}>
                                {message.startsWith('Success') ? 'Success!' : 'Generation Failed'}
                            </p>
                            <p className={`text-sm mt-1 ${
                                message.startsWith('Success') ? 'text-green-800' : 'text-red-800'
                            }`}>
                                {message}
                            </p>
                            {message.startsWith('Success') && generatedCount > 0 && (
                                <p className="text-sm text-green-700 mt-2">
                                    Trainees can now practice these questions in the MCQ Practice section.
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Generation Stats */}
            {generatedCount > 0 && (
                <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg p-6 border border-indigo-200">
                    <h4 className="font-semibold text-indigo-900 mb-3">Generation Summary</h4>
                    <div className="grid grid-cols-3 gap-4 text-center">
                        <div>
                            <div className="text-3xl font-bold text-indigo-600">{generatedCount}</div>
                            <div className="text-xs text-gray-600">Questions Created</div>
                        </div>
                        <div>
                            <div className="text-3xl font-bold text-purple-600">{difficulty}</div>
                            <div className="text-xs text-gray-600">Difficulty</div>
                        </div>
                        <div>
                            <div className="text-3xl font-bold text-pink-600">
                                {contents.find(c => c.id === parseInt(selectedContent))?.chunk_count || 0}
                            </div>
                            <div className="text-xs text-gray-600">Source Chunks</div>
                        </div>
                    </div>
                </div>
            )}

            {/* Troubleshooting */}
            <details className="bg-gray-50 rounded-lg p-4 border">
                <summary className="cursor-pointer font-semibold text-gray-700">
                    Troubleshooting: Generation not working?
                </summary>
                <div className="mt-3 space-y-2 text-sm text-gray-600">
                    <p><strong>1. Check Ollama is running:</strong></p>
                    <code className="block bg-gray-800 text-green-400 p-2 rounded">
                        $ ollama list
                    </code>
                    
                    <p className="mt-3"><strong>2. Check backend logs:</strong></p>
                    <p>Look for errors in your FastAPI terminal. Common issues:</p>
                    <ul className="list-disc list-inside ml-4">
                        <li>Ollama not running → Start with <code>ollama serve</code></li>
                        <li>Model not found → Pull with <code>ollama pull llama3.1:8b-instruct-q4_K_M</code></li>
                        <li>No chunks found → Upload content first</li>
                        <li>JSON parsing error → LLM response malformed (retry)</li>
                    </ul>

                    <p className="mt-3"><strong>3. Test backend directly:</strong></p>
                    <code className="block bg-gray-800 text-green-400 p-2 rounded text-xs">
                        curl -X POST http://localhost:8000/orgs/1/mcq/generate \<br/>
                        &nbsp;&nbsp;-H "Authorization: Bearer YOUR_TOKEN" \<br/>
                        &nbsp;&nbsp;-d '{{"content_id": 1, "num_questions": 3, "difficulty": "easy"}}'
                    </code>
                </div>
            </details>
        </div>
    );
}