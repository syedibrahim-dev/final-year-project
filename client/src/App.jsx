// src/App.jsx

import React, { useState, useEffect, useCallback } from 'react';
import { Home, UserPlus, Briefcase } from 'lucide-react';
import { apiFetch } from './utils/api';
import LoginView from './pages/Login';
import { OrgCreateView, RegisterView, roles } from './pages/RegisterOrg'; // Import components and roles

// --- UI Sub-Components (Kept here for simplicity, move to src/components/ in production) ---

export const Card = ({ title, icon, children }) => ( /* ... Card implementation ... */
    <div className="max-w-md mx-auto p-6 md:p-8 bg-white rounded-xl shadow-2xl border border-gray-100">
        <div className="flex items-center space-x-3 mb-6 border-b pb-4">
            <div className="p-3 bg-indigo-100 text-indigo-600 rounded-full">{icon}</div>
            <h2 className="text-2xl font-bold text-gray-800">{title}</h2>
        </div>
        {children}
    </div>
);

export const Input = ({ name, label, type, value, onChange, required = false, disabled = false }) => ( /* ... Input implementation ... */
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
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 transition duration-150"
        />
    </div>
);

export const Select = ({ name, label, value, options, onChange, required = false, disabled = false }) => ( /* ... Select implementation ... */
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

export const Button = ({ children, onClick, type = 'button', loading = false, className = '' }) => ( /* ... Button implementation ... */
    <button
        type={type}
        onClick={onClick}
        disabled={loading}
        className={`w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-lg shadow-md text-base font-semibold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
        {loading && (
            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
        )}
        {children}
    </button>
);

// --- Dashboard Sub-Components (moved from original block) ---

const MenuItem = ({ onClick, active, icon, label }) => ( /* ... MenuItem implementation ... */
    <button
        onClick={onClick}
        className={`flex items-center space-x-3 w-full p-3 rounded-lg transition duration-150 ${
            active ? 'bg-indigo-50 text-indigo-700 font-semibold' : 'text-gray-600 hover:bg-gray-100'
        }`}
    >
        {React.cloneElement(icon, { size: 20 })}
        <span>{label}</span>
    </button>
);

const DetailItem = ({ label, value, highlight, color = 'gray' }) => { /* ... DetailItem implementation ... */
    const colorClasses = {
        gray: 'text-gray-800',
        green: 'text-green-600 font-semibold',
        red: 'text-red-600 font-semibold',
    };
    return (
        <div className="grid grid-cols-2 gap-4 border-b border-gray-100 py-2">
            <p className="text-sm font-medium text-gray-500">{label}</p>
            <p className={`text-base ${colorClasses[color]} ${highlight ? 'font-bold text-lg' : ''}`}>{value}</p>
        </div>
    );
};

const ProfileView = ({ user }) => ( /* ... ProfileView implementation ... */
    <>
        <h3 className="text-3xl font-extrabold text-gray-900 mb-6 border-b pb-4">Welcome, {user.email}!</h3>
        <div className="space-y-6">
            <DetailItem label="Organization" value={user.organization.name} />
            <DetailItem label="Your Role" value={user.role.toUpperCase()} highlight />
            <DetailItem label="User ID" value={user.id} />
            <DetailItem label="Org ID" value={user.organization_id} />
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
            const response = await apiFetch(`/orgs/${user.organization_id}/invite`, 'POST', formData, token);
            setMessage(`Success! User invited with role '${formData.role}'. Invite Token: ${response.access_token}`);
        } catch (error) {
            setMessage(`Error: ${error.message}`);
        }
        setLoading(false);
    };

    return (
        <>
            <h3 className="text-2xl font-bold text-gray-800 mb-6">Invite New User to {user.organization.name}</h3>
            <p className="mb-6 text-gray-600">You must be an Admin or Manager to send invites.</p>
            
            <form onSubmit={handleInvite} className="space-y-4">
                <Input name="email" type="email" label="User Email to Invite" value={formData.email} onChange={handleChange} required />
                <Select name="role" label="Assign Role" value={formData.role} options={roles} onChange={handleChange} required />
                <Button type="submit" loading={loading}>
                    {loading ? 'Sending Invite...' : 'Generate Invite Token'}
                </Button>
            </form>
            
            {message && (
                <div className={`mt-6 p-4 rounded-lg text-sm break-all ${message.startsWith('Error') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
                    <p className="font-semibold">{message.startsWith('Success') ? 'Invitation Sent!' : 'Action Failed!'}</p>
                    <p>{message.substring(message.indexOf(':') + 1)}</p>
                </div>
            )}
        </>
    );
};


// 4. Protected Dashboard View (Protected Content)
const DashboardView = ({ token, user, logout }) => {
    const [view, setView] = useState('profile');

    const DashboardMenu = () => (
        <nav className="flex flex-col space-y-2 p-4 bg-gray-50 rounded-lg">
            <h3 className="text-xs font-semibold uppercase text-gray-500 mb-1">Navigation</h3>
            <MenuItem onClick={() => setView('profile')} active={view === 'profile'} icon={<Home />} label="My Profile" />
            {(user.role === 'admin' || user.role === 'manager') && (
                <MenuItem onClick={() => setView('invite')} active={view === 'invite'} icon={<UserPlus />} label="Invite User" />
            )}
            <hr className="my-2 border-gray-200" />
            <Button onClick={logout} className="bg-red-500 hover:bg-red-600 text-white">
                Logout
            </Button>
        </nav>
    );

    const renderContent = () => {
        if (!user) return <p>Loading user profile...</p>;

        switch (view) {
            case 'profile':
                return <ProfileView user={user} />;
            case 'invite':
                return <InviteUserView user={user} token={token} />;
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
                <div className="bg-white p-6 md:p-8 rounded-xl shadow-2xl border border-gray-100 min-h-[500px]">
                    {renderContent()}
                </div>
            </div>
        </div>
    );
};

// --- Main App Component ---
export default function App() {
    const [token, setToken] = useState(localStorage.getItem('sf_token'));
    const [user, setUser] = useState(null);
    const [view, setView] = useState('login'); // 'login', 'register', 'org_create', 'dashboard'

    // Navigation and state update handler
    const navigate = (newView, authResult = null) => {
        if (authResult && authResult.access_token) {
            setToken(authResult.access_token);
            localStorage.setItem('sf_token', authResult.access_token);
            // Don't set view here, let the useEffect handle the 'dashboard' switch after fetching user
        }
        setView(newView);
    };

    const logout = () => {
        setToken(null);
        setUser(null);
        localStorage.removeItem('sf_token');
        setView('login');
    };

    // Effect to fetch user details on token change
    useEffect(() => {
        const fetchUser = async () => {
            if (token) {
                try {
                    const fetchedUser = await apiFetch('/users/me', 'GET', null, token);
                    setUser(fetchedUser);
                    setView('dashboard');
                } catch (error) {
                    console.error('Failed to fetch user:', error);
                    logout(); // Log out if token is invalid
                }
            } else {
                setUser(null);
                // Ensure view is a public one if no token exists
                if (!['login', 'register', 'org_create'].includes(view)) {
                    setView('login');
                }
            }
        };
        fetchUser();
    }, [token]);

    // Conditional Rendering of Views
    const renderView = () => {
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
        <div className="min-h-screen bg-gray-50 font-sans p-4 md:p-8">
            <header className="flex justify-between items-center max-w-7xl mx-auto py-4 mb-8">
                <h1 className="text-3xl font-black text-indigo-700">SalesForge</h1>
                <nav className="flex space-x-4">
                    {!token && (
                        <>
                            <button onClick={() => navigate('login')} className={`px-4 py-2 rounded-lg text-sm font-medium ${view === 'login' ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-100'}`}>Login</button>
                            <button onClick={() => navigate('register')} className={`px-4 py-2 rounded-lg text-sm font-medium ${view === 'register' ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-100'}`}>Register</button>
                            <button onClick={() => navigate('org_create')} className={`px-4 py-2 rounded-lg text-sm font-medium ${view === 'org_create' ? 'bg-indigo-600 text-white' : 'text-indigo-600 border border-indigo-600 hover:bg-indigo-50'}`}>Create Org</button>
                        </>
                    )}
                </nav>
            </header>
            
            {/* Main Content Area */}
            {renderView()}

            <footer className="mt-12 text-center text-gray-400 text-xs">
                SalesForge Front-end Demo (React + Tailwind)
            </footer>
        </div>
    );
}