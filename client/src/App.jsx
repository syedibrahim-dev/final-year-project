import React, { useState, useEffect } from 'react';
import { Home, UserPlus, Upload, BookOpen, Search, Loader2, Brain } from 'lucide-react';
import { apiFetch, auth as authApi } from './utils/api';

// Page Imports
import LoginView from './pages/Login';
import { OrgCreateView, RegisterView, roles } from './pages/RegisterOrg';
import ContentUploadView from './pages/ContentUpload';
import ContentRetrieverView from './pages/ContentRetriever';
import ContentManagerView from './pages/ContentManager';
// MCQ Practice (Available to all users)
import MCQPracticeView from './pages/MCQPractice';

// ===== UI Components =====
export const Card = ({ title, icon, children }) => (
    <div className="max-w-md mx-auto p-6 md:p-8 bg-white rounded-xl shadow-2xl border border-gray-100">
        <div className="flex items-center space-x-3 mb-6 border-b pb-4">
            <div className="p-3 bg-indigo-100 text-indigo-600 rounded-full">{icon}</div>
            <h2 className="text-2xl font-bold text-gray-800">{title}</h2>
        </div>
        {children}
    </div>
);

export const Input = ({ name, label, type, value, onChange, required = false, disabled = false, placeholder = '' }) => (
    <div>
        <label htmlFor={name} className="block text-sm font-medium text-gray-700 mb-1">
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
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 transition duration-150"
        />
    </div>
);

export const Select = ({ name, label, value, options, onChange, required = false, disabled = false }) => (
    <div>
        <label htmlFor={name} className="block text-sm font-medium text-gray-700 mb-1">
            {label}
        </label>
        <select
            id={name}
            name={name}
            value={value}
            onChange={onChange}
            required={required}
            disabled={disabled}
            className="w-full p-3 border border-gray-300 rounded-lg bg-white focus:ring-indigo-500 focus:border-indigo-500 transition duration-150"
        >
            {options.map(option => (
                <option key={option} value={option}>{option.charAt(0).toUpperCase() + option.slice(1)}</option>
            ))}
        </select>
    </div>
);

export const Button = ({ children, onClick, type = 'button', loading = false, className = '' }) => (
    <button
        type={type}
        onClick={onClick}
        disabled={loading}
        className={`w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-lg shadow-md text-base font-semibold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
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
        className={`flex items-center space-x-3 w-full p-3 rounded-lg transition duration-150 text-sm font-medium ${
            active ? 'bg-indigo-100 text-indigo-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`}
    >
        {React.cloneElement(icon, { size: 18 })}
        <span>{label}</span>
    </button>
);

const DetailItem = ({ label, value, highlight, color = 'gray' }) => {
    const colorClasses = {
        gray: 'text-gray-800',
        green: 'text-green-600 font-semibold',
        red: 'text-red-600 font-semibold',
    };
    return (
        <div className="grid grid-cols-3 gap-4 border-b border-gray-100 py-3">
            <p className="text-sm font-medium text-gray-500">{label}</p>
            <p className={`text-sm col-span-2 ${colorClasses[color]} ${highlight ? 'font-bold text-base' : ''}`}>{value}</p>
        </div>
    );
};

const ProfileView = ({ user }) => (
    <>
        <h3 className="text-3xl font-extrabold text-gray-900 mb-6 border-b pb-4">
            Welcome, {user.email}!
        </h3>
        <div className="space-y-4 max-w-lg">
            <DetailItem label="Email" value={user.email} />
            <DetailItem label="Organization" value={user.organization.name} />
            <DetailItem label="Your Role" value={user.role.toUpperCase()} highlight />
            <DetailItem label="User ID" value={user.id} />
            <DetailItem label="Org ID" value={user.organization.id} />
            <DetailItem label="Status" value={user.is_active ? 'Active' : 'Inactive'} color={user.is_active ? 'green' : 'red'} />
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
            const response = await apiFetch(`/orgs/${user.organization.id}/invite`, 'POST', formData, token);
            setMessage(`Success! User invited with role '${formData.role}'. Invite Token: ${response.access_token}`);
            setFormData({ email: '', role: 'trainee' });
        } catch (error) {
            setMessage(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <h3 className="text-2xl font-bold text-gray-800 mb-6 flex items-center space-x-3">
                <UserPlus size={24} className="text-indigo-600"/> <span>Invite New User</span>
            </h3>
            <p className="mb-6 text-gray-600">Invite a new user to <strong>{user.organization.name}</strong> and assign their role.</p>
            
            <form onSubmit={handleInvite} className="space-y-6 max-w-lg">
                <Input name="email" type="email" label="User Email to Invite" value={formData.email} onChange={handleChange} required />
                <Select name="role" label="Assign Role" value={formData.role} options={roles} onChange={handleChange} required />
                <Button type="submit" loading={loading} className="w-full">
                    {loading ? 'Sending Invite...' : 'Generate Invite Token'}
                </Button>
            </form>
            
            {message && (
                <div className={`mt-6 p-4 rounded-lg text-sm break-all ${message.startsWith('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                    <p className="font-semibold">{message.startsWith('Success') ? 'Invitation Sent!' : 'Action Failed!'}</p>
                    <p>{message}</p>
                </div>
            )}
        </>
    );
};

const DashboardView = ({ token, user, logout }) => {
    const [view, setView] = useState('profile');

    const DashboardMenu = () => (
        <nav className="flex flex-col space-y-2 p-4 bg-gray-50 rounded-lg border">
            <h3 className="text-xs font-semibold uppercase text-gray-500 mb-1">My Workspace</h3>
            <MenuItem onClick={() => setView('profile')} active={view === 'profile'} icon={<Home />} label="My Profile" />
            
            <h3 className="text-xs font-semibold uppercase text-gray-500 mt-4 mb-1">Training</h3>
            {/* MCQ Practice - Available to ALL users */}
            <MenuItem onClick={() => setView('mcq')} active={view === 'mcq'} icon={<Brain />} label="MCQ Practice" />
            <MenuItem onClick={() => setView('search')} active={view === 'search'} icon={<Search />} label="Search Knowledge" />
            
            {/* Admin/Manager Tools */}
            {(user.role === 'admin' || user.role === 'manager') && (
                <>
                    <h3 className="text-xs font-semibold uppercase text-gray-500 mt-4 mb-1">Admin Tools</h3>
                    <MenuItem onClick={() => setView('upload')} active={view === 'upload'} icon={<Upload />} label="Upload Content" />
                    <MenuItem onClick={() => setView('manage')} active={view === 'manage'} icon={<BookOpen />} label="Manage Content" />
                    <MenuItem onClick={() => setView('invite')} active={view === 'invite'} icon={<UserPlus />} label="Invite Team" />
                </>
            )}
            
            <hr className="my-2 border-gray-200" />
            <Button onClick={logout} className="bg-red-500 hover:bg-red-600 text-white w-full">
                Logout
            </Button>
        </nav>
    );

    const renderContent = () => {
        if (!user) return <div className="text-center p-12"><Loader2 className="animate-spin inline-block h-8 w-8 text-indigo-600" /></div>;

        switch (view) {
            case 'profile':
                return <ProfileView user={user} />;
            case 'invite':
                return <InviteUserView user={user} token={token} />;
            case 'upload':
                return <ContentUploadView orgId={user.organization.id} token={token} user={user} />;
            case 'search':
                return <ContentRetrieverView orgId={user.organization.id} token={token} />;
            case 'manage':
                return <ContentManagerView orgId={user.organization.id} token={token} />;
            case 'mcq':
                return <MCQPracticeView orgId={user.organization.id} token={token} />;
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
                <div className="bg-white p-6 md:p-8 rounded-xl shadow-xl border border-gray-100 min-h-[500px]">
                    {renderContent()}
                </div>
            </div>
        </div>
    );
};

// ===== Main App =====
export default function App() {
    const [token, setToken] = useState(localStorage.getItem('sf_token'));
    const [user, setUser] = useState(null);
    const [view, setView] = useState('login');
    const [loadingUser, setLoadingUser] = useState(true);

    const navigate = (newView, authResult = null) => {
        if (authResult && authResult.access_token) {
            setToken(authResult.access_token);
            localStorage.setItem('sf_token', authResult.access_token);
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
                    setView('dashboard');
                } catch (error) {
                    console.error('Failed to fetch user:', error);
                    logout();
                } finally {
                    setLoadingUser(false);
                }
            } else {
                setUser(null);
                setLoadingUser(false);
                if (!['login', 'register', 'org_create'].includes(view)) {
                    setView('login');
                }
            }
        };
        fetchUser();
    }, [token]);

    const renderView = () => {
        if (loadingUser) {
            return <div className="text-center p-24"><Loader2 className="animate-spin inline-block h-12 w-12 text-indigo-600" /></div>;
        }

        if (token && user) {
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
        <div className="min-h-screen bg-gray-100 font-sans p-4 md:p-8">
            <header className="flex justify-between items-center max-w-7xl mx-auto py-4 mb-8">
                <h1 className="text-3xl font-black text-indigo-700 flex items-center">
                    SalesForge AI
                </h1>
                <nav className="flex space-x-2">
                    {!token && !loadingUser && (
                        <>
                            <button onClick={() => navigate('login')} className={`px-4 py-2 rounded-lg text-sm font-medium ${view === 'login' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-600 hover:bg-gray-100'}`}>Login</button>
                            <button onClick={() => navigate('register')} className={`px-4 py-2 rounded-lg text-sm font-medium ${view === 'register' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-600 hover:bg-gray-100'}`}>Register</button>
                            <button onClick={() => navigate('org_create')} className={`px-4 py-2 rounded-lg text-sm font-medium ${view === 'org_create' ? 'bg-indigo-600 text-white shadow-sm' : 'text-indigo-600 border border-indigo-600 hover:bg-indigo-50'}`}>Create Org</button>
                        </>
                    )}
                </nav>
            </header>
            
            {renderView()}

            <footer className="mt-12 text-center text-gray-500 text-xs">
                SalesForge AI - FYP 2026 | AI Training with MCQ Generation
            </footer>
        </div>
    );
}