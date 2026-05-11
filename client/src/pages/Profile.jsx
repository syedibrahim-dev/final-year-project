import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Brain, MessageCircle, Sparkles, Search, ChevronRight, Lightbulb } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { PageHeader } from '../components/ui';

export default function ProfilePage() {
    const { user } = useAuth();
    const navigate = useNavigate();

    if (!user) return null;

    const quickActions = [
        { icon: Brain,         label: 'MCQ Practice',    desc: 'Test your knowledge',  color: 'text-blue-600',   bg: 'bg-blue-50 hover:bg-blue-100',   border: 'border-blue-100 hover:border-blue-200',   to: '/mcq' },
        { icon: MessageCircle, label: 'AI Roleplay',      desc: 'Practice selling',      color: 'text-teal-600',   bg: 'bg-teal-50 hover:bg-teal-100',   border: 'border-teal-100 hover:border-teal-200',   to: '/roleplay' },
        { icon: Sparkles,      label: 'Knowledge Chat',   desc: 'Ask your docs',         color: 'text-violet-600', bg: 'bg-violet-50 hover:bg-violet-100', border: 'border-violet-100 hover:border-violet-200', to: '/knowledge-chat' },
        { icon: Search,        label: 'Search Docs',      desc: 'Find content',          color: 'text-amber-600',  bg: 'bg-amber-50 hover:bg-amber-100',  border: 'border-amber-100 hover:border-amber-200',  to: '/search' },
    ];

    const details = [
        { label: 'Email',        value: user.email },
        { label: 'Full Name',    value: user.full_name || 'Not set' },
        { label: 'User ID',      value: `#${user.id}` },
        { label: 'Organization', value: `Org #${user.organization_id}` },
        { label: 'Role',         value: user.role.charAt(0).toUpperCase() + user.role.slice(1) },
        { label: 'Status',       value: user.is_active ? 'Active' : 'Inactive' },
        { label: 'Member Since', value: new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) },
    ];

    return (
        <div>
            <PageHeader
                title="My Profile"
                subtitle="Your account overview"
                backTo="/dashboard"
                backLabel="Dashboard"
            />

            {/* Quick actions */}
            <div className="mb-8">
                <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Quick Actions</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {quickActions.map(action => (
                        <button
                            key={action.to}
                            onClick={() => navigate(action.to)}
                            className={`${action.bg} ${action.border} border rounded-xl p-4 text-left transition-all duration-200 group cursor-pointer`}
                        >
                            <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 ${action.bg.split(' ')[0]}`}>
                                <action.icon size={18} className={action.color} />
                            </div>
                            <p className="text-sm font-bold text-slate-800">{action.label}</p>
                            <p className="text-[11px] text-slate-400 mt-0.5">{action.desc}</p>
                        </button>
                    ))}
                </div>
            </div>

            {/* Account details + tip */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {/* Details table */}
                <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
                    <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-100">
                        <h3 className="text-sm font-semibold text-slate-700">Account Details</h3>
                    </div>
                    {details.map((item, i) => (
                        <div key={i} className="flex items-center justify-between px-5 py-3 border-b border-slate-50 last:border-0">
                            <span className="text-sm text-slate-500">{item.label}</span>
                            <span className="text-sm font-medium text-slate-800">{item.value}</span>
                        </div>
                    ))}
                </div>

                {/* Pro tip */}
                <div className="bg-gradient-to-br from-slate-50 to-blue-50/40 rounded-xl border border-slate-200 p-5 flex flex-col">
                    <div className="w-9 h-9 bg-amber-100 rounded-xl flex items-center justify-center mb-3">
                        <Lightbulb size={18} className="text-amber-600" />
                    </div>
                    <h4 className="font-bold text-slate-800 text-sm mb-1">Pro Tip</h4>
                    <p className="text-xs text-slate-500 leading-relaxed flex-1">
                        Use the <strong>AI Roleplay</strong> module daily to sharpen objection handling.
                        The AI adapts to your skill level and provides real-time coaching.
                    </p>
                    <button
                        onClick={() => navigate('/roleplay')}
                        className="mt-4 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors"
                    >
                        Try Roleplay <ChevronRight size={11} />
                    </button>
                </div>
            </div>
        </div>
    );
}
