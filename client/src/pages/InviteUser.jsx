import React, { useState } from 'react';
import { UserPlus } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../utils/api';
import { PageHeader, Input, Select, Button, Alert, RelatedLinks } from '../components/ui';

const ROLES = ['trainee', 'trainer', 'manager', 'admin'];

export default function InviteUser() {
    const { token, user } = useAuth();
    const [formData, setFormData] = useState({ email: '', role: 'trainee' });
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null); // { type, message }

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        setResult(null);
    };

    const handleInvite = async (e) => {
        e.preventDefault();
        setLoading(true);
        setResult(null);
        try {
            const url = `/orgs/${user.organization_id}/users/invite?email=${encodeURIComponent(formData.email)}&role=${formData.role}`;
            const response = await apiFetch(url, 'POST', null, token);
            const inviteToken = response.invite_token || response.token || '—';
            setResult({
                type: 'success',
                message: `Invitation sent to ${formData.email} with role "${formData.role}". Invite token: ${inviteToken}`,
            });
            setFormData({ email: '', role: 'trainee' });
        } catch (error) {
            setResult({ type: 'error', message: error.message });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <PageHeader
                title="Invite Team Member"
                subtitle="Generate an invite token to add someone to your organization"
                backTo="/dashboard"
                backLabel="Dashboard"
            />

            <div className="max-w-lg">
                <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                    <form onSubmit={handleInvite} className="space-y-5">
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
                            options={ROLES}
                            onChange={handleChange}
                            required
                        />
                        <Button type="submit" loading={loading} className="w-full">
                            <UserPlus size={15} className="mr-2" />
                            {loading ? 'Sending...' : 'Generate Invite'}
                        </Button>
                    </form>
                </div>

                {result && (
                    <Alert
                        message={result.message}
                        type={result.type === 'success' ? 'success' : 'error'}
                        className="mt-4 font-mono text-xs"
                    />
                )}

                <div className="mt-5 bg-slate-50 border border-slate-200 rounded-xl p-4">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">How it works</p>
                    <ol className="text-xs text-slate-500 space-y-1.5 list-decimal list-inside">
                        <li>Enter the invitee's email and select their role</li>
                        <li>Click Generate — an invite token is created</li>
                        <li>Share the token with the invitee</li>
                        <li>They paste it at <strong>/register</strong> to set their password</li>
                    </ol>
                </div>
            </div>

            <RelatedLinks links={[
                { label: 'Performance Dashboard', to: '/performance' },
                { label: 'Manage Content', to: '/content/manage' },
            ]} />
        </div>
    );
}
