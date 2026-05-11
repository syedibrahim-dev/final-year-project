import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, Brain, MessageCircle, BarChart2, Shield } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { Input, Button, Alert } from '../components/ui';

const FEATURES = [
    { icon: Brain,         label: 'AI-Powered MCQ Generation',  desc: 'Auto-generate quizzes from your docs' },
    { icon: MessageCircle, label: 'Roleplay Simulations',        desc: 'Practice with AI customers' },
    { icon: BarChart2,     label: 'Performance Analytics',       desc: 'Track progress over time' },
    { icon: Shield,        label: 'Knowledge Verification',      desc: 'RAG-powered fact checking' },
];

export default function LoginView() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [formData, setFormData] = useState({ email: '', password: '' });
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        if (message) setMessage('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.email.includes('@')) { setMessage('Please enter a valid email address'); return; }
        if (formData.password.length < 6)  { setMessage('Password must be at least 6 characters'); return; }

        setLoading(true);
        try {
            const result = await apiFetch('/auth/login', 'POST', {
                username: formData.email,
                password: formData.password,
            });
            login(result.access_token);
            navigate('/dashboard', { replace: true });
        } catch (error) {
            setMessage(error.message || 'Invalid credentials. Please try again.');
            setFormData(prev => ({ ...prev, password: '' }));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex w-full max-w-4xl mx-auto rounded-2xl overflow-hidden shadow-2xl shadow-slate-900/20">
            {/* Left — hero panel */}
            <div className="hidden md:flex md:w-[42%] login-hero flex-col justify-between p-10 text-white relative">
                <div className="geo-shape geo-1" />
                <div className="geo-shape geo-2" />
                <div className="geo-shape geo-3" />

                <div className="relative z-10">
                    <p className="text-xs font-bold tracking-widest text-white/50 uppercase mb-8">SalesForge AI</p>
                    <h2 className="text-3xl font-extrabold leading-tight mb-3">
                        Train Smarter.<br />
                        <span className="text-teal-400">Sell Better.</span>
                    </h2>
                    <p className="text-sm text-slate-300 leading-relaxed">
                        AI-powered sales training that adapts to your team. Master objection handling, product knowledge, and closing.
                    </p>
                </div>

                <div className="relative z-10 space-y-3">
                    {FEATURES.map(({ icon: Icon, label, desc }, i) => (
                        <div key={i} className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-white/[0.08] flex items-center justify-center flex-shrink-0">
                                <Icon size={14} className="text-teal-300" />
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-white/90">{label}</p>
                                <p className="text-[11px] text-slate-400">{desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Right — form panel */}
            <div className="flex-1 bg-white p-8 md:p-10 flex flex-col justify-center">
                <div className="mb-7">
                    <div className="flex items-center gap-3 mb-1.5">
                        <div className="p-2 bg-blue-50 rounded-xl">
                            <LogIn size={18} className="text-blue-600" />
                        </div>
                        <h2 className="text-2xl font-bold text-slate-800">Welcome back</h2>
                    </div>
                    <p className="text-slate-400 text-sm ml-[44px]">Sign in to your account</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <Input name="email" type="email" label="Email" value={formData.email} onChange={handleChange} required placeholder="you@company.com" />
                    <Input name="password" type="password" label="Password" value={formData.password} onChange={handleChange} required placeholder="••••••••" />
                    <Button type="submit" loading={loading} className="w-full mt-2">
                        {loading ? 'Signing in...' : 'Sign In'}
                    </Button>
                </form>

                {message && <Alert message={message} type="error" className="mt-4" />}

                <div className="mt-6 pt-5 border-t border-slate-100 text-sm text-center space-y-2">
                    <p className="text-slate-500">
                        New company?{' '}
                        <button onClick={() => navigate('/org/create')} className="text-blue-600 hover:text-blue-700 font-semibold">
                            Create Organization
                        </button>
                    </p>
                    <p className="text-slate-500">
                        Have an invite token?{' '}
                        <button onClick={() => navigate('/register')} className="text-blue-600 hover:text-blue-700 font-semibold">
                            Complete Registration
                        </button>
                    </p>
                </div>
            </div>
        </div>
    );
}
