import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Briefcase, Key, Zap, Building2, Users, Shield, Globe, CheckCircle, UserPlus, Lock, Mail } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Input, Button } from '../App';

const roles = ["admin", "manager", "trainer", "trainee"];

// ═══════════════════════════════════════════════════════════════
// Organization Creation View — Premium Split Layout
// ═══════════════════════════════════════════════════════════════
const OrgCreateView = ({ navigate }) => {
    const [formData, setFormData] = useState({ name: '', admin_email: '', admin_password: '' });
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage('');
        
        try {
            const org = await apiFetch('/orgs', 'POST', formData);
            setMessage(`✅ Organization "${org.name}" created successfully! Admin user registered. Redirecting to login...`);
            setFormData({ name: '', admin_email: '', admin_password: '' });
            setTimeout(() => navigate('/login'), 2000); 
        } catch (error) {
            console.error('Organization creation error:', error);
            if (error.message.includes('already exists')) {
                setMessage('❌ Organization name or admin email already exists.');
            } else if (error.message.includes('8 characters')) {
                setMessage('❌ Password must be at least 8 characters long.');
            } else {
                setMessage(`❌ Error: ${error.message}`);
            }
        } finally {
            setLoading(false);
        }
    };

    const benefits = [
        { icon: Users, label: 'Team Management', desc: 'Invite & manage your sales team' },
        { icon: Shield, label: 'Role-Based Access', desc: 'Admin, manager, trainer & trainee roles' },
        { icon: Globe, label: 'Knowledge Base', desc: 'Upload docs, build your AI training hub' },
        { icon: CheckCircle, label: 'AI-Powered Training', desc: 'MCQs, roleplay & performance analytics' },
    ];

    return (
        <div className="flex w-full max-w-5xl mx-auto min-h-[560px] rounded-2xl overflow-hidden shadow-2xl shadow-stone-300/40">
            {/* Left Hero Panel — Teal theme for Org creation */}
            <motion.div
                initial={{ opacity: 0, x: -30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
                className="hidden md:flex md:w-[42%] flex-col justify-between p-10 text-white relative overflow-hidden"
                style={{ background: 'linear-gradient(135deg, #0f172a 0%, #134e4a 50%, #0f172a 100%)' }}
            >
                {/* Decorative blobs */}
                <div className="absolute w-[400px] h-[400px] -top-[15%] -right-[15%] rounded-full opacity-20" style={{ background: 'radial-gradient(circle, rgba(13, 148, 136, 0.5), transparent 60%)', filter: 'blur(60px)' }} />
                <div className="absolute w-[300px] h-[300px] -bottom-[10%] -left-[10%] rounded-full opacity-15" style={{ background: 'radial-gradient(circle, rgba(217, 119, 6, 0.4), transparent 60%)', filter: 'blur(60px)' }} />

                {/* Floating geometric shapes */}
                <div className="absolute top-[18%] right-[12%] w-[160px] h-[160px] border border-white/[0.06] rounded-3xl rotate-12 animate-float" style={{ background: 'rgba(13, 148, 136, 0.08)' }} />
                <div className="absolute bottom-[22%] left-[12%] w-[100px] h-[100px] border border-white/[0.06] rounded-2xl -rotate-6 animate-float" style={{ background: 'rgba(217, 119, 6, 0.06)', animationDelay: '1s' }} />

                <div className="relative z-10">
                    <div className="flex items-center space-x-2 mb-8">
                        <div className="w-9 h-9 bg-gradient-to-br from-teal-400 to-teal-600 rounded-lg flex items-center justify-center">
                            <Building2 size={18} className="text-white" />
                        </div>
                        <span className="text-sm font-bold tracking-wide text-white/80">NEW ORGANIZATION</span>
                    </div>

                    <h2 className="text-3xl font-extrabold leading-tight mb-3">
                        Build Your<br />
                        <span className="text-teal-400">Training Hub.</span>
                    </h2>
                    <p className="text-sm text-slate-300 leading-relaxed mb-8">
                        Set up your organization in seconds. Upload content, invite your team, and start AI-powered sales training.
                    </p>
                </div>

                <div className="relative z-10 space-y-3">
                    {benefits.map((feat, i) => (
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
                        <div className="p-2 bg-teal-50 rounded-xl">
                            <Briefcase size={20} className="text-teal-600" />
                        </div>
                        <h2 className="text-2xl font-bold text-stone-800">Create Organization</h2>
                    </div>
                    <p className="text-stone-500 text-sm ml-[44px]">Set up your company's training workspace</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    <Input 
                        name="name" 
                        type="text" 
                        label="Organization Name" 
                        value={formData.name} 
                        onChange={handleChange} 
                        required 
                        placeholder="e.g., Acme Corporation"
                    />
                    <Input 
                        name="admin_email" 
                        type="email" 
                        label="Admin Email" 
                        value={formData.admin_email} 
                        onChange={handleChange} 
                        required 
                        placeholder="admin@example.com"
                    />
                    <Input 
                        name="admin_password" 
                        type="password" 
                        label="Admin Password (min 8 chars)" 
                        value={formData.admin_password} 
                        onChange={handleChange} 
                        required 
                        minLength={8}
                        placeholder="••••••••"
                    />
                    <Button type="submit" loading={loading} disabled={loading} className="!from-teal-600 !to-teal-700 hover:!from-teal-700 hover:!to-teal-800 !shadow-teal-600/20">
                        {loading ? 'Creating...' : 'Register Organization'}
                    </Button>
                </form>

                {message && (
                    <div className={`mt-5 p-3 rounded-xl text-sm font-medium ${
                        message.startsWith('❌')
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : 'bg-teal-50 text-teal-700 border border-teal-200'
                    }`}>
                        {message}
                    </div>
                )}

                <div className="mt-6 pt-4 border-t border-stone-100 text-sm text-center">
                    <p className="text-stone-500">
                        Already have an account?{' '}
                        <button
                            type="button"
                            onClick={() => navigate('login')}
                            className="text-blue-600 hover:text-blue-700 font-semibold"
                        >
                            Sign In
                        </button>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

// ═══════════════════════════════════════════════════════════════
// User Registration via Invite Token — Premium Split Layout
// ═══════════════════════════════════════════════════════════════
const RegisterView = ({ navigate }) => {
    const [formData, setFormData] = useState({ token: '', password: '' });
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage('');
        
        try {
            const result = await apiFetch('/auth/register', 'POST', formData);
            setMessage('✅ Registration complete! Logging you in...');
            setFormData({ token: '', password: '' });
            setTimeout(() => navigate('/dashboard', result), 1500);
        } catch (error) {
            console.error('Registration error:', error);
            if (error.message.includes('expired') || error.message.includes('invalid')) {
                setMessage('❌ Invalid or expired invite token.');
            } else if (error.message.includes('8 characters')) {
                setMessage('❌ Password must be at least 8 characters long.');
            } else {
                setMessage(`❌ Error: ${error.message}`);
            }
        } finally {
            setLoading(false);
        }
    };

    const steps = [
        { icon: Mail, label: 'Receive Invite', desc: 'Your admin sends you a token', num: '1' },
        { icon: Key, label: 'Enter Token', desc: 'Paste the invite code below', num: '2' },
        { icon: Lock, label: 'Set Password', desc: 'Create your secure password', num: '3' },
        { icon: CheckCircle, label: 'Start Training', desc: 'Access AI-powered modules', num: '4' },
    ];

    return (
        <div className="flex w-full max-w-5xl mx-auto min-h-[480px] rounded-2xl overflow-hidden shadow-2xl shadow-stone-300/40">
            {/* Left Hero Panel — Gold/Amber theme for invite registration */}
            <motion.div
                initial={{ opacity: 0, x: -30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
                className="hidden md:flex md:w-[42%] flex-col justify-between p-10 text-white relative overflow-hidden"
                style={{ background: 'linear-gradient(135deg, #0f172a 0%, #2e1065 50%, #0f172a 100%)' }}
            >
                {/* Decorative blobs */}
                <div className="absolute w-[400px] h-[400px] -top-[15%] -right-[15%] rounded-full opacity-20" style={{ background: 'radial-gradient(circle, rgba(139, 92, 246, 0.5), transparent 60%)', filter: 'blur(60px)' }} />
                <div className="absolute w-[300px] h-[300px] -bottom-[10%] -left-[10%] rounded-full opacity-15" style={{ background: 'radial-gradient(circle, rgba(37, 99, 235, 0.3), transparent 60%)', filter: 'blur(60px)' }} />

                {/* Floating shapes */}
                <div className="absolute top-[20%] right-[15%] w-[140px] h-[140px] border border-white/[0.06] rounded-3xl rotate-12 animate-float" style={{ background: 'rgba(139, 92, 246, 0.08)' }} />
                <div className="absolute bottom-[25%] left-[10%] w-[80px] h-[80px] border border-white/[0.06] rounded-full animate-float" style={{ background: 'rgba(37, 99, 235, 0.06)', animationDelay: '1.5s' }} />

                <div className="relative z-10">
                    <div className="flex items-center space-x-2 mb-8">
                        <div className="w-9 h-9 bg-gradient-to-br from-violet-400 to-violet-600 rounded-lg flex items-center justify-center">
                            <UserPlus size={18} className="text-white" />
                        </div>
                        <span className="text-sm font-bold tracking-wide text-white/80">TEAM INVITE</span>
                    </div>

                    <h2 className="text-3xl font-extrabold leading-tight mb-3">
                        Join Your<br />
                        <span className="text-violet-400">Team Today.</span>
                    </h2>
                    <p className="text-sm text-slate-300 leading-relaxed mb-8">
                        You've been invited to join a sales training organization. Complete your registration in just two steps.
                    </p>
                </div>

                <div className="relative z-10 space-y-3">
                    {steps.map((step, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: 0.4 + i * 0.1, duration: 0.4 }}
                            className="flex items-center space-x-3"
                        >
                            <div className="w-8 h-8 rounded-lg bg-white/[0.08] flex items-center justify-center flex-shrink-0 text-xs font-bold text-violet-300">
                                {step.num}
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-white/90">{step.label}</p>
                                <p className="text-[11px] text-slate-400">{step.desc}</p>
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
                        <div className="p-2 bg-violet-50 rounded-xl">
                            <Key size={20} className="text-violet-600" />
                        </div>
                        <h2 className="text-2xl font-bold text-stone-800">Complete Registration</h2>
                    </div>
                    <p className="text-stone-500 text-sm ml-[44px]">Enter your invite token and set your password</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    <Input 
                        name="token" 
                        type="text" 
                        label="Invite Token" 
                        value={formData.token} 
                        onChange={handleChange} 
                        required 
                        placeholder="Paste your invite token here"
                    />
                    <Input 
                        name="password" 
                        type="password" 
                        label="New Password (min 8 chars)" 
                        value={formData.password} 
                        onChange={handleChange} 
                        required 
                        minLength={8}
                        placeholder="••••••••"
                    />
                    <Button type="submit" loading={loading} disabled={loading} className="!from-violet-600 !to-violet-700 hover:!from-violet-700 hover:!to-violet-800 !shadow-violet-600/20">
                        {loading ? 'Registering...' : 'Set Password & Login'}
                    </Button>
                </form>

                {message && (
                    <div className={`mt-5 p-3 rounded-xl text-sm font-medium ${
                        message.startsWith('❌')
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : 'bg-teal-50 text-teal-700 border border-teal-200'
                    }`}>
                        {message}
                    </div>
                )}

                <div className="mt-6 pt-4 border-t border-stone-100 text-sm text-center space-y-2">
                    <p className="text-stone-500">
                        Already registered?{' '}
                        <button
                            type="button"
                            onClick={() => navigate('login')}
                            className="text-blue-600 hover:text-blue-700 font-semibold"
                        >
                            Sign In
                        </button>
                    </p>
                    <p className="text-stone-500">
                        Need a new organization?{' '}
                        <button
                            type="button"
                            onClick={() => navigate('org_create')}
                            className="text-blue-600 hover:text-blue-700 font-semibold"
                        >
                            Create One
                        </button>
                    </p>
                </div>
            </motion.div>
        </div>
    );
};

export { OrgCreateView, RegisterView, roles };