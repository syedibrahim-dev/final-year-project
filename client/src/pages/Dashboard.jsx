import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Brain, MessageCircle, MessageSquare, Search,
    FileText, BarChart2, Upload, FolderOpen, UserPlus,
    Sparkles, Package, Activity, TrendingUp, ChevronRight,
    ArrowRight
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

// ── Feature card definition ──────────────────────────────────────────────────
const FEATURE_CARDS = {
    training: [
        {
            to: '/mcq',
            icon: Brain,
            title: 'MCQ Practice',
            description: 'Take AI-generated quizzes on product knowledge, objection handling, and sales techniques. Track your scores over time.',
            color: 'blue',
        },
        {
            to: '/roleplay',
            icon: MessageCircle,
            title: 'AI Roleplay',
            description: 'Practice live sales conversations with AI buyer personas of varying difficulty. Get coached in real time.',
            color: 'teal',
        },
        {
            to: '/knowledge-chat',
            icon: MessageSquare,
            title: 'Knowledge Chat',
            description: 'Ask questions about your organization\'s uploaded documents and get instant AI-powered answers with source citations.',
            color: 'violet',
        },
        {
            to: '/search',
            icon: Search,
            title: 'Search Docs',
            description: 'Run semantic searches across your training content to find specific information fast.',
            color: 'amber',
        },
    ],
    management: [
        {
            to: '/tests/create',
            icon: FileText,
            title: 'Create MCQ Test',
            description: 'Generate and publish quiz tests for your team using AI. Set topic, difficulty, and number of questions.',
            color: 'blue',
        },
        {
            to: '/performance',
            icon: BarChart2,
            title: 'Performance Dashboard',
            description: 'Monitor team-wide MCQ scores, roleplay ratings, and training activity. Export reports for review.',
            color: 'indigo',
        },
        {
            to: '/content/upload',
            icon: Upload,
            title: 'Upload Content',
            description: 'Add PDFs, Word documents, or media files to your knowledge base. Also supports scraping from URLs.',
            color: 'teal',
        },
        {
            to: '/content/manage',
            icon: FolderOpen,
            title: 'Manage Content',
            description: 'View, search, and delete training documents in your organization\'s knowledge base.',
            color: 'slate',
        },
        {
            to: '/team/invite',
            icon: UserPlus,
            title: 'Invite Member',
            description: 'Generate invite tokens to add trainers and trainees to your organization.',
            color: 'violet',
        },
    ],
    automation: [
        {
            to: '/marketing',
            icon: Sparkles,
            title: 'Marketing Posts',
            description: 'Generate AI-written social media captions and images for LinkedIn and Twitter. Schedule or post instantly.',
            color: 'pink',
        },
        {
            to: '/inventory',
            icon: Package,
            title: 'Inventory Forecasts',
            description: 'Upload sales data and get AI-powered demand forecasts and stock-level recommendations.',
            color: 'amber',
        },
        {
            to: '/analytics',
            icon: Activity,
            title: 'Transaction Analytics',
            description: 'Detect anomalies and trends in your transaction data with ML-powered analysis and charts.',
            color: 'red',
        },
        {
            to: '/leads',
            icon: TrendingUp,
            title: 'Lead Scoring',
            description: 'Upload your CRM leads and get AI win-probability scores. Prioritize outreach and allocate reps.',
            color: 'green',
        },
    ],
};

const COLOR_MAP = {
    blue:   { icon: 'bg-blue-50 text-blue-600',   ring: 'group-hover:ring-blue-200',   badge: 'bg-blue-600' },
    teal:   { icon: 'bg-teal-50 text-teal-600',   ring: 'group-hover:ring-teal-200',   badge: 'bg-teal-600' },
    violet: { icon: 'bg-violet-50 text-violet-600', ring: 'group-hover:ring-violet-200', badge: 'bg-violet-600' },
    amber:  { icon: 'bg-amber-50 text-amber-600',  ring: 'group-hover:ring-amber-200',  badge: 'bg-amber-600' },
    indigo: { icon: 'bg-indigo-50 text-indigo-600', ring: 'group-hover:ring-indigo-200', badge: 'bg-indigo-600' },
    slate:  { icon: 'bg-slate-100 text-slate-600', ring: 'group-hover:ring-slate-200',  badge: 'bg-slate-600' },
    pink:   { icon: 'bg-pink-50 text-pink-600',   ring: 'group-hover:ring-pink-200',   badge: 'bg-pink-600' },
    red:    { icon: 'bg-red-50 text-red-600',     ring: 'group-hover:ring-red-200',    badge: 'bg-red-600' },
    green:  { icon: 'bg-green-50 text-green-600', ring: 'group-hover:ring-green-200',  badge: 'bg-green-600' },
};

// ── Feature card ─────────────────────────────────────────────────────────────
function FeatureCard({ to, icon: Icon, title, description, color }) {
    const navigate = useNavigate();
    const c = COLOR_MAP[color] || COLOR_MAP.blue;
    return (
        <button
            onClick={() => navigate(to)}
            className={`group w-full text-left bg-white border border-slate-200 rounded-xl p-5 hover:border-slate-300 hover:shadow-md transition-all duration-200 ring-2 ring-transparent ${c.ring} focus:outline-none focus:ring-2 focus:ring-blue-400`}
        >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${c.icon}`}>
                <Icon size={20} />
            </div>
            <h3 className="text-sm font-bold text-slate-800 mb-1.5">{title}</h3>
            <p className="text-xs text-slate-500 leading-relaxed mb-4">{description}</p>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 group-hover:gap-2 transition-all">
                Open <ArrowRight size={11} />
            </span>
        </button>
    );
}

// ── Section ──────────────────────────────────────────────────────────────────
function Section({ title, cards }) {
    return (
        <div className="mb-8">
            <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">{title}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {cards.map(card => <FeatureCard key={card.to} {...card} />)}
            </div>
        </div>
    );
}

// ── Quick stat card ───────────────────────────────────────────────────────────
function StatCard({ label, value, sub, color }) {
    const colors = {
        blue: 'border-blue-200 bg-blue-50/50',
        teal: 'border-teal-200 bg-teal-50/50',
        violet: 'border-violet-200 bg-violet-50/50',
    };
    return (
        <div className={`border rounded-xl p-4 ${colors[color] || colors.blue}`}>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</p>
            <p className="text-2xl font-bold text-slate-800 mt-1">{value}</p>
            {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
        </div>
    );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export default function Dashboard() {
    const { user } = useAuth();
    const navigate = useNavigate();

    const isManager = ['admin', 'manager'].includes(user?.role);
    const isTrainer = ['admin', 'manager', 'trainer'].includes(user?.role);

    const hour = new Date().getHours();
    const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
    const displayName = user?.full_name || user?.email?.split('@')[0] || 'there';

    return (
        <div>
            {/* Greeting */}
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-slate-900">
                    {greeting}, {displayName}
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                    Welcome to SalesForge AI — your sales training workspace.
                </p>
            </div>

            {/* Quick stats row */}
            <div className="grid grid-cols-3 gap-4 mb-10">
                <StatCard label="Your Role" value={user?.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : '—'} sub={`Org #${user?.organization_id}`} color="blue" />
                <StatCard label="Status" value="Active" sub="Account in good standing" color="teal" />
                <StatCard label="Member Since" value={user?.created_at ? new Date(user.created_at).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }) : '—'} sub="SalesForge member" color="violet" />
            </div>

            {/* Training section — all roles */}
            <Section title="Training" cards={FEATURE_CARDS.training} />

            {/* Management section — trainer+ */}
            {isTrainer && (
                <Section title="Management" cards={FEATURE_CARDS.management} />
            )}

            {/* Automation section — manager+ */}
            {isManager && (
                <Section title="Automation" cards={FEATURE_CARDS.automation} />
            )}
        </div>
    );
}
