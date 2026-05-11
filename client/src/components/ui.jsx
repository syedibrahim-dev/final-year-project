import React from 'react';
import { Loader2, ChevronRight, ArrowLeft, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// ── Button ──────────────────────────────────────────────────────────────────
export const Button = ({
    children, onClick, type = 'button', loading = false,
    disabled = false, className = '', variant = 'primary', size = 'md'
}) => {
    const base = 'inline-flex items-center justify-center font-semibold rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed';
    const sizes = {
        sm: 'px-3 py-1.5 text-xs',
        md: 'px-4 py-2.5 text-sm',
        lg: 'px-5 py-3 text-sm',
    };
    const variants = {
        primary: 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500 shadow-sm',
        secondary: 'bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 focus:ring-slate-400 shadow-sm',
        danger: 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500 shadow-sm',
        ghost: 'bg-transparent hover:bg-slate-100 text-slate-600 focus:ring-slate-400',
        teal: 'bg-teal-600 hover:bg-teal-700 text-white focus:ring-teal-500 shadow-sm',
    };

    return (
        <button
            type={type}
            onClick={onClick}
            disabled={loading || disabled}
            className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
        >
            {loading && <Loader2 className="animate-spin -ml-0.5 mr-1.5 h-3.5 w-3.5" />}
            {children}
        </button>
    );
};

// ── Input ───────────────────────────────────────────────────────────────────
export const Input = ({
    name, label, type = 'text', value, onChange, required = false,
    disabled = false, placeholder = '', minLength, className = ''
}) => (
    <div className={className}>
        {label && (
            <label htmlFor={name} className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                {label}
            </label>
        )}
        <input
            id={name}
            name={name}
            type={type}
            value={value}
            onChange={onChange}
            required={required}
            disabled={disabled}
            placeholder={placeholder}
            minLength={minLength}
            className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg bg-white text-slate-800 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-colors disabled:bg-slate-50 disabled:text-slate-400"
        />
    </div>
);

// ── Textarea ─────────────────────────────────────────────────────────────────
export const Textarea = ({
    name, label, value, onChange, required = false,
    disabled = false, placeholder = '', rows = 4, className = ''
}) => (
    <div className={className}>
        {label && (
            <label htmlFor={name} className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                {label}
            </label>
        )}
        <textarea
            id={name}
            name={name}
            value={value}
            onChange={onChange}
            required={required}
            disabled={disabled}
            placeholder={placeholder}
            rows={rows}
            className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg bg-white text-slate-800 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-colors resize-none disabled:bg-slate-50"
        />
    </div>
);

// ── Select ───────────────────────────────────────────────────────────────────
export const Select = ({
    name, label, value, options, onChange, required = false,
    disabled = false, className = ''
}) => (
    <div className={className}>
        {label && (
            <label htmlFor={name} className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                {label}
            </label>
        )}
        <select
            id={name}
            name={name}
            value={value}
            onChange={onChange}
            required={required}
            disabled={disabled}
            className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg bg-white text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-colors cursor-pointer disabled:bg-slate-50"
        >
            {options.map(opt => {
                const val = typeof opt === 'object' ? opt.value : opt;
                const label = typeof opt === 'object' ? opt.label : opt.charAt(0).toUpperCase() + opt.slice(1);
                return <option key={val} value={val}>{label}</option>;
            })}
        </select>
    </div>
);

// ── Card ─────────────────────────────────────────────────────────────────────
export const Card = ({ children, className = '', onClick }) => (
    <div
        onClick={onClick}
        className={`bg-white border border-slate-200 rounded-xl shadow-sm ${onClick ? 'cursor-pointer hover:border-blue-300 hover:shadow-md transition-all duration-200' : ''} ${className}`}
    >
        {children}
    </div>
);

// ── PageHeader ────────────────────────────────────────────────────────────────
// Shows page title, subtitle, optional back button, and optional action slot
export const PageHeader = ({ title, subtitle, backTo, backLabel = 'Back', action }) => {
    const navigate = useNavigate();
    return (
        <div className="mb-6">
            {backTo && (
                <button
                    onClick={() => navigate(backTo)}
                    className="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-blue-600 mb-3 transition-colors group"
                >
                    <ArrowLeft size={13} className="group-hover:-translate-x-0.5 transition-transform" />
                    {backLabel}
                </button>
            )}
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
                    {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
                </div>
                {action && <div className="flex-shrink-0">{action}</div>}
            </div>
        </div>
    );
};

// ── RelatedLinks ──────────────────────────────────────────────────────────────
// Footer bar of contextual "you might also need" links
export const RelatedLinks = ({ links }) => {
    const navigate = useNavigate();
    if (!links || links.length === 0) return null;
    return (
        <div className="mt-8 pt-5 border-t border-slate-100">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Related</p>
            <div className="flex flex-wrap gap-2">
                {links.map(({ label, to }) => (
                    <button
                        key={to}
                        onClick={() => navigate(to)}
                        className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors"
                    >
                        {label}
                        <ChevronRight size={11} />
                    </button>
                ))}
            </div>
        </div>
    );
};

// ── StatusBadge ───────────────────────────────────────────────────────────────
export const StatusBadge = ({ label, color = 'slate' }) => {
    const colors = {
        slate: 'bg-slate-100 text-slate-600',
        blue: 'bg-blue-50 text-blue-700',
        teal: 'bg-teal-50 text-teal-700',
        amber: 'bg-amber-50 text-amber-700',
        red: 'bg-red-50 text-red-700',
        green: 'bg-green-50 text-green-700',
        violet: 'bg-violet-50 text-violet-700',
    };
    return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold ${colors[color] || colors.slate}`}>
            {label}
        </span>
    );
};

// ── Spinner ───────────────────────────────────────────────────────────────────
export const Spinner = ({ text = 'Loading...' }) => (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Loader2 className="h-7 w-7 animate-spin text-blue-500" />
        <p className="text-sm text-slate-500">{text}</p>
    </div>
);

// ── EmptyState ────────────────────────────────────────────────────────────────
export const EmptyState = ({ icon: Icon, title, description, action }) => (
    <div className="flex flex-col items-center justify-center py-16 text-center">
        {Icon && (
            <div className="w-14 h-14 bg-slate-100 rounded-xl flex items-center justify-center mb-4">
                <Icon size={24} className="text-slate-400" />
            </div>
        )}
        <p className="text-sm font-semibold text-slate-700 mb-1">{title}</p>
        {description && <p className="text-xs text-slate-400 max-w-xs">{description}</p>}
        {action && <div className="mt-4">{action}</div>}
    </div>
);

// ── Toast-style inline alert ──────────────────────────────────────────────────
export const Alert = ({ message, type = 'error', className = '' }) => {
    if (!message) return null;
    const styles = {
        error: 'bg-red-50 text-red-700 border-red-200',
        success: 'bg-teal-50 text-teal-700 border-teal-200',
        info: 'bg-blue-50 text-blue-700 border-blue-200',
        warning: 'bg-amber-50 text-amber-700 border-amber-200',
    };
    return (
        <div className={`px-4 py-3 rounded-lg border text-sm font-medium ${styles[type]} ${className}`}>
            {message}
        </div>
    );
};
