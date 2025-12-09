import React, { useState, useEffect } from 'react';
import { 
    Home, UserPlus, Upload, Loader2, Brain, 
    BarChart2, FileText, FolderOpen, Search, LogOut, Sparkles, Zap
} from 'lucide-react';
import { apiFetch, auth as authApi } from './utils/api';

// Page Imports
import LoginView from './pages/Login';
import { OrgCreateView, RegisterView, roles } from './pages/RegisterOrg';
import ContentUploadView from './pages/ContentUpload';
import ContentRetrieverView from './pages/ContentRetriever';
import ContentManagerView from './pages/ContentManager';

// MCQ Features
import MCQPracticeView from './pages/MCQPractice';
import MCQTestCreator from './pages/MCQTestCreator';
import PerformanceDashboard from './pages/PerformanceDashboard';

// ===== UI Components ===== 
export const Card = ({ title, icon, children, onClick, className = '' }) => (
    <div 
        onClick={onClick}
        className={`max-w-md mx-auto p-6 md:p-8 bg-white/95 backdrop-blur-sm rounded-3xl shadow-2xl border-2 border-cyan-100/50 hover:shadow-cyan-200/50 hover:shadow-3xl hover:border-cyan-200 transition-all duration-300 ${className}`}
    >
        <div className="flex items-center space-x-3 mb-6 border-b-2 border-gradient-to-r from-cyan-200 to-blue-200 pb-4">
            <div className="p-3 bg-gradient-to-br from-cyan-500 via-blue-500 to-indigo-600 text-white rounded-2xl shadow-lg shadow-cyan-500/30">
                {icon}
            </div>
            <h2 className="text-2xl font-black bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-700 bg-clip-text text-transparent">
                {title}
            </h2>
        </div>
        {children}
    </div>
);

export const Input = ({ name, label, type, value, onChange, required = false, disabled = false, placeholder = '' }) => (
    <div>
        <label htmlFor={name} className="block text-sm font-bold text-slate-700 mb-2 flex items-center">
            <span className="w-1 h-4 bg-gradient-to-b from-cyan-500 to-blue-600 rounded-full mr-2"></span>
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
            className="w-full p-3.5 border-2 border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 bg-white/80 transition-all duration-200 hover:border-slate-300 hover:bg-white placeholder:text-slate-400"
        />
    </div>
);

export const Select = ({ name, label, value, options, onChange, required = false, disabled = false }) => (
    <div>
        <label htmlFor={name} className="block text-sm font-bold text-slate-700 mb-2 flex items-center">
            <span className="w-1 h-4 bg-gradient-to-b from-cyan-500 to-blue-600 rounded-full mr-2"></span>
            {label}
        </label>
        <select
            id={name}
            name={name}
            value={value}
            onChange={onChange}
            required={required}
            disabled={disabled}
            className="w-full p-3.5 border-2 border-slate-200 rounded-2xl bg-white/80 focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 transition-all duration-200 hover:border-slate-300 hover:bg-white cursor-pointer"
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
        className={`w-full flex justify-center items-center py-4 px-6 border-2 border-transparent rounded-2xl shadow-lg text-base font-bold text-white bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600 hover:from-cyan-600 hover:via-blue-600 hover:to-indigo-700 focus:outline-none focus:ring-4 focus:ring-cyan-300/50 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-[1.02] hover:shadow-xl hover:shadow-cyan-500/30 active:scale-[0.98] ${className}`}
    >
        {loading && (
            <Loader2 className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" />
        )}
        {children}
    </button>
);

// ===== Dashboard Components =====
const MenuItem = ({ onClick, active, icon, label }) => (
    <button
        onClick={onClick}
        className={`flex items-center space-x-3 w-full p-3.5 rounded-2xl transition-all duration-300 text-sm font-bold group ${
            active 
                ? 'bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600 text-white shadow-lg shadow-cyan-500/30 transform scale-[1.03]' 
                : 'text-slate-600 hover:bg-gradient-to-r hover:from-cyan-50 hover:via-blue-50 hover:to-indigo-50 hover:text-slate-900 hover:shadow-md'
        }`}
    >
        <div className={`${active ? 'text-white' : 'text-cyan-600 group-hover:text-blue-600'} transition-colors duration-200`}>
            {React.cloneElement(icon, { size: 20 })}
        </div>
        <span>{label}</span>
    </button>
);

const DetailItem = ({ label, value, highlight, color = 'slate' }) => {
    const colorClasses = {
        slate: 'text-slate-800',
        green: 'text-emerald-600 font-bold',
        red: 'text-rose-600 font-bold',
        cyan: 'text-cyan-600 font-bold',
        blue: 'text-blue-600 font-bold',
    };
    return (
        <div className="grid grid-cols-3 gap-4 border-b-2 border-slate-100 py-4 hover:bg-gradient-to-r hover:from-cyan-50/50 hover:to-blue-50/50 transition-all duration-200 rounded-xl px-3">
            <p className="text-sm font-bold text-slate-500 flex items-center">
                <span className="w-2 h-2 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-full mr-2"></span>
                {label}
            </p>
            <p className={`text-sm col-span-2 ${colorClasses[color]} ${highlight ? 'font-black text-base' : ''}`}>{value}</p>
        </div>
    );
};

const ProfileView = ({ user }) => (
    <>
        <div className="mb-8 bg-gradient-to-r from-cyan-50 via-blue-50 to-indigo-50 p-6 rounded-3xl border-2 border-cyan-100">
            <div className="flex items-center space-x-3 mb-3">
                <div className="p-3 bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-2xl shadow-lg shadow-cyan-500/30">
                    <Zap size={28} />
                </div>
                <h3 className="text-4xl font-black bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-700 bg-clip-text text-transparent">
                    Welcome back!
                </h3>
            </div>
            <p className="text-slate-600 text-xl font-semibold ml-16">
                {user.full_name || user.email.split('@')[0]} 👋
            </p>
            <p className="text-slate-500 text-sm mt-2 ml-16">Here's your profile information</p>
        </div>
        
        <div className="space-y-2 bg-gradient-to-br from-white to-slate-50 p-7 rounded-3xl border-2 border-slate-100 shadow-xl">
            <DetailItem label="Email" value={user.email} color="blue" />
            <DetailItem label="Full Name" value={user.full_name || 'Not set'} color="slate" />
            <DetailItem label="Your Role" value={user.role.toUpperCase()} highlight color="cyan" />
            <DetailItem label="User ID" value={user.id} color="slate" />
            <DetailItem label="Org ID" value={user.organization_id} color="slate" />
            <DetailItem label="Status" value={user.is_active ? '🟢 Active' : '🔴 Inactive'} color={user.is_active ? 'green' : 'red'} />
            <DetailItem label="Member Since" value={new Date(user.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })} color="slate" />
        </div>
    </>
);

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
        <>
            <div className="mb-8 bg-gradient-to-r from-cyan-50 via-blue-50 to-indigo-50 p-6 rounded-3xl border-2 border-cyan-100">
                <h3 className="text-3xl font-black text-slate-800 mb-2 flex items-center space-x-3">
                    <div className="p-3 bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-2xl shadow-lg shadow-cyan-500/30">
                        <UserPlus size={26} />
                    </div>
                    <span className="bg-gradient-to-r from-cyan-600 to-blue-700 bg-clip-text text-transparent">
                        Invite New Team Member
                    </span>
                </h3>
                <p className="text-slate-600 font-medium ml-16">Send an invitation to join your organization</p>
            </div>
            
            <form onSubmit={handleInvite} className="space-y-6 max-w-lg">
                <Input 
                    name="email" 
                    type="email" 
                    label="📧 User Email Address" 
                    value={formData.email} 
                    onChange={handleChange} 
                    required 
                    placeholder="colleague@company.com"
                />
                <Select 
                    name="role" 
                    label="👔 Assign Role" 
                    value={formData.role} 
                    options={roles} 
                    onChange={handleChange} 
                    required 
                />
                <Button type="submit" loading={loading}>
                    {loading ? (
                        <>
                            <Loader2 className="animate-spin mr-2" size={20} />
                            Sending Invitation...
                        </>
                    ) : (
                        <>
                            <Sparkles size={20} className="mr-2" />
                            Generate Invite Token
                        </>
                    )}
                </Button>
            </form>
            
            {message && (
                <div className={`mt-6 p-6 rounded-2xl text-sm break-all border-2 shadow-lg ${
                    message.startsWith('Error') 
                        ? 'bg-gradient-to-r from-rose-50 to-red-50 text-rose-700 border-rose-300 shadow-rose-200/50' 
                        : 'bg-gradient-to-r from-emerald-50 to-green-50 text-emerald-700 border-emerald-300 shadow-emerald-200/50'
                }`}>
                    <p className="font-black text-base mb-3 flex items-center">
                        {message.startsWith('Success') ? (
                            <>
                                <span className="w-6 h-6 bg-emerald-500 rounded-full flex items-center justify-center mr-2">✓</span>
                                Invitation Sent!
                            </>
                        ) : (
                            <>
                                <span className="w-6 h-6 bg-rose-500 rounded-full flex items-center justify-center mr-2">✕</span>
                                Action Failed!
                            </>
                        )}
                    </p>
                    <p className="font-mono text-xs bg-white/50 p-3 rounded-xl">{message}</p>
                </div>
            )}
        </>
    );
};

const DashboardView = ({ token, user, logout }) => {
    const [view, setView] = useState('profile');

    if (!user) {
        return (
            <div className="text-center p-16">
                <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-cyan-500 via-blue-500 to-indigo-600 rounded-3xl mb-6 shadow-2xl shadow-cyan-500/40 animate-pulse">
                    <Loader2 className="animate-spin h-10 w-10 text-white" />
                </div>
                <p className="mt-4 text-slate-700 text-xl font-bold">Loading your dashboard...</p>
                <p className="text-slate-500 text-sm mt-2">This won't take long</p>
            </div>
        );
    }

    const DashboardMenu = () => (
        <nav className="flex flex-col space-y-2 p-6 bg-gradient-to-br from-white via-slate-50 to-cyan-50/30 rounded-3xl border-2 border-slate-200/50 shadow-2xl backdrop-blur-sm">
            <div className="pb-4 border-b-2 border-slate-200 mb-3">
                <h3 className="text-xs font-black uppercase text-slate-400 tracking-widest flex items-center">
                    <Sparkles size={14} className="mr-2 text-cyan-500" />
                    My Workspace
                </h3>
            </div>
            <MenuItem onClick={() => setView('profile')} active={view === 'profile'} icon={<Home />} label="My Profile" />
            
            <div className="pt-4 border-t-2 border-slate-200 mt-3">
                <h3 className="text-xs font-black uppercase text-slate-400 tracking-widest mb-3 flex items-center">
                    <Brain size={14} className="mr-2 text-blue-500" />
                    Training
                </h3>
            </div>
            <MenuItem onClick={() => setView('mcq-practice')} active={view === 'mcq-practice'} icon={<Brain />} label="MCQ Practice" />
            <MenuItem onClick={() => setView('search')} active={view === 'search'} icon={<Search />} label="Search Knowledge" />
            
            {(['admin', 'manager', 'trainer'].includes(user.role)) && (
                <>
                    <div className="pt-4 border-t-2 border-slate-200 mt-3">
                        <h3 className="text-xs font-black uppercase text-slate-400 tracking-widest mb-3 flex items-center">
                            <FileText size={14} className="mr-2 text-indigo-500" />
                            MCQ Management
                        </h3>
                    </div>
                    <MenuItem 
                        onClick={() => setView('create-test')} 
                        active={view === 'create-test'} 
                        icon={<FileText />} 
                        label="Create MCQ Test" 
                    />
                    <MenuItem 
                        onClick={() => setView('performance')} 
                        active={view === 'performance'} 
                        icon={<BarChart2 />} 
                        label="View Performance" 
                    />
                    
                    <div className="pt-4 border-t-2 border-slate-200 mt-3">
                        <h3 className="text-xs font-black uppercase text-slate-400 tracking-widest mb-3 flex items-center">
                            <FolderOpen size={14} className="mr-2 text-blue-500" />
                            Content Management
                        </h3>
                    </div>
                    <MenuItem onClick={() => setView('upload')} active={view === 'upload'} icon={<Upload />} label="Upload Content" />
                    <MenuItem onClick={() => setView('manage')} active={view === 'manage'} icon={<FolderOpen />} label="Manage Content" />
                    
                    <div className="pt-4 border-t-2 border-slate-200 mt-3">
                        <h3 className="text-xs font-black uppercase text-slate-400 tracking-widest mb-3 flex items-center">
                            <UserPlus size={14} className="mr-2 text-cyan-500" />
                            User Management
                        </h3>
                    </div>
                    <MenuItem onClick={() => setView('invite')} active={view === 'invite'} icon={<UserPlus />} label="Invite Team" />
                </>
            )}
            
            <div className="pt-4 border-t-2 border-slate-200 mt-4">
                <button
                    onClick={logout}
                    className="w-full flex items-center justify-center space-x-2 py-3.5 px-4 bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white rounded-2xl shadow-lg shadow-rose-500/30 font-bold transition-all duration-200 transform hover:scale-[1.02] hover:shadow-xl active:scale-[0.98]"
                >
                    <LogOut size={18} />
                    <span>Logout</span>
                </button>
            </div>
        </nav>
    );

    const renderContent = () => {
        switch (view) {
            case 'profile':
                return <ProfileView user={user} />;
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
            case 'create-test':
                return <MCQTestCreator orgId={user.organization_id} token={token} />;
            case 'performance':
                return <PerformanceDashboard orgId={user.organization_id} token={token} />;
            default:
                return <ProfileView user={user} />;
        }
    };

    return (
        <div className="flex flex-col lg:flex-row max-w-7xl mx-auto p-4 md:p-8 space-y-6 lg:space-y-0 lg:space-x-8">
            <div className="w-full lg:w-1/4">
                <DashboardMenu />
            </div>
            <div className="w-full lg:w-3/4">
                <div className="bg-white/95 backdrop-blur-sm p-8 md:p-10 rounded-3xl shadow-2xl border-2 border-slate-200/50 min-h-[500px]">
                    {renderContent()}
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
        console.log('🧭 Navigate called:', { newView, authResult });
        
        if (authResult && authResult.access_token) {
            console.log('💾 Setting token from login');
            setToken(authResult.access_token);
            localStorage.setItem('sf_token', authResult.access_token);
            setView('dashboard');
        } else {
            setView(newView);
        }
    };

    const logout = () => {
        console.log('🚪 Logging out...');
        setToken(null);
        setUser(null);
        localStorage.removeItem('sf_token');
        setView('login');
    };

    useEffect(() => {
        const fetchUser = async () => {
            console.log('🔍 Token changed, token exists:', !!token);
            
            if (token) {
                setLoadingUser(true);
                try {
                    console.log('👤 Fetching user data...');
                    const fetchedUser = await authApi.getMe(token);
                    console.log('✅ User data received:', fetchedUser);
                    setUser(fetchedUser);
                } catch (error) {
                    console.error('❌ Failed to fetch user:', error);
                    alert('Session expired. Please login again.');
                    logout();
                } finally {
                    setLoadingUser(false);
                }
            } else {
                console.log('ℹ️  No token found');
                setUser(null);
                setLoadingUser(false);
            }
        };
        
        fetchUser();
    }, [token]);

    useEffect(() => {
        console.log('🚀 App mounted, checking for stored token...');
        const storedToken = localStorage.getItem('sf_token');
        if (storedToken) {
            console.log('✅ Found stored token');
            setToken(storedToken);
            setView('dashboard');
        } else {
            console.log('ℹ️  No stored token');
        }
    }, []);

    const renderView = () => {
        console.log('🎨 Rendering view:', view, 'User:', !!user, 'Token:', !!token, 'Loading:', loadingUser);

        if (loadingUser) {
            return (
                <div className="text-center p-24">
                    <div className="inline-flex items-center justify-center w-24 h-24 bg-gradient-to-br from-cyan-500 via-blue-500 to-indigo-600 rounded-3xl mb-6 shadow-2xl shadow-cyan-500/50 animate-pulse">
                        <Loader2 className="animate-spin h-12 w-12 text-white" />
                    </div>
                    <p className="mt-4 text-slate-700 text-xl font-bold">Loading your dashboard...</p>
                    <p className="text-slate-500 text-sm mt-2">This won't take long</p>
                </div>
            );
        }

        if (view === 'dashboard') {
            return <DashboardView token={token} user={user} logout={logout} />;
        }
        
        switch (view) {
            case 'org_create':
                return <OrgCreateView navigate={navigate} />;
            case 'register':
                return <RegisterView navigate={navigate} />;
            case 'login':
            default:
                return <LoginView navigate={navigate} />;
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-100 font-sans p-4 md:p-8">
            <header className="flex justify-between items-center max-w-7xl mx-auto py-6 mb-8 bg-white/90 backdrop-blur-md rounded-3xl shadow-2xl border-2 border-slate-200/50 px-8">
                <div>
                    <h1 className="text-4xl font-black bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-700 bg-clip-text text-transparent flex items-center">
                        SalesForge AI
                        <Zap size={28} className="ml-3 text-cyan-500" />
                    </h1>
                    {user && (
                        <p className="text-sm text-slate-600 mt-2 font-bold flex items-center">
                            <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2 animate-pulse"></span>
                            {user.email} 
                            <span className="ml-2 px-2 py-0.5 bg-gradient-to-r from-cyan-100 to-blue-100 text-cyan-700 rounded-lg text-xs font-black">
                                {user.role.toUpperCase()}
                            </span>
                        </p>
                    )}
                </div>
                <nav className="flex space-x-3">
                    {!token && (
                        <>
                            <button 
                                onClick={() => navigate('login')} 
                                className={`px-6 py-3 rounded-2xl text-sm font-bold transition-all duration-200 ${
                                    view === 'login' 
                                        ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/30' 
                                        : 'text-slate-600 hover:bg-slate-100 border-2 border-transparent hover:border-slate-200'
                                }`}
                            >
                                Login
                            </button>
                            <button 
                                onClick={() => navigate('register')} 
                                className={`px-6 py-3 rounded-2xl text-sm font-bold transition-all duration-200 ${
                                    view === 'register' 
                                        ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/30' 
                                        : 'text-slate-600 hover:bg-slate-100 border-2 border-transparent hover:border-slate-200'
                                }`}
                            >
                                Register
                            </button>
                            <button 
                                onClick={() => navigate('org_create')} 
                                className={`px-6 py-3 rounded-2xl text-sm font-bold transition-all duration-200 ${
                                    view === 'org_create' 
                                        ? 'bg-gradient-to-r from-cyan-600 to-indigo-700 text-white shadow-lg shadow-cyan-500/40' 
                                        : 'text-cyan-600 border-2 border-cyan-600 hover:bg-cyan-50'
                                }`}
                            >
                                Create Org
                            </button>
                        </>
                    )}
                </nav>
            </header>
            
            {renderView()}

            <footer className="mt-16 text-center text-slate-500 pb-8">
                <div className="max-w-2xl mx-auto bg-white/80 backdrop-blur-sm rounded-3xl p-6 shadow-xl border-2 border-slate-200/50">
                    <p className="font-black text-slate-700 text-lg bg-gradient-to-r from-cyan-600 to-blue-700 bg-clip-text text-transparent">
                        SalesForge AI - FYP 2026
                    </p>
                    <p className="text-xs mt-2 text-slate-600 font-semibold">
                        Advanced MCQ Generation with RAG Technology
                    </p>
                    <div className="mt-3 flex items-center justify-center space-x-2 text-xs text-slate-500">
                        <Sparkles size={12} className="text-cyan-500" />
                        <span>Powered by AI</span>
                        <span>•</span>
                        <span>Built with ❤️</span>
                    </div>
                </div>
            </footer>
        </div>
    );
}