import React, { useState } from 'react';
import { Brain, CheckCircle, XCircle, RefreshCw, Loader2, Award, Wand2 } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Button } from '../App';

export default function MCQPracticeView({ orgId, token }) {
    // Generation State
    const [topic, setTopic] = useState('');
    const [numQuestions, setNumQuestions] = useState(5);
    const [difficulty, setDifficulty] = useState('medium');
    const [generating, setGenerating] = useState(false);
    
    // Practice State
    const [questions, setQuestions] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [selectedAnswer, setSelectedAnswer] = useState(null);
    const [showResult, setShowResult] = useState(false);
    const [score, setScore] = useState({ correct: 0, incorrect: 0 });
    const [error, setError] = useState('');

    const handleGenerate = async (e) => {
        e.preventDefault();
        if (!topic.trim()) {
            setError('Please enter a topic');
            return;
        }

        setGenerating(true);
        setError('');
        setQuestions([]);
        setScore({ correct: 0, incorrect: 0 });

        try {
            const response = await apiFetch(`/orgs/${orgId}/mcq/generate`, 'POST', {
                topic: topic,
                num_questions: numQuestions,
                difficulty: difficulty
            }, token);

            if (response.questions && response.questions.length > 0) {
                setQuestions(response.questions);
                setCurrentIndex(0);
                setSelectedAnswer(null);
                setShowResult(false);
            } else {
                setError('No questions generated. Please try again with a different topic.');
            }
        } catch (err) {
            setError(`Generation failed: ${err.message}. Make sure Ollama is running and training content exists.`);
        } finally {
            setGenerating(false);
        }
    };

    const handleAnswerSelect = (optionIndex) => {
        if (!showResult) {
            setSelectedAnswer(optionIndex);
        }
    };

    const handleSubmit = () => {
        if (selectedAnswer === null) return;

        const currentQuestion = questions[currentIndex];
        const isCorrect = currentQuestion.options[selectedAnswer].is_correct;

        if (isCorrect) {
            setScore(prev => ({ ...prev, correct: prev.correct + 1 }));
        } else {
            setScore(prev => ({ ...prev, incorrect: prev.incorrect + 1 }));
        }

        setShowResult(true);
    };

    const handleNext = () => {
        if (currentIndex < questions.length - 1) {
            setCurrentIndex(currentIndex + 1);
            setSelectedAnswer(null);
            setShowResult(false);
        }
    };

    const handleRestart = () => {
        setCurrentIndex(0);
        setSelectedAnswer(null);
        setShowResult(false);
        setScore({ correct: 0, incorrect: 0 });
        setQuestions([]);
        setTopic('');
    };

    const currentQuestion = questions[currentIndex];
    const totalAttempts = score.correct + score.incorrect;
    const accuracy = totalAttempts > 0 ? Math.round((score.correct / totalAttempts) * 100) : 0;

    // Show generation form if no questions
    if (questions.length === 0) {
        return (
            <div className="space-y-6">
                {/* Header */}
                <div className="border-b pb-4">
                    <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                        <Brain className="mr-2 text-indigo-600" size={28} />
                        MCQ Practice
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                        Generate and practice MCQ questions from your training content
                    </p>
                </div>

                {/* Info Box */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div className="text-sm text-blue-800">
                        <p className="font-semibold mb-2">How it works:</p>
                        <ol className="list-decimal list-inside space-y-1">
                            <li>Enter a topic related to your training content</li>
                            <li>AI will retrieve relevant content and generate questions</li>
                            <li>Practice and test your knowledge instantly</li>
                        </ol>
                        <p className="mt-3 text-xs text-blue-600">
                            ⚠️ Requires: Ollama running locally + Training content uploaded
                        </p>
                    </div>
                </div>

                {/* Generation Form */}
                <form onSubmit={handleGenerate} className="space-y-6 max-w-2xl">
                    {/* Topic Input */}
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Topic or Question
                        </label>
                        <input
                            type="text"
                            value={topic}
                            onChange={(e) => setTopic(e.target.value)}
                            placeholder="e.g., sales techniques, product features, customer objections"
                            required
                            disabled={generating}
                            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 transition duration-150"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                            Enter a topic from your training materials
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
                            Recommended: 5-10 questions (max 20)
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
                    >
                        {generating ? (
                            <>
                                <Loader2 className="animate-spin mr-2" size={18} />
                                Generating Questions... (30-60 seconds)
                            </>
                        ) : (
                            <>
                                <Wand2 className="mr-2" size={18} />
                                Generate {numQuestions} MCQ Questions
                            </>
                        )}
                    </Button>
                </form>

                {/* Error Message */}
                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <p className="text-sm text-red-800 font-semibold">Generation Failed</p>
                        <p className="text-sm text-red-700 mt-1">{error}</p>
                    </div>
                )}
            </div>
        );
    }

    // Show practice interface if questions exist
    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="border-b pb-4 flex justify-between items-center">
                <div>
                    <h3 className="text-2xl font-bold text-gray-800 flex items-center">
                        <Brain className="mr-2 text-indigo-600" size={28} />
                        MCQ Practice
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                        Question {currentIndex + 1} of {questions.length}
                    </p>
                </div>
                <Button onClick={handleRestart} className="bg-gray-500 hover:bg-gray-600">
                    <RefreshCw className="mr-2" size={16} />
                    New Session
                </Button>
            </div>

            {/* Stats Bar */}
            <div className="grid grid-cols-4 gap-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-blue-600">{totalAttempts}</div>
                    <div className="text-xs text-gray-600">Attempted</div>
                </div>
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">{score.correct}</div>
                    <div className="text-xs text-gray-600">Correct</div>
                </div>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-red-600">{score.incorrect}</div>
                    <div className="text-xs text-gray-600">Incorrect</div>
                </div>
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-purple-600">{accuracy}%</div>
                    <div className="text-xs text-gray-600">Accuracy</div>
                </div>
            </div>

            {/* Question Card */}
            <div className="bg-white border rounded-xl p-6 shadow-sm">
                {/* Question Header */}
                <div className="flex items-start justify-between mb-6">
                    <div className="flex-1">
                        <span className="px-3 py-1 bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-full">
                            {currentQuestion.difficulty}
                        </span>
                        <h4 className="text-lg font-semibold text-gray-800 leading-relaxed mt-3">
                            {currentQuestion.question}
                        </h4>
                    </div>
                </div>

                {/* Answer Options */}
                <div className="space-y-3 mb-6">
                    {currentQuestion.options.map((option, index) => {
                        const isSelected = selectedAnswer === index;
                        const isCorrect = option.is_correct;
                        const isWrong = showResult && isSelected && !isCorrect;

                        let borderColor = 'border-gray-300';
                        let bgColor = 'bg-white hover:bg-gray-50';
                        let textColor = 'text-gray-800';

                        if (showResult) {
                            if (isCorrect) {
                                borderColor = 'border-green-500';
                                bgColor = 'bg-green-50';
                                textColor = 'text-green-900';
                            } else if (isWrong) {
                                borderColor = 'border-red-500';
                                bgColor = 'bg-red-50';
                                textColor = 'text-red-900';
                            }
                        } else if (isSelected) {
                            borderColor = 'border-indigo-500';
                            bgColor = 'bg-indigo-50';
                            textColor = 'text-indigo-900';
                        }

                        return (
                            <button
                                key={index}
                                onClick={() => handleAnswerSelect(index)}
                                disabled={showResult}
                                className={`w-full text-left p-4 border-2 rounded-lg transition-all ${borderColor} ${bgColor} ${textColor} ${
                                    !showResult ? 'cursor-pointer' : 'cursor-default'
                                }`}
                            >
                                <div className="flex items-center justify-between">
                                    <span className="font-medium">{option.text}</span>
                                    {showResult && isCorrect && (
                                        <CheckCircle className="text-green-600" size={20} />
                                    )}
                                    {showResult && isWrong && (
                                        <XCircle className="text-red-600" size={20} />
                                    )}
                                </div>
                            </button>
                        );
                    })}
                </div>

                {/* Explanation */}
                {showResult && (
                    <div className={`p-4 rounded-lg border-2 mb-4 ${
                        currentQuestion.options[selectedAnswer].is_correct
                            ? 'bg-green-50 border-green-200'
                            : 'bg-red-50 border-red-200'
                    }`}>
                        <div className="flex items-start">
                            {currentQuestion.options[selectedAnswer].is_correct ? (
                                <CheckCircle className="text-green-600 mr-3 flex-shrink-0" size={24} />
                            ) : (
                                <XCircle className="text-red-600 mr-3 flex-shrink-0" size={24} />
                            )}
                            <div className="flex-1">
                                <p className={`font-semibold mb-2 ${
                                    currentQuestion.options[selectedAnswer].is_correct ? 'text-green-900' : 'text-red-900'
                                }`}>
                                    {currentQuestion.options[selectedAnswer].is_correct ? 'Correct!' : 'Incorrect'}
                                </p>
                                <p className={`text-sm ${
                                    currentQuestion.options[selectedAnswer].is_correct ? 'text-green-800' : 'text-red-800'
                                }`}>
                                    {currentQuestion.explanation}
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Action Buttons */}
                <div className="flex justify-between items-center">
                    <div className="text-sm text-gray-500">
                        Progress: {currentIndex + 1} / {questions.length}
                    </div>
                    <div className="flex space-x-3">
                        {!showResult ? (
                            <Button
                                onClick={handleSubmit}
                                disabled={selectedAnswer === null}
                            >
                                Submit Answer
                            </Button>
                        ) : currentIndex < questions.length - 1 ? (
                            <Button onClick={handleNext}>
                                Next Question
                            </Button>
                        ) : (
                            <Button onClick={handleRestart} className="bg-green-600 hover:bg-green-700">
                                <Award className="mr-2" size={16} />
                                Complete Session
                            </Button>
                        )}
                    </div>
                </div>
            </div>

            {/* Completion Message */}
            {currentIndex === questions.length - 1 && showResult && (
                <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl p-6 border border-indigo-200">
                    <div className="flex items-start">
                        <Award className="text-indigo-600 mr-4" size={32} />
                        <div>
                            <h4 className="font-semibold text-indigo-900 mb-2">Session Completed! 🎉</h4>
                            <p className="text-sm text-indigo-800 mb-3">
                                You completed all {questions.length} questions with {accuracy}% accuracy.
                                <br />
                                Score: {score.correct} correct, {score.incorrect} incorrect
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}