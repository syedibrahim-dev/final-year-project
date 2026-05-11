import React, { useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
    LayoutDashboard, Brain, MessageCircle, Search, MessageSquare,
    FileText, BarChart2, Upload, FolderOpen, UserPlus, Sparkles,
    Package, Activity, TrendingUp, LogOut, Zap, Menu, X, ChevronRight,
    User
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

// ── Nav item ─────────────────────────────────────────────────────────────────
const NavItem = ({ to, icon: Icon, label, onClick }) => (
    <NavLink
        to={to}
        onClick={onClick}
        className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors duration-150 relative group ${
                isActive
                    ? 'bg-white/[0.08] text-white'
                    : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-200'
            }`
        }
    >
        {({ isActive }) => (
            <>
                {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-blue-400 rounded-r-full" />
                )}
                <Icon size={16} className={`flex-shrink-0 transition-colors ${isActive ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'}`} />
                <span className="truncate">{label}</span>
            </>
        )}
    </NavLink>
);

// ── Section label ─────────────────────────────────────────────────────────────
const NavSection = ({ label }) => (
    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-600 px-3 pt-5 pb-1.5">
        {label}
    </p>
);

// ── Sidebar content ───────────────────────────────────────────────────────────
const SidebarContent = ({ user, logout, onNavClick }) => {
    const navigate = useNavigate();
    const isManager = ['admin', 'manager'].includes(user?.role);
    const isTrainer = ['admin', 'manager', 'trainer'].includes(user?.role);

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <div className="flex flex-col h-full">
            {/* Brand */}
            <div className="flex items-center gap-3 px-4 py-5 border-b border-white/[0.06]">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center flex-shrink-0 shadow-md shadow-blue-900/40">
                    <Zap size={16} className="text-white" />
                </div>
                <div className="min-w-0">
                    <p className="text-sm font-bold text-white truncate">SalesForge AI</p>
                    <p className="text-[10px] text-blue-400 font-semibold uppercase tracking-wide">{user?.role || 'Loading'}</p>
                </div>
            </div>

            {/* User badge */}
            <div className="px-3 py-3">
                <button
                    onClick={() => { navigate('/profile'); onNavClick?.(); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.05] transition-colors group"
                >
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-teal-500 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                        {(user?.full_name || user?.email || 'U')[0].toUpperCase()}
                    </div>
                    <div className="min-w-0 text-left">
                        <p className="text-xs font-semibold text-white truncate">{user?.full_name || user?.email?.split('@')[0]}</p>
                        <p className="text-[10px] text-slate-500 truncate">{user?.email}</p>
                    </div>
                    <ChevronRight size={12} className="ml-auto text-slate-600 group-hover:text-slate-400 flex-shrink-0" />
                </button>
            </div>

            {/* Nav items */}
            <nav className="flex-1 overflow-y-auto px-3 pb-4 space-y-0.5">
                <NavSection label="Overview" />
                <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" onClick={onNavClick} />

                <NavSection label="Training" />
                <NavItem to="/mcq" icon={Brain} label="MCQ Practice" onClick={onNavClick} />
                <NavItem to="/roleplay" icon={MessageCircle} label="AI Roleplay" onClick={onNavClick} />
                <NavItem to="/knowledge-chat" icon={MessageSquare} label="Knowledge Chat" onClick={onNavClick} />
                <NavItem to="/search" icon={Search} label="Search Docs" onClick={onNavClick} />

                {isTrainer && (
                    <>
                        <NavSection label="Management" />
                        <NavItem to="/tests/create" icon={FileText} label="Create MCQ Test" onClick={onNavClick} />
                        <NavItem to="/performance" icon={BarChart2} label="Performance" onClick={onNavClick} />

                        <NavSection label="Content" />
                        <NavItem to="/content/upload" icon={Upload} label="Upload Content" onClick={onNavClick} />
                        <NavItem to="/content/manage" icon={FolderOpen} label="Manage Content" onClick={onNavClick} />

                        <NavSection label="Team" />
                        <NavItem to="/team/invite" icon={UserPlus} label="Invite Member" onClick={onNavClick} />
                    </>
                )}

                {isManager && (
                    <>
                        <NavSection label="Automation" />
                        <NavItem to="/marketing" icon={Sparkles} label="Marketing Posts" onClick={onNavClick} />
                        <NavItem to="/inventory" icon={Package} label="Inventory Forecasts" onClick={onNavClick} />
                        <NavItem to="/analytics" icon={Activity} label="Transaction Analytics" onClick={onNavClick} />
                        <NavItem to="/leads" icon={TrendingUp} label="Lead Scoring" onClick={onNavClick} />
                    </>
                )}
            </nav>

            {/* Sign out */}
            <div className="px-3 pb-4 border-t border-white/[0.06] pt-3">
                <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/[0.08] transition-colors text-[13px] font-medium"
                >
                    <LogOut size={15} />
                    Sign Out
                </button>
            </div>
        </div>
    );
};

// ── Layout shell ──────────────────────────────────────────────────────────────
export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const location = useLocation();
    const [sidebarOpen, setSidebarOpen] = useState(false);

    // Build breadcrumb from pathname
    const crumbs = {
        '/dashboard': 'Dashboard',
        '/profile': 'My Profile',
        '/mcq': 'MCQ Practice',
        '/roleplay': 'AI Roleplay',
        '/roleplay/chat': 'Session',
        '/roleplay/feedback': 'Feedback',
        '/knowledge-chat': 'Knowledge Chat',
        '/search': 'Search Docs',
        '/tests/create': 'Create MCQ Test',
        '/performance': 'Performance',
        '/content/upload': 'Upload Content',
        '/content/manage': 'Manage Content',
        '/team/invite': 'Invite Member',
        '/marketing': 'Marketing Posts',
        '/inventory': 'Inventory Forecasts',
        '/analytics': 'Transaction Analytics',
        '/leads': 'Lead Scoring',
    };
    const pathKey = Object.keys(crumbs).find(k => location.pathname.startsWith(k) && k !== '/dashboard') || location.pathname;
    const currentLabel = crumbs[pathKey] || crumbs[location.pathname] || 'Page';

    return (
        <div className="flex h-screen bg-slate-50 overflow-hidden">
            {/* ── Desktop sidebar ── */}
            <aside className="hidden lg:flex flex-col w-60 flex-shrink-0 bg-slate-900 border-r border-white/[0.04]">
                <SidebarContent user={user} logout={logout} />
            </aside>

            {/* ── Mobile sidebar drawer ── */}
            {sidebarOpen && (
                <div className="lg:hidden fixed inset-0 z-50 flex">
                    <div
                        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
                        onClick={() => setSidebarOpen(false)}
                    />
                    <aside className="relative flex flex-col w-72 bg-slate-900 shadow-2xl z-10">
                        <SidebarContent user={user} logout={logout} onNavClick={() => setSidebarOpen(false)} />
                    </aside>
                </div>
            )}

            {/* ── Main column ── */}
            <div className="flex flex-col flex-1 min-w-0">
                {/* Top bar */}
                <header className="flex items-center gap-4 px-5 py-3.5 bg-white border-b border-slate-200 flex-shrink-0">
                    {/* Hamburger (mobile) */}
                    <button
                        onClick={() => setSidebarOpen(true)}
                        className="lg:hidden p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
                    >
                        <Menu size={20} />
                    </button>

                    {/* Breadcrumb */}
                    <div className="flex items-center gap-2 text-sm">
                        <span className="text-slate-400 hidden sm:inline">SalesForge</span>
                        <ChevronRight size={13} className="text-slate-300 hidden sm:inline" />
                        <span className="font-semibold text-slate-800">{currentLabel}</span>
                    </div>

                    {/* Right side — user avatar */}
                    <div className="ml-auto flex items-center gap-2">
                        <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-teal-500 rounded-lg flex items-center justify-center text-white text-xs font-bold">
                            {(user?.full_name || user?.email || 'U')[0].toUpperCase()}
                        </div>
                        <span className="hidden sm:block text-sm font-medium text-slate-700 truncate max-w-[120px]">
                            {user?.full_name || user?.email?.split('@')[0]}
                        </span>
                    </div>
                </header>

                {/* Page content */}
                <main className="flex-1 overflow-y-auto">
                    <div className="max-w-6xl mx-auto px-5 py-6">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}
