import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { LogIn, Zap, Brain, MessageCircle, BarChart2, Shield } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Input, Button } from '../App';

const LoginView = ({ navigate }) => {
    const [formData, setFormData] = useState({ email: '', password: '' });
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        if (message) setMessage('');
    };

    const validateForm = () => {
        if (!formData.email.includes('@')) {
            setMessage('Please enter a valid email address');
            return false;
        }
        if (formData.password.length < 6) {
            setMessage('Password must be at least 6 characters');
            return false;
        }
        return true;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validateForm()) return;

        setLoading(true);
        setMessage('');

        try {
            const result = await apiFetch('/auth/login', 'POST', {
                username: formData.email,
                password: formData.password
            });
            setMessage('Login successful! Redirecting...');
            setTimeout(() => navigate('dashboard', result), 500);
        } catch (error) {
            setMessage(`Login failed: ${error.message || 'Invalid credentials'}`);
            setFormData(prev => ({ ...prev, password: '' }));
        } finally {
            setLoading(false);
        }
    };

    const features = [
        { icon: Brain, label: 'AI-Powered MCQ Generation', desc: 'Auto-generate quizzes from your docs' },
        { icon: MessageCircle, label: 'Roleplay Simulations', desc: 'Practice with AI customers' },
        { icon: BarChart2, label: 'Performance Analytics', desc: 'Track progress over time' },
        { icon: Shield, label: 'Knowledge Verification', desc: 'RAG-powered fact checking' },
    ];

    return (
        <div className="flex w-full max-w-5xl mx-auto min-h-[520px] rounded-2xl overflow-hidden shadow-2xl shadow-stone-300/40">
            {/* Left Hero Panel */}
            <motion.div
                initial={{ opacity: 0, x: -30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
                className="hidden md:flex md:w-[42%] login-hero flex-col justify-between p-10 text-white relative"
            >
                {/* Decorative geometric shapes */}
                <div className="geo-shape geo-1" />
                <div className="geo-shape geo-2" />
                <div className="geo-shape geo-3" />

                <div className="relative z-10">
                    <div className="flex items-center space-x-2 mb-8">
                        <div className="w-9 h-9 bg-gradient-to-br from-blue-400 to-teal-400 rounded-lg flex items-center justify-center">
                            <Zap size={18} className="text-white" />
                        </div>
                        <span className="text-sm font-bold tracking-wide text-white/80">SALESFORGE AI</span>
                    </div>

                    <h2 className="text-3xl font-extrabold leading-tight mb-3">
                        Train Smarter.<br />
                        <span className="text-teal-400">Sell Better.</span>
                    </h2>
                    <p className="text-sm text-slate-300 leading-relaxed mb-8">
                        AI-powered sales training that adapts to your team's needs. Master objection handling, product knowledge, and closing techniques.
                    </p>
                </div>

                <div className="relative z-10 space-y-3">
                    {features.map((feat, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.4 + i * 0.1, duration: 0.4 }}
                            className="flex items-center space-x-3"
                        >
                            <div className="w-8 h-8 rounded-lg bg-white/[0.08] flex items-center justify-center flex-shrink-0">
                                <feat.icon size={15} className="text-teal-300" />
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-white/90">{feat.label}</p>
                                <p className="text-[11px] text-slate-400">{feat.desc}</p>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </motion.div>

            {/* Right Form Panel */}
            <motion.div
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, ease: 'easeOut', delay: 0.1 }}
                className="flex-1 bg-white p-8 md:p-10 flex flex-col justify-center"
            >
                <div className="mb-8">
                    <div className="flex items-center space-x-3 mb-2">
                        <div className="p-2 bg-blue-50 rounded-xl">
                            <LogIn size={20} className="text-blue-600" />
                        </div>
                        <h2 className="text-2xl font-bold text-stone-800">Welcome back</h2>
                    </div>
                    <p className="text-stone-500 text-sm ml-[44px]">Sign in to your account to continue</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    <Input
                        name="email"
                        type="email"
                        label="Email"
                        value={formData.email}
                        onChange={handleChange}
                        required
                        placeholder="you@example.com"
                    />
                    <Input
                        name="password"
                        type="password"
                        label="Password"
                        value={formData.password}
                        onChange={handleChange}
                        required
                        placeholder="Enter your password"
                    />
                    <Button type="submit" loading={loading}>
                        {loading ? 'Signing in...' : 'Sign In'}
                    </Button>
                </form>

                {message && (
                    <div className={`mt-4 p-3 rounded-xl text-sm font-medium ${message.includes('successful')
                            ? 'bg-teal-50 text-teal-700 border border-teal-200'
                            : 'bg-red-50 text-red-700 border border-red-200'
                        }`}>
                        {message}
                    </div>
                )}

                <div className="mt-6 pt-4 border-t border-stone-100 text-sm text-center space-y-2">
                    <p className="text-stone-500">
                        New Company?{' '}
                        <button
                            type="button"
                            onClick={() => navigate('org_create')}
                            className="text-blue-600 hover:text-blue-700 font-semibold"
                        >
                            Create Organization
                        </button>
                    </p>
                    <p className="text-stone-500">
                        Have an invite?{' '}
                        <button
                            type="button"
                            onClick={() => navigate('register')}
                            className="text-blue-600 hover:text-blue-700 font-semibold"
                        >
                            Complete Registration
                        </button>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export default LoginView;