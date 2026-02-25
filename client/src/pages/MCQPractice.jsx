import React, { useState, useEffect } from 'react';
import { Brain, CheckCircle, XCircle, RefreshCw, Loader2, Award, AlertCircle, Trophy, Trash2 } from 'lucide-react';
import { mcq as mcqApi } from '../utils/api';
import { Button } from '../App';

export default function MCQPracticeView({ orgId, token }) {
    const [tests, setTests] = useState([]);
    const [selectedTest, setSelectedTest] = useState(null);
    const [testDetails, setTestDetails] = useState(null);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [answers, setAnswers] = useState([]);
    const [showResult, setShowResult] = useState(false);
    const [finalResult, setFinalResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [startTime, setStartTime] = useState(null);
    const [deleting, setDeleting] = useState(null);

    useEffect(() => {
        fetchTests();
    }, []);

    const fetchTests = async () => {
        setLoading(true);
        setError('');
        try {
            // ✅ FIXED: API returns {tests: [...]}
            const response = await mcqApi.listTests(orgId, token);
            const testsList = response.tests || [];
            
            if (testsList.length === 0) {
                setError('No MCQ tests available. Ask your admin to create some first.');
            } else {
                setTests(testsList);
            }
        } catch (err) {
            setError(`Error loading tests: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteTest = async (e, testId, testTitle) => {
        e.stopPropagation(); // Prevent triggering startTest
        if (!window.confirm(`Delete "${testTitle}"? This will also remove all attempts and scores for this test.`)) {
            return;
        }
        setDeleting(testId);
        try {
            await mcqApi.deleteTest(orgId, testId, token);
            setTests(prev => prev.filter(t => t.id !== testId));
            if (tests.length <= 1) {
                setError('No MCQ tests available. Ask your admin to create some first.');
            }
        } catch (err) {
            setError(`Failed to delete test: ${err.message}`);
        } finally {
            setDeleting(null);
        }
    };

    const startTest = async (testId) => {
        setLoading(true);
        setError('');
        try {
            const data = await mcqApi.getTest(orgId, testId, token);
            
            // ✅ FIXED: Check if questions exist
            if (!data.questions || data.questions.length === 0) {
                setError('This test has no questions.');
                setLoading(false);
                return;
            }
            
            setTestDetails(data);
            setSelectedTest(testId);
            setCurrentIndex(0);
            setAnswers(new Array(data.questions.length).fill(null));
            setShowResult(false);
            setFinalResult(null);
            setStartTime(Date.now());
        } catch (err) {
            setError(`Error loading test: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleAnswerSelect = (answerLetter) => {
        const newAnswers = [...answers];
        newAnswers[currentIndex] = answerLetter;
        setAnswers(newAnswers);
    };

    const handleNext = () => {
        if (currentIndex < testDetails.questions.length - 1) {
            setCurrentIndex(currentIndex + 1);
        }
    };

    const handlePrevious = () => {
        if (currentIndex > 0) {
            setCurrentIndex(currentIndex - 1);
        }
    };

    const handleSubmit = async () => {
        if (answers.some(a => a === null)) {
            if (!window.confirm('You have unanswered questions. Submit anyway?')) {
                return;
            }
        }

        setLoading(true);
        try {
            const timeTaken = Math.floor((Date.now() - startTime) / 1000);
            
            // ✅ FIXED: Proper submission format
            const submission = {
                test_id: selectedTest,
                answers: answers.map(a => a || 'A'), // Default null to 'A'
                time_taken_seconds: timeTaken
            };

            const result = await mcqApi.submitAttempt(orgId, submission, token);
            
            // ✅ FIXED: Build detailed results for review
            const detailedResults = testDetails.questions.map((q, idx) => ({
                question: q.question_text,
                user_answer: answers[idx],
                correct_answer: q.correct_answer,
                is_correct: answers[idx] === q.correct_answer,
                explanation: q.explanation
            }));
            
            setFinalResult({
                ...result,
                answers_json: detailedResults
            });
            setShowResult(true);
        } catch (err) {
            setError(`Error submitting test: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleRestart = () => {
        setSelectedTest(null);
        setTestDetails(null);
        setCurrentIndex(0);
        setAnswers([]);
        setShowResult(false);
        setFinalResult(null);
        setStartTime(null);
        setError('');
    };

    const getOptionLetter = (index) => {
        return ['A', 'B', 'C', 'D'][index];
    };

    // Initial state - show test selection
    if (!selectedTest) {
        return (
            <div className="space-y-6">
                <div className="border-b pb-4">
                    <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                        <Brain className="mr-2 text-indigo-600" size={28} />
                        MCQ Practice
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                        Select a test to practice and improve your knowledge
                    </p>
                </div>

                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <div className="flex items-start">
                            <AlertCircle className="text-red-600 mr-3 flex-shrink-0" size={20} />
                            <p className="text-sm text-red-800">{error}</p>
                        </div>
                    </div>
                )}

                {loading ? (
                    <div className="flex items-center justify-center p-12">
                        <Loader2 className="animate-spin h-8 w-8 text-indigo-600" />
                        <span className="ml-3 text-gray-600">Loading tests...</span>
                    </div>
                ) : tests.length === 0 ? (
                    <div className="text-center p-12 bg-gray-50 rounded-lg border">
                        <Brain className="mx-auto h-16 w-16 text-gray-400 mb-4" />
                        <h3 className="text-xl font-semibold text-gray-700 mb-2">No Tests Available</h3>
                        <p className="text-gray-500">Ask your admin to create MCQ tests.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {tests.map(test => (
                            <div
                                key={test.id}
                                className="bg-white border-2 border-gray-200 rounded-lg p-6 hover:border-indigo-400 transition cursor-pointer relative group"
                                onClick={() => startTest(test.id)}
                            >
                                <div className="flex items-start justify-between mb-3">
                                    <h4 className="font-semibold text-gray-900 text-lg pr-8">{test.title}</h4>
                                    <div className="flex items-center space-x-2">
                                        <button
                                            onClick={(e) => handleDeleteTest(e, test.id, test.title)}
                                            disabled={deleting === test.id}
                                            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition"
                                            title="Delete test"
                                        >
                                            {deleting === test.id ? (
                                                <Loader2 className="animate-spin" size={18} />
                                            ) : (
                                                <Trash2 size={18} />
                                            )}
                                        </button>
                                        <Trophy className="text-indigo-500" size={24} />
                                    </div>
                                </div>
                                
                                {test.description && (
                                    <p className="text-sm text-gray-600 mb-4">{test.description}</p>
                                )}
                                
                                <div className="flex items-center space-x-4 text-sm">
                                    <span className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded-full font-medium">
                                        {test.topic}
                                    </span>
                                    <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded-full">
                                        {test.difficulty}
                                    </span>
                                    <span className="text-gray-600">
                                        {test.questions_count || 0} questions
                                    </span>
                                </div>
                                
                                <button className="mt-4 w-full py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition">
                                    Start Test
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    // Final results view
    if (showResult && finalResult) {
        const passed = finalResult.score >= 70;
        
        return (
            <div className="space-y-6">
                <div className="border-b pb-4">
                    <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                        <Award className="mr-2 text-yellow-600" size={28} />
                        Test Results
                    </h3>
                </div>

                <div className={`rounded-lg p-8 border-2 ${
                    passed 
                        ? 'bg-green-50 border-green-300' 
                        : 'bg-red-50 border-red-300'
                }`}>
                    <div className="text-center">
                        {passed ? (
                            <CheckCircle className="mx-auto text-green-600 mb-4" size={64} />
                        ) : (
                            <XCircle className="mx-auto text-red-600 mb-4" size={64} />
                        )}
                        
                        <h4 className={`text-3xl font-bold mb-2 ${
                            passed ? 'text-green-900' : 'text-red-900'
                        }`}>
                            {passed ? 'Congratulations!' : 'Keep Practicing!'}
                        </h4>
                        
                        <p className={`text-lg mb-6 ${
                            passed ? 'text-green-800' : 'text-red-800'
                        }`}>
                            You scored {finalResult.score.toFixed(1)}%
                        </p>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mb-6">
                        <div className="bg-white rounded-lg p-4 text-center">
                            <div className="text-2xl font-bold text-blue-600">{finalResult.total_questions}</div>
                            <div className="text-xs text-gray-600">Total Questions</div>
                        </div>
                        <div className="bg-white rounded-lg p-4 text-center">
                            <div className="text-2xl font-bold text-green-600">{finalResult.correct_answers}</div>
                            <div className="text-xs text-gray-600">Correct</div>
                        </div>
                        <div className="bg-white rounded-lg p-4 text-center">
                            <div className="text-2xl font-bold text-red-600">
                                {finalResult.total_questions - finalResult.correct_answers}
                            </div>
                            <div className="text-xs text-gray-600">Incorrect</div>
                        </div>
                    </div>

                    <Button onClick={handleRestart} className="w-full bg-indigo-600 hover:bg-indigo-700">
                        <RefreshCw className="mr-2" size={16} />
                        Try Another Test
                    </Button>
                </div>

                {/* Question-by-question review */}
                <div className="bg-white border rounded-lg p-6">
                    <h4 className="font-semibold text-gray-900 mb-4">Review Your Answers</h4>
                    <div className="space-y-4">
                        {finalResult.answers_json?.map((detail, idx) => (
                            <div
                                key={idx}
                                className={`p-4 rounded-lg border-2 ${
                                    detail.is_correct
                                        ? 'bg-green-50 border-green-300'
                                        : 'bg-red-50 border-red-300'
                                }`}
                            >
                                <div className="flex items-start justify-between mb-2">
                                    <p className="font-medium text-gray-900">
                                        Q{idx + 1}: {detail.question}
                                    </p>
                                    {detail.is_correct ? (
                                        <CheckCircle className="text-green-600 flex-shrink-0" size={20} />
                                    ) : (
                                        <XCircle className="text-red-600 flex-shrink-0" size={20} />
                                    )}
                                </div>
                                
                                {!detail.is_correct && (
                                    <div className="text-sm mt-2">
                                        <p className="text-red-800">
                                            Your answer: {detail.user_answer}
                                        </p>
                                        <p className="text-green-800">
                                            Correct answer: {detail.correct_answer}
                                        </p>
                                    </div>
                                )}
                                
                                {detail.explanation && (
                                    <p className="text-sm text-gray-700 mt-2">
                                        <strong>Explanation:</strong> {detail.explanation}
                                    </p>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    // Active test view
    if (!testDetails) {
        return (
            <div className="flex items-center justify-center p-12">
                <Loader2 className="animate-spin h-8 w-8 text-indigo-600" />
            </div>
        );
    }

    const currentQuestion = testDetails.questions[currentIndex];
    const progress = ((currentIndex + 1) / testDetails.questions.length) * 100;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="border-b pb-4 flex justify-between items-center">
                <div>
                    <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                        <Brain className="mr-2 text-indigo-600" size={28} />
                        {testDetails.title}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                        Question {currentIndex + 1} of {testDetails.questions.length}
                    </p>
                </div>
                <Button onClick={handleRestart} className="bg-gray-500 hover:bg-gray-600">
                    Exit Test
                </Button>
            </div>

            {/* Progress Bar */}
            <div className="bg-gray-200 rounded-full h-2">
                <div
                    className="bg-indigo-600 h-2 rounded-full transition-all"
                    style={{ width: `${progress}%` }}
                />
            </div>

            {/* Question Card */}
            <div className="bg-white border rounded-xl p-6 shadow-sm">
                <div className="mb-6">
                    <div className="flex items-center space-x-2 mb-3">
                        <span className="px-3 py-1 bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-full">
                            {currentQuestion.difficulty}
                        </span>
                        <span className={`px-2 py-1 rounded-full text-xs ${
                            answers[currentIndex] !== null
                                ? 'bg-green-100 text-green-700'
                                : 'bg-gray-100 text-gray-700'
                        }`}>
                            {answers[currentIndex] !== null ? 'Answered' : 'Not answered'}
                        </span>
                    </div>
                    <h4 className="text-lg font-semibold text-gray-800 leading-relaxed">
                        {currentQuestion.question_text}
                    </h4>
                </div>

                {/* Answer Options */}
                <div className="space-y-3 mb-6">
                    {currentQuestion.options.map((option, index) => {
                        const letter = getOptionLetter(index);
                        const isSelected = answers[currentIndex] === letter;

                        return (
                            <button
                                key={index}
                                onClick={() => handleAnswerSelect(letter)}
                                className={`w-full text-left p-4 border-2 rounded-lg transition-all ${
                                    isSelected
                                        ? 'border-indigo-500 bg-indigo-50 text-indigo-900'
                                        : 'border-gray-300 bg-white hover:bg-gray-50 text-gray-800'
                                }`}
                            >
                                <div className="flex items-center">
                                    <span className="font-medium">
                                        <strong>{letter})</strong> {option.option_text}
                                    </span>
                                </div>
                            </button>
                        );
                    })}
                </div>

                {/* Navigation */}
                <div className="flex justify-between items-center pt-4 border-t">
                    <Button
                        onClick={handlePrevious}
                        disabled={currentIndex === 0}
                        className="bg-gray-500 hover:bg-gray-600"
                    >
                        Previous
                    </Button>

                    <span className="text-sm text-gray-600">
                        {answers.filter(a => a !== null).length} / {testDetails.questions.length} answered
                    </span>

                    {currentIndex < testDetails.questions.length - 1 ? (
                        <Button onClick={handleNext}>
                            Next
                        </Button>
                    ) : (
                        <Button
                            onClick={handleSubmit}
                            loading={loading}
                            className="bg-green-600 hover:bg-green-700"
                        >
                            Submit Test
                        </Button>
                    )}
                </div>
            </div>
        </div>
    );
}