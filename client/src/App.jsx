import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';

// Auth pages
import LoginView from './pages/Login';
import { OrgCreateView, RegisterView } from './pages/RegisterOrg';

// Authenticated pages
import Dashboard from './pages/Dashboard';
import ProfilePage from './pages/Profile';
import MCQPracticeView from './pages/MCQPractice';
import MCQTestCreator from './pages/MCQTestCreator';
import PerformanceDashboard from './pages/PerformanceDashboard';
import RoleplayPersonas from './pages/RoleplayPersonas';
import RoleplayChat from './pages/RoleplayChat';
import RoleplayFeedback from './pages/RoleplayFeedback';
import KnowledgeChatbot from './pages/KnowledgeChatbot';
import ContentRetrieverView from './pages/ContentRetriever';
import ContentUploadView from './pages/ContentUpload';
import ContentManagerView from './pages/ContentManager';
import MarketingPostCreator from './pages/MarketingPostCreator';
import InventoryManagerView from './pages/InventoryManager';
import TransactionAnalytics from './pages/TransactionAnalytics';
import LeadManager from './pages/LeadManager';
import InviteUser from './pages/InviteUser';

// ── Loading screen ──────────────────────────────────────────────────────────
function LoadingScreen() {
    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center">
            <div className="text-center">
                <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-sm text-slate-500 font-medium">Loading workspace...</p>
            </div>
        </div>
    );
}

// ── ProtectedRoute — redirects to /login if not authenticated ────────────────
function ProtectedRoute() {
    const { token, loading } = useAuth();
    if (loading) return <LoadingScreen />;
    if (!token) return <Navigate to="/login" replace />;
    return (
        <Layout>
            <Outlet />
        </Layout>
    );
}

// ── RoleRoute — redirects to /dashboard if role not met ────────────────────
function RoleRoute({ allowedRoles }) {
    const { user } = useAuth();
    if (!user) return <LoadingScreen />;
    if (!allowedRoles.includes(user.role)) return <Navigate to="/dashboard" replace />;
    return <Outlet />;
}

// ── PublicRoute — redirects to /dashboard if already logged in ───────────────
function PublicRoute() {
    const { token, loading } = useAuth();
    if (loading) return <LoadingScreen />;
    if (token) return <Navigate to="/dashboard" replace />;
    return (
        <div className="min-h-screen flex flex-col aurora-bg">
            <div className="aurora-blob" />
            <header className="max-w-5xl w-full mx-auto py-6 px-6 flex items-center gap-3 relative z-10">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-teal-500 rounded-lg flex items-center justify-center shadow-md">
                    <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
                    </svg>
                </div>
                <span className="text-lg font-bold text-slate-800">SalesForge AI</span>
            </header>
            <div className="flex-1 flex items-center justify-center px-4 pb-10 relative z-10">
                <Outlet />
            </div>
            <footer className="text-center py-5 relative z-10">
                <p className="text-xs text-slate-400">SalesForge AI — FYP 2026</p>
            </footer>
        </div>
    );
}

// ── Router ────────────────────────────────────────────────────────────────────
function AppRouter() {
    return (
        <Routes>
            {/* Public / auth routes */}
            <Route element={<PublicRoute />}>
                <Route path="/login" element={<LoginView />} />
                <Route path="/register" element={<RegisterView />} />
                <Route path="/org/create" element={<OrgCreateView />} />
            </Route>

            {/* Protected routes — all wrapped in Layout */}
            <Route element={<ProtectedRoute />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/profile" element={<ProfilePage />} />

                {/* Training — all roles */}
                <Route path="/mcq" element={<MCQPracticeView />} />
                <Route path="/roleplay" element={<RoleplayPersonas />} />
                <Route path="/roleplay/chat/:sessionId" element={<RoleplayChat />} />
                <Route path="/roleplay/feedback/:sessionId" element={<RoleplayFeedback />} />
                <Route path="/knowledge-chat" element={<KnowledgeChatbot />} />
                <Route path="/search" element={<ContentRetrieverView />} />

                {/* Management — trainer+ */}
                <Route element={<RoleRoute allowedRoles={['admin', 'manager', 'trainer']} />}>
                    <Route path="/tests/create" element={<MCQTestCreator />} />
                    <Route path="/performance" element={<PerformanceDashboard />} />
                    <Route path="/content/upload" element={<ContentUploadView />} />
                    <Route path="/content/manage" element={<ContentManagerView />} />
                    <Route path="/team/invite" element={<InviteUser />} />
                </Route>

                {/* Automation — manager+ */}
                <Route element={<RoleRoute allowedRoles={['admin', 'manager']} />}>
                    <Route path="/marketing" element={<MarketingPostCreator />} />
                    <Route path="/inventory" element={<InventoryManagerView />} />
                    <Route path="/analytics" element={<TransactionAnalytics />} />
                    <Route path="/leads" element={<LeadManager />} />
                </Route>
            </Route>

            {/* Catch-all */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
    );
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <AppRouter />
            </AuthProvider>
        </BrowserRouter>
    );
}
