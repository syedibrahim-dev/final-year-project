import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Home, UserPlus, Upload, Loader2, Brain,
    BarChart2, FileText, FolderOpen, Search, LogOut, Sparkles, Zap,
    MessageSquare, MessageCircle, ChevronRight, Shield, Rocket, BookOpen, Target, Lightbulb,
    // Module 5: Automation icons (added by friend's branch)
    Activity, Users, TrendingUp, Package, Box,
    // Integrations + Customer Analytics
    Plug, UserCheck
} from 'lucide-react';
import { apiFetch, auth as authApi } from './utils/api';

// Page Imports
import LoginView from './pages/Login';
import { OrgCreateView, RegisterView, roles } from './pages/RegisterOrg';
import ContentUploadView from './pages/ContentUpload';
import ContentRetrieverView from './pages/ContentRetriever';
import ContentManagerView from './pages/ContentManager';
import KnowledgeChatbot from './pages/KnowledgeChatbot';

// MCQ Features
import MCQPracticeView from './pages/MCQPractice';
import MCQTestCreator from './pages/MCQTestCreator';
import PerformanceDashboard from './pages/PerformanceDashboard';

// Roleplay Features
import RoleplayPersonas from './pages/RoleplayPersonas';
import RoleplayChat from './pages/RoleplayChat';
import RoleplayFeedback from './pages/RoleplayFeedback';

// Module 5: Automation (from friend's branch)
// MarketingPostCreator import removed — module hidden from UI but file retained.
// Re-enable: uncomment next line + the nav entry + the switch case in DashboardView.
// import MarketingPostCreator from './pages/MarketingPostCreator';
import InventoryManagerView from './pages/InventoryManager';
import TransactionAnalytics from './pages/TransactionAnalytics';
import LeadManager from './pages/LeadManager';

// Integrations + Customer Analytics
import IntegrationsPage from './pages/IntegrationsPage';
import CustomerAnalyticsPage from './pages/CustomerAnalyticsPage';

// ===== Shared UI Components =====
export const Card = ({ title, icon, children, onClick, className = '' }) => (
    <div
        onClick={onClick}
        className={`max-w-md mx-auto p-6 md:p-8 bg-white rounded-2xl shadow-lg shadow-stone-200/50 border border-stone-200/80 hover:shadow-xl hover:border-blue-300/50 transition-all duration-300 ${className}`}
    >
        <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-stone-100">
            <div className="p-2.5 bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-xl shadow-lg shadow-blue-500/20">
                {icon}
            </div>
            <h2 className="text-xl font-bold text-stone-800">
                {title}
            </h2>
        </div>
        {children}
    </div>
);

export const Input = ({ name, label, type, value, onChange, required = false, disabled = false, placeholder = '' }) => (
    <div>
        <label htmlFor={name} className="block text-sm font-semibold text-stone-600 mb-1.5">
            {label}
        </label>
        <input
            id={name}
            name={name}
            type={type}
            value={value}
            onChange={onChange}
            required={required}
            disabled={disabled}
            placeholder={placeholder}
            className="w-full px-4 py-3 border border-stone-300 rounded-xl bg-stone-50/50 focus:bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all duration-200 placeholder:text-stone-400 text-sm text-stone-800"
        />
    </div>
);

export const Select = ({ name, label, value, options, onChange, required = false, disabled = false }) => (
    <div>
        <label htmlFor={name} className="block text-sm font-semibold text-stone-600 mb-1.5">
            {label}
        </label>
        <select
            id={name}
            name={name}
            value={value}
            onChange={onChange}
            required={required}
            disabled={disabled}
            className="w-full px-4 py-3 border border-stone-300 rounded-xl bg-stone-50/50 text-stone-800 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all duration-200 cursor-pointer text-sm"
        >
            {options.map(option => (
                <option key={option} value={option}>{option.charAt(0).toUpperCase() + option.slice(1)}</option>
            ))}
        </select>
    </div>
);

export const Button = ({ children, onClick, type = 'button', loading = false, disabled = false, className = '' }) => (
    <button
        type={type}
        onClick={onClick}
        disabled={loading || disabled}
        className={`w-full flex justify-center items-center py-3 px-6 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:ring-offset-2 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-600/20 hover:shadow-xl hover:shadow-blue-600/25 active:scale-[0.98] ${className}`}
    >
        {loading && (
            <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" />
        )}
        {children}
    </button>
);

// ===== Sidebar Nav Item (with Framer Motion) =====
const NavItem = ({ onClick, active, icon, label, index = 0 }) => (
    <motion.button
        onClick={onClick}
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: index * 0.05, type: 'spring', stiffness: 300, damping: 24 }}
        whileHover={{ x: 4 }}
        whileTap={{ scale: 0.97 }}
        className={`flex items-center space-x-3 w-full px-3 py-2.5 rounded-xl transition-colors duration-200 text-[13px] font-semibold group relative ${active
            ? 'bg-teal-600 text-white shadow-lg shadow-teal-900/40'
            : 'text-slate-300 hover:bg-white/[0.06] hover:text-white'
            }`}
    >
        {active && (
            <motion.div
                layoutId="nav-active-indicator"
                className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-teal-300 rounded-r-full"
                transition={{ type: 'spring', stiffness: 380, damping: 28 }}
            />
        )}
        <div className={`flex-shrink-0 ${active ? 'text-white' : 'text-slate-400 group-hover:text-teal-400'} transition-colors`}>
            {React.cloneElement(icon, { size: 18 })}
        </div>
        <span className="truncate">{label}</span>
        {active && (
            <ChevronRight size={14} className="ml-auto text-teal-200" />
        )}
    </motion.button>
);

// ===== Sidebar Section Header =====
const NavSection = ({ label }) => (
    <div className="pt-5 pb-1.5 px-3">
        <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-teal-400/60">
            {label}
        </p>
    </div>
);

// ===== Profile View =====
const ProfileView = ({ user, onNavigate }) => (
    <div>
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="mb-8"
        >
            <h3 className="text-3xl font-bold text-stone-800 mb-1">
                Welcome back, {user.full_name || user.email.split('@')[0]} 👋
            </h3>
            <p className="text-stone-500">Here's your profile overview</p>
        </motion.div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            {[
                { bg: 'from-blue-600 to-blue-700', shadow: 'shadow-blue-500/20', accent: 'text-blue-200', label: 'Role', value: user.role.charAt(0).toUpperCase() + user.role.slice(1), size: 'text-2xl' },
                { bg: 'from-teal-500 to-teal-700', shadow: 'shadow-teal-500/20', accent: 'text-teal-200', label: 'Status', value: user.is_active ? '🟢 Active' : '🔴 Inactive', size: 'text-2xl' },
                { bg: 'from-violet-500 to-violet-700', shadow: 'shadow-violet-500/20', accent: 'text-violet-200', label: 'Member Since', value: new Date(user.created_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' }), size: 'text-lg' },
            ].map((card, i) => (
                <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 20, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ delay: 0.1 + i * 0.1, type: 'spring', stiffness: 260, damping: 20 }}
                    whileHover={{ y: -4, transition: { duration: 0.2 } }}
                    className={`bg-gradient-to-br ${card.bg} p-5 rounded-2xl text-white shadow-lg ${card.shadow} cursor-default`}
                >
                    <p className={`${card.accent} text-xs font-medium uppercase tracking-wide`}>{card.label}</p>
                    <p className={`${card.size} font-bold mt-1`}>{card.value}</p>
                </motion.div>
            ))}
        </div>

        {/* Quick Actions */}
        <div className="mb-8">
            <h4 className="text-sm font-bold text-stone-500 uppercase tracking-wide mb-3">Quick Actions</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                    { icon: Brain, label: 'MCQ Practice', desc: 'Test your knowledge', color: 'text-blue-600', bg: 'bg-blue-50 hover:bg-blue-100', border: 'border-blue-100 hover:border-blue-200', view: 'mcq-practice' },
                    { icon: MessageCircle, label: 'AI Roleplay', desc: 'Practice selling', color: 'text-teal-600', bg: 'bg-teal-50 hover:bg-teal-100', border: 'border-teal-100 hover:border-teal-200', view: 'roleplay' },
                    { icon: Sparkles, label: 'Knowledge Chat', desc: 'Ask your docs', color: 'text-violet-600', bg: 'bg-violet-50 hover:bg-violet-100', border: 'border-violet-100 hover:border-violet-200', view: 'knowledge-chat' },
                    { icon: Search, label: 'Search Docs', desc: 'Find content', color: 'text-amber-600', bg: 'bg-amber-50 hover:bg-amber-100', border: 'border-amber-100 hover:border-amber-200', view: 'search' },
                ].map((action, i) => (
                    <motion.button
                        key={i}
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 + i * 0.08, type: 'spring', stiffness: 260, damping: 22 }}
                        whileHover={{ y: -3, transition: { duration: 0.2 } }}
                        whileTap={{ scale: 0.97 }}
                        onClick={() => onNavigate && onNavigate(action.view)}
                        className={`${action.bg} ${action.border} border rounded-2xl p-4 text-left transition-all duration-200 group cursor-pointer`}
                    >
                        <div className={`w-10 h-10 rounded-xl ${action.bg.split(' ')[0]} flex items-center justify-center mb-3`}>
                            <action.icon size={20} className={action.color} />
                        </div>
                        <p className="text-sm font-bold text-stone-800 group-hover:text-stone-900">{action.label}</p>
                        <p className="text-[11px] text-stone-400 mt-0.5">{action.desc}</p>
                    </motion.button>
                ))}
            </div>
        </div>

        {/* Account Details + Pro Tip side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Account Details — takes 2 cols */}
            <div className="lg:col-span-2 bg-white rounded-2xl border border-stone-200 overflow-hidden shadow-sm">
                <div className="px-6 py-4 bg-stone-50 border-b border-stone-100">
                    <h4 className="font-semibold text-stone-700 text-sm">Account Details</h4>
                </div>
                {[
                    { label: 'Email', value: user.email },
                    { label: 'Full Name', value: user.full_name || 'Not set' },
                    { label: 'User ID', value: `#${user.id}` },
                    { label: 'Organization', value: `Org #${user.organization_id}` },
                ].map((item, i) => (
                    <div key={i} className="flex items-center justify-between px-6 py-3.5 border-b border-stone-50 last:border-0 hover:bg-blue-50/30 transition-colors">
                        <span className="text-sm text-stone-500">{item.label}</span>
                        <span className="text-sm font-medium text-stone-800">{item.value}</span>
                    </div>
                ))}
            </div>

            {/* Pro Tip Card */}
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.5, type: 'spring', stiffness: 260, damping: 22 }}
                className="bg-gradient-to-br from-stone-50 to-blue-50/50 rounded-2xl border border-stone-200 p-5 flex flex-col"
            >
                <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center mb-3">
                    <Lightbulb size={20} className="text-amber-600" />
                </div>
                <h4 className="font-bold text-stone-800 text-sm mb-1">Pro Tip</h4>
                <p className="text-xs text-stone-500 leading-relaxed flex-1">
                    Try the <strong>AI Roleplay</strong> module to practice handling objections. The AI adapts to your skill level and provides real-time coaching.
                </p>
                <button
                    onClick={() => onNavigate && onNavigate('roleplay')}
                    className="mt-4 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors"
                >
                    Try Roleplay <ChevronRight size={12} />
                </button>
            </motion.div>
        </div>
    </div>
);

// ===== Invite User View =====
const InviteUserView = ({ user, token }) => {
    const [formData, setFormData] = useState({ email: '', role: 'trainee' });
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState('');

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleInvite = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage('');
        try {
            const url = `/orgs/${user.organization_id}/users/invite?email=${encodeURIComponent(formData.email)}&role=${formData.role}`;
            const response = await apiFetch(url, 'POST', null, token);
            setMessage(`Success! User invited with role '${formData.role}'. Invite Token: ${response.invite_token || response.token}`);
            setFormData({ email: '', role: 'trainee' });
        } catch (error) {
            setMessage(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="animate-fadeInUp">
            <div className="mb-8">
                <h3 className="text-3xl font-bold text-stone-800 mb-1">Invite Team Member</h3>
                <p className="text-stone-500">Send an invitation to join your organization</p>
            </div>

            <form onSubmit={handleInvite} className="space-y-5 max-w-lg">
                <Input
                    name="email"
                    type="email"
                    label="Email Address"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    placeholder="colleague@company.com"
                />
                <Select
                    name="role"
                    label="Assign Role"
                    value={formData.role}
                    options={roles}
                    onChange={handleChange}
                    required
                />
                <Button type="submit" loading={loading}>
                    {loading ? 'Sending...' : (
                        <><UserPlus size={16} className="mr-2" /> Generate Invite</>
                    )}
                </Button>
            </form>

            {message && (
                <div className={`mt-6 p-4 rounded-xl text-sm ${message.startsWith('Error')
                    ? 'bg-red-50 text-red-700 border border-red-200'
                    : 'bg-teal-50 text-teal-700 border border-teal-200'
                    }`}>
                    <p className="font-semibold mb-1">{message.startsWith('Success') ? '✓ Invitation Sent' : '✕ Failed'}</p>
                    <p className="text-xs font-mono opacity-80 break-all">{message}</p>
                </div>
            )}
        </div>
    );
};

// ===== Dashboard Layout =====
const DashboardView = ({ token, user, logout }) => {
    const [view, setView] = useState('profile');
    const [sessionData, setSessionData] = useState(null);
    const [nlpData, setNlpData] = useState(null);
    const [conversionHistory, setConversionHistory] = useState(null);
    // Marketing gen state lives here so it survives sidebar navigation (from friend's branch)
    const [marketingGenState, setMarketingGenState] = useState({
        jobId: null, loading: false, status: '', image: null,
    });

    if (!user) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center">
                    <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-teal-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-500/30 animate-pulse">
                        <Loader2 className="animate-spin h-8 w-8 text-white" />
                    </div>
                    <p className="text-stone-500 font-medium">Loading dashboard...</p>
                </div>
            </div>
        );
    }

    const Sidebar = () => (
        <nav className="flex flex-col h-full sidebar-glass rounded-2xl p-4 text-white shadow-xl shadow-slate-900/50">
            {/* Brand */}
            <div className="flex items-center space-x-3 px-3 pt-2 pb-5 border-b border-white/[0.06] mb-2">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-teal-500 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30">
                    <Zap size={20} className="text-white" />
                </div>
                <div>
                    <h3 className="text-base font-bold text-white tracking-tight">SalesForge AI</h3>
                    <p className="text-[11px] text-teal-300 font-medium">{user.role.toUpperCase()}</p>
                </div>
            </div>

            {/* User badge */}
            <div className="px-3 py-3 rounded-xl bg-white/[0.05] border border-white/[0.05] mb-4">
                <div className="flex items-center space-x-2.5">
                    <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-teal-500 rounded-lg flex items-center justify-center text-white text-sm font-bold shadow-md">
                        {(user.full_name || user.email)[0].toUpperCase()}
                    </div>
                    <div className="min-w-0">
                        <p className="text-sm font-semibold text-white truncate">{user.full_name || user.email.split('@')[0]}</p>
                        <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
                    </div>
                </div>
            </div>

            <NavSection label="Overview" />
            <NavItem onClick={() => setView('profile')} active={view === 'profile'} icon={<Home />} label="My Profile" index={0} />

            <NavSection label="Training" />
            <NavItem onClick={() => setView('mcq-practice')} active={view === 'mcq-practice'} icon={<Brain />} label="MCQ Practice" index={1} />
            <NavItem onClick={() => setView('roleplay')} active={view === 'roleplay'} icon={<MessageCircle />} label="AI Roleplay" index={2} />
            <NavItem onClick={() => setView('search')} active={view === 'search'} icon={<Search />} label="Search Knowledge" index={3} />
            <NavItem
                onClick={() => setView('knowledge-chat')}
                active={view === 'knowledge-chat'}
                icon={<MessageSquare />}
                label="Knowledge Chat"
                index={4}
            />

            {(['admin', 'manager'].includes(user.role)) && (
                <>
                    {/* Marketing Posts UI removed — module incomplete. Re-enable by
                        uncommenting the NavSection below + corresponding switch case +
                        import. MarketingPostCreator.jsx itself is intact. */}
                    {/*
                    <NavSection label="Marketing" />
                    <NavItem onClick={() => setView('marketing-posts')} active={view === 'marketing-posts'} icon={<Sparkles />} label="Marketing Posts" index={10} />
                    */}

                    <NavSection label="Inventory" />
                    <NavItem onClick={() => setView('inventory')} active={view === 'inventory'} icon={<Package />} label="Inventory Forecasts" index={11} />
                    <NavItem onClick={() => setView('analytics')} active={view === 'analytics'} icon={<Activity />} label="Transaction Analytics" index={12} />

                    <NavSection label="Customer Intelligence" />
                    <NavItem onClick={() => setView('integrations')} active={view === 'integrations'} icon={<Plug />} label="Store Integrations" index={14} />
                    <NavItem onClick={() => setView('customer-analytics')} active={view === 'customer-analytics'} icon={<UserCheck />} label="Customer Analytics" index={15} />

                    <NavSection label="Lead Management" />
                    <NavItem onClick={() => setView('lead-scoring')} active={view === 'lead-scoring'} icon={<TrendingUp />} label="Lead Scoring" index={13} />
                </>
            )}

            {(['admin', 'manager', 'trainer'].includes(user.role)) && (
                <>
                    <NavSection label="Management" />
                    <NavItem onClick={() => setView('create-test')} active={view === 'create-test'} icon={<FileText />} label="Create MCQ Test" index={5} />
                    <NavItem onClick={() => setView('performance')} active={view === 'performance'} icon={<BarChart2 />} label="Performance" index={6} />

                    <NavSection label="Content" />
                    <NavItem onClick={() => setView('upload')} active={view === 'upload'} icon={<Upload />} label="Upload Content" index={7} />
                    <NavItem onClick={() => setView('manage')} active={view === 'manage'} icon={<FolderOpen />} label="Manage Content" index={8} />

                    <NavSection label="Team" />
                    <NavItem onClick={() => setView('invite')} active={view === 'invite'} icon={<UserPlus />} label="Invite Member" index={9} />
                </>
            )}

            {/* Logout at bottom */}
            <div className="mt-auto pt-4 border-t border-white/[0.05]">
                <button
                    onClick={logout}
                    className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 bg-white/[0.04] hover:bg-red-500/15 text-slate-400 hover:text-red-400 rounded-xl text-sm font-semibold transition-all duration-200 border border-white/[0.04] hover:border-red-500/20"
                >
                    <LogOut size={14} />
                    <span>Sign Out</span>
                </button>
            </div>
        </nav>
    );

    const renderContent = () => {
        switch (view) {
            case 'profile':
                return <ProfileView user={user} onNavigate={setView} />;
            case 'invite':
                return <InviteUserView user={user} token={token} />;
            case 'upload':
                return <ContentUploadView orgId={user.organization_id} token={token} user={user} />;
            case 'search':
                return <ContentRetrieverView orgId={user.organization_id} token={token} />;
            case 'manage':
                return <ContentManagerView orgId={user.organization_id} token={token} />;
            case 'mcq-practice':
                return <MCQPracticeView orgId={user.organization_id} token={token} />;
            case 'roleplay':
                return <RoleplayPersonas token={token} navigate={(newView, data) => {
                    setSessionData(data);
                    setView(newView);
                }} />;
            case 'roleplay-chat':
                return <RoleplayChat
                    sessionId={sessionData?.sessionId}
                    mode={sessionData?.mode || 'text'}
                    token={token}
                    onEnd={(receivedNlpData, sid, receivedConvHistory) => {
                        setNlpData(receivedNlpData || null);
                        setConversionHistory(receivedConvHistory || null);
                        setView('roleplay-feedback');
                    }}
                />;
            case 'roleplay-feedback':
                return <RoleplayFeedback
                    sessionId={sessionData?.sessionId}
                    token={token}
                    initialNlpData={nlpData}
                    conversionHistory={conversionHistory}
                    onBack={() => {
                        setView('roleplay');
                        setSessionData(null);
                        setNlpData(null);
                        setConversionHistory(null);
                    }}
                />;
            case 'create-test':
                return <MCQTestCreator orgId={user.organization_id} token={token} />;
            case 'performance':
                return <PerformanceDashboard key={`perf-${Date.now()}`} orgId={user.organization_id} token={token} userId={user.id} />;
            case 'knowledge-chat':
                return <KnowledgeChatbot orgId={user.organization_id} token={token} />;
            // Marketing Posts UI removed — module incomplete. Re-enable by uncommenting.
            // case 'marketing-posts':
            //     return <MarketingPostCreator token={token} genState={marketingGenState} setGenState={setMarketingGenState} />;
            case 'inventory':
                return <InventoryManagerView orgId={user.organization_id} token={token} />;
            case 'analytics':
                return <TransactionAnalytics token={token} />;
            case 'integrations':
                return <IntegrationsPage token={token} />;
            case 'customer-analytics':
                return <CustomerAnalyticsPage token={token} />;
            case 'lead-scoring':
                return <LeadManager token={token} />;
            default:
                return <ProfileView user={user} onNavigate={setView} />;
        }
    };

    return (
        <div className="flex max-w-[1440px] mx-auto h-[calc(100vh-2rem)] p-4 gap-4 dashboard-bg">
            {/* Sidebar */}
            <div className="hidden lg:block w-64 flex-shrink-0">
                <Sidebar />
            </div>

            {/* Mobile top bar */}
            <div className="lg:hidden fixed top-0 left-0 right-0 z-50 glass-dark px-4 py-3 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-teal-500 rounded-lg flex items-center justify-center">
                        <Zap size={16} className="text-white" />
                    </div>
                    <span className="text-sm font-bold text-white">SalesForge</span>
                </div>
                <button onClick={logout} className="text-slate-500 hover:text-red-400 transition-colors">
                    <LogOut size={18} />
                </button>
            </div>

            {/* Main content area — with page transitions */}
            <div className="flex-1 min-w-0 overflow-y-auto">
                <div className="bg-white/50 backdrop-blur-sm rounded-2xl border border-stone-200/40 shadow-sm p-6 md:p-8 min-h-full">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={view}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                        >
                            {renderContent()}
                        </motion.div>
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
};

// ===== Main App =====
export default function App() {
    const [token, setToken] = useState(null);
    const [user, setUser] = useState(null);
    const [view, setView] = useState('login');
    const [loadingUser, setLoadingUser] = useState(false);

    const navigate = (newView, authResult = null) => {
        if (authResult && authResult.access_token) {
            setToken(authResult.access_token);
            localStorage.setItem('sf_token', authResult.access_token);
            setView('dashboard');
        } else {
            setView(newView);
        }
    };

    const logout = () => {
        setToken(null);
        setUser(null);
        localStorage.removeItem('sf_token');
        setView('login');
    };

    useEffect(() => {
        const fetchUser = async () => {
            if (token) {
                setLoadingUser(true);
                try {
                    const fetchedUser = await authApi.getMe(token);
                    setUser(fetchedUser);
                } catch (error) {
                    console.error('Failed to fetch user:', error);
                    alert('Session expired. Please login again.');
                    logout();
                } finally {
                    setLoadingUser(false);
                }
            } else {
                setUser(null);
                setLoadingUser(false);
            }
        };
        fetchUser();
    }, [token]);

    useEffect(() => {
        const storedToken = localStorage.getItem('sf_token');
        if (storedToken) {
            setToken(storedToken);
            setView('dashboard');
        }
    }, []);

    const renderView = () => {
        if (loadingUser) {
            return (
                <div className="flex items-center justify-center min-h-screen">
                    <div className="text-center">
                        <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-teal-600 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-xl shadow-blue-500/25 animate-pulse">
                            <Loader2 className="animate-spin h-8 w-8 text-white" />
                        </div>
                        <p className="text-stone-600 font-medium">Loading your workspace...</p>
                        <p className="text-stone-400 text-sm mt-1">This won't take long</p>
                    </div>
                </div>
            );
        }

        if (view === 'dashboard') {
            return <DashboardView token={token} user={user} logout={logout} />;
        }

        // Auth views — centered layout with aurora animated background
        return (
            <div className="min-h-screen flex flex-col aurora-bg">
                {/* Aurora floating blob */}
                <div className="aurora-blob" />

                {/* Auth header */}
                <motion.header
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, ease: 'easeOut' }}
                    className="flex justify-between items-center max-w-5xl w-full mx-auto py-6 px-6 relative z-10"
                >
                    <div className="flex items-center space-x-3">
                        <motion.div
                            initial={{ scale: 0, rotate: -180 }}
                            animate={{ scale: 1, rotate: 0 }}
                            transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 0.2 }}
                            className="w-10 h-10 bg-gradient-to-br from-blue-600 to-teal-500 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/25"
                        >
                            <Zap size={20} className="text-white" />
                        </motion.div>
                        <h1 className="text-xl font-bold text-stone-800">SalesForge AI</h1>
                    </div>
                    <nav className="flex space-x-2">
                        {['login', 'register', 'org_create'].map((v, i) => (
                            <motion.button
                                key={v}
                                initial={{ opacity: 0, y: -10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.3 + i * 0.1 }}
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                                onClick={() => navigate(v)}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${view === v
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                                    : 'text-stone-600 hover:bg-white/60'
                                    }`}
                            >
                                {v === 'login' ? 'Login' : v === 'register' ? 'Register' : 'Create Org'}
                            </motion.button>
                        ))}
                    </nav>
                </motion.header>

                {/* Auth content — with page transitions */}
                <div className="flex-1 flex items-center justify-center px-4 pb-12 relative z-10">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={view}
                            initial={{ opacity: 0, scale: 0.96, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.96, y: -10 }}
                            transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
                            className="w-full"
                        >
                            {view === 'org_create' ? <OrgCreateView navigate={navigate} /> :
                                view === 'register' ? <RegisterView navigate={navigate} /> :
                                    <LoginView navigate={navigate} />}
                        </motion.div>
                    </AnimatePresence>
                </div>

                {/* Minimal footer */}
                <footer className="text-center py-6 relative z-10">
                    <p className="text-xs text-slate-400 font-medium">
                        SalesForge AI — Built with ❤️ for FYP 2026
                    </p>
                </footer>
            </div>
        );
    };

    return (
        <div className="min-h-screen dashboard-bg font-['Inter',sans-serif]">
            {renderView()}
        </div>
    );
}