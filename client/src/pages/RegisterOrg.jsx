import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Briefcase, Key, Building2, Users, Shield, Globe, CheckCircle, UserPlus, Lock, Mail } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import { Input, Button, Alert } from '../components/ui';

// kept for backward-compat with any import that uses roles
export const roles = ['trainee', 'trainer', 'manager', 'admin'];

// ── Create Organization ───────────────────────────────────────────────────────
export function OrgCreateView() {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({ name: '', admin_email: '', admin_password: '' });
    const [message, setMessage] = useState('');
    const [msgType, setMsgType] = useState('error');
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
            setMsgType('success');
            setMessage(`Organization "${org.name}" created! Redirecting to login…`);
            setFormData({ name: '', admin_email: '', admin_password: '' });
            setTimeout(() => navigate('/login'), 2000);
        } catch (error) {
            setMsgType('error');
            if (error.message.includes('already exists'))      setMessage('Organization name or admin email already exists.');
            else if (error.message.includes('8 characters'))   setMessage('Password must be at least 8 characters.');
            else                                                setMessage(error.message);
        } finally {
            setLoading(false);
        }
    };

    const BENEFITS = [
        { icon: Users,         label: 'Team Management',   desc: 'Invite & manage your sales team' },
        { icon: Shield,        label: 'Role-Based Access',  desc: 'Admin, manager, trainer & trainee roles' },
        { icon: Globe,         label: 'Knowledge Base',     desc: 'Upload docs, build your AI training hub' },
        { icon: CheckCircle,   label: 'AI-Powered Training', desc: 'MCQs, roleplay & performance analytics' },
    ];

    return (
        <div className="flex w-full max-w-4xl mx-auto rounded-2xl overflow-hidden shadow-2xl shadow-slate-900/20">
            {/* Left hero — teal */}
            <div className="hidden md:flex md:w-[42%] flex-col justify-between p-10 text-white relative overflow-hidden"
                style={{ background: 'linear-gradient(135deg, #0f172a 0%, #134e4a 50%, #0f172a 100%)' }}>
                <div className="absolute w-96 h-96 -top-16 -right-16 rounded-full opacity-20"
                    style={{ background: 'radial-gradient(circle, rgba(13,148,136,0.5), transparent 60%)', filter: 'blur(60px)' }} />

                <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-8">
                        <div className="w-8 h-8 bg-gradient-to-br from-teal-400 to-teal-600 rounded-lg flex items-center justify-center">
                            <Building2 size={16} className="text-white" />
                        </div>
                        <span className="text-xs font-bold tracking-widest text-white/60 uppercase">New Organization</span>
                    </div>
                    <h2 className="text-3xl font-extrabold leading-tight mb-3">
                        Build Your<br />
                        <span className="text-teal-400">Training Hub.</span>
                    </h2>
                    <p className="text-sm text-slate-300 leading-relaxed">
                        Set up your organization in seconds. Upload content, invite your team, and start AI-powered training.
                    </p>
                </div>

                <div className="relative z-10 space-y-3">
                    {BENEFITS.map(({ icon: Icon, label, desc }, i) => (
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

            {/* Right form */}
            <div className="flex-1 bg-white p-8 md:p-10 flex flex-col justify-center">
                <div className="mb-7">
                    <div className="flex items-center gap-3 mb-1.5">
                        <div className="p-2 bg-teal-50 rounded-xl">
                            <Briefcase size={18} className="text-teal-600" />
                        </div>
                        <h2 className="text-2xl font-bold text-slate-800">Create Organization</h2>
                    </div>
                    <p className="text-slate-400 text-sm ml-[44px]">Set up your company's training workspace</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <Input name="name" type="text" label="Organization Name" value={formData.name} onChange={handleChange} required placeholder="Acme Corporation" />
                    <Input name="admin_email" type="email" label="Admin Email" value={formData.admin_email} onChange={handleChange} required placeholder="admin@company.com" />
                    <Input name="admin_password" type="password" label="Admin Password (min 8 chars)" value={formData.admin_password} onChange={handleChange} required minLength={8} placeholder="••••••••" />
                    <Button type="submit" loading={loading} variant="teal" className="w-full">
                        {loading ? 'Creating…' : 'Register Organization'}
                    </Button>
                </form>

                {message && <Alert message={message} type={msgType} className="mt-4" />}

                <div className="mt-6 pt-5 border-t border-slate-100 text-sm text-center">
                    <p className="text-slate-500">
                        Already have an account?{' '}
                        <button onClick={() => navigate('/login')} className="text-blue-600 hover:text-blue-700 font-semibold">Sign In</button>
                    </p>
                </div>
            </div>
        </div>
    );
}

// ── Register via invite token ─────────────────────────────────────────────────
export function RegisterView() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [formData, setFormData] = useState({ token: '', password: '' });
    const [message, setMessage] = useState('');
    const [msgType, setMsgType] = useState('error');
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
            const cleaned = { token: (formData.token || '').trim(), password: formData.password };
            const result = await apiFetch('/auth/register', 'POST', cleaned);
            setMsgType('success');
            setMessage('Registration complete! Logging you in…');
            if (result.access_token) {
                login(result.access_token);
                setTimeout(() => navigate('/dashboard', { replace: true }), 1200);
            } else {
                setTimeout(() => navigate('/login'), 1500);
            }
        } catch (error) {
            setMsgType('error');
            if (error.message.toLowerCase().includes('expired') || error.message.toLowerCase().includes('invalid'))
                setMessage('Invalid or expired invite token. Make sure you copied the full token with no extra spaces.');
            else if (error.message.includes('8 characters'))
                setMessage('Password must be at least 8 characters.');
            else
                setMessage(error.message);
        } finally {
            setLoading(false);
        }
    };

    const STEPS = [
        { icon: Mail,         label: 'Receive Invite',  desc: 'Your admin sends you a token', num: '1' },
        { icon: Key,          label: 'Enter Token',      desc: 'Paste the invite code below',  num: '2' },
        { icon: Lock,         label: 'Set Password',     desc: 'Create your secure password',  num: '3' },
        { icon: CheckCircle,  label: 'Start Training',   desc: 'Access AI-powered modules',    num: '4' },
    ];

    return (
        <div className="flex w-full max-w-4xl mx-auto rounded-2xl overflow-hidden shadow-2xl shadow-slate-900/20">
            {/* Left hero — violet */}
            <div className="hidden md:flex md:w-[42%] flex-col justify-between p-10 text-white relative overflow-hidden"
                style={{ background: 'linear-gradient(135deg, #0f172a 0%, #2e1065 50%, #0f172a 100%)' }}>
                <div className="absolute w-96 h-96 -top-16 -right-16 rounded-full opacity-20"
                    style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.5), transparent 60%)', filter: 'blur(60px)' }} />

                <div className="relative z-10">
                    <div className="flex items-center gap-2 mb-8">
                        <div className="w-8 h-8 bg-gradient-to-br from-violet-400 to-violet-600 rounded-lg flex items-center justify-center">
                            <UserPlus size={16} className="text-white" />
                        </div>
                        <span className="text-xs font-bold tracking-widest text-white/60 uppercase">Team Invite</span>
                    </div>
                    <h2 className="text-3xl font-extrabold leading-tight mb-3">
                        Join Your<br />
                        <span className="text-violet-400">Team Today.</span>
                    </h2>
                    <p className="text-sm text-slate-300 leading-relaxed">
                        You've been invited to a SalesForge organization. Complete registration in two steps.
                    </p>
                </div>

                <div className="relative z-10 space-y-3">
                    {STEPS.map(({ icon: Icon, label, desc, num }, i) => (
                        <div key={i} className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-white/[0.08] flex items-center justify-center flex-shrink-0 text-xs font-bold text-violet-300">
                                {num}
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-white/90">{label}</p>
                                <p className="text-[11px] text-slate-400">{desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Right form */}
            <div className="flex-1 bg-white p-8 md:p-10 flex flex-col justify-center">
                <div className="mb-7">
                    <div className="flex items-center gap-3 mb-1.5">
                        <div className="p-2 bg-violet-50 rounded-xl">
                            <Key size={18} className="text-violet-600" />
                        </div>
                        <h2 className="text-2xl font-bold text-slate-800">Complete Registration</h2>
                    </div>
                    <p className="text-slate-400 text-sm ml-[44px]">Enter your invite token and set your password</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <Input name="token" type="text" label="Invite Token" value={formData.token} onChange={handleChange} required placeholder="Paste your invite token here" />
                    <Input name="password" type="password" label="New Password (min 8 chars)" value={formData.password} onChange={handleChange} required minLength={8} placeholder="••••••••" />
                    <Button type="submit" loading={loading} className="w-full !bg-violet-600 hover:!bg-violet-700">
                        {loading ? 'Registering…' : 'Set Password & Login'}
                    </Button>
                </form>

                {message && <Alert message={message} type={msgType} className="mt-4" />}

                <div className="mt-6 pt-5 border-t border-slate-100 text-sm text-center space-y-2">
                    <p className="text-slate-500">
                        Already registered?{' '}
                        <button onClick={() => navigate('/login')} className="text-blue-600 hover:text-blue-700 font-semibold">Sign In</button>
                    </p>
                    <p className="text-slate-500">
                        Need a new organization?{' '}
                        <button onClick={() => navigate('/org/create')} className="text-blue-600 hover:text-blue-700 font-semibold">Create One</button>
                    </p>
                </div>
            </div>
        </div>
    );
}
