// src/pages/RegisterOrg.jsx

import React, { useState } from 'react';
import { Briefcase, Key } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Card, Input, Button } from '../App'; // Assuming App exports UI components

const roles = ["admin", "manager", "trainer", "trainee"];

// 1. Organization Creation View (POST /orgs)
const OrgCreateView = ({ navigate }) => {
    const [formData, setFormData] = useState({ name: '', admin_email: '', admin_password: '' });
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage('');
        try {
            const org = await apiFetch('/orgs', 'POST', formData);
            // Note: The backend's org response is OrganizationOut, but the admin user is created.
            setMessage(`Organization "${org.name}" created successfully! Admin user registered. Please log in.`);
            navigate('login');
        } catch (error) {
            setMessage(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card title="Create New Organization" icon={<Briefcase />}>
            <form onSubmit={handleSubmit} className="space-y-4">
                <Input name="name" type="text" label="Organization Name" value={formData.name} onChange={handleChange} required />
                <Input name="admin_email" type="email" label="Admin Email" value={formData.admin_email} onChange={handleChange} required />
                <Input name="admin_password" type="password" label="Admin Password" value={formData.admin_password} onChange={handleChange} required />
                <Button type="submit" loading={loading}>
                    {loading ? 'Creating...' : 'Register Organization'}
                </Button>
            </form>
            {message && <p className={`mt-4 text-sm font-medium ${message.startsWith('Error') ? 'text-red-600' : 'text-green-600'}`}>{message}</p>}
        </Card>
    );
};

// 2. User Registration via Invite Token View (POST /auth/register)
const RegisterView = ({ navigate }) => {
    const [formData, setFormData] = useState({ token: '', password: '' });
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage('');
        try {
            // Note: Token and password are sent as JSON, the response is a JWT token
            const result = await apiFetch('/auth/register', 'POST', formData);
            setMessage('Registration complete! Logging you in...');
            navigate('dashboard', result);
        } catch (error) {
            setMessage(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card title="Complete Registration" icon={<Key />}>
            <p className="text-sm text-gray-500 mb-4">Enter the invite token and set your password.</p>
            <form onSubmit={handleSubmit} className="space-y-4">
                <Input name="token" type="text" label="Invite Token" value={formData.token} onChange={handleChange} required />
                <Input name="password" type="password" label="New Password" value={formData.password} onChange={handleChange} required />
                <Button type="submit" loading={loading}>
                    {loading ? 'Registering...' : 'Set Password & Login'}
                </Button>
            </form>
            {message && <p className={`mt-4 text-sm font-medium ${message.startsWith('Error') ? 'text-red-600' : 'text-green-600'}`}>{message}</p>}
        </Card>
    );
};

export { OrgCreateView, RegisterView, roles }; // Export views and roles