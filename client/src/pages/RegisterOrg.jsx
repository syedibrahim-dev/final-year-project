import React, { useState } from 'react';
import { Briefcase, Key } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Card, Input, Button } from '../App';

const roles = ["admin", "manager", "trainer", "trainee"];

// Organization Creation View
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
            // ✅ FIX: Use /orgs (not /api/orgs)
            const org = await apiFetch('/orgs', 'POST', formData);
            
            setMessage(`✅ Organization "${org.name}" created successfully! Admin user registered. Redirecting to login...`);
            
            setFormData({ name: '', admin_email: '', admin_password: '' });
            
            setTimeout(() => navigate('/login'), 2000); 
            
        } catch (error) {
            console.error('Organization creation error:', error);
            
            if (error.message.includes('already exists')) {
                setMessage('❌ Organization name or admin email already exists.');
            } else if (error.message.includes('8 characters')) {
                setMessage('❌ Password must be at least 8 characters long.');
            } else {
                setMessage(`❌ Error: ${error.message}`);
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card title="Create New Organization" icon={<Briefcase />}>
            <form onSubmit={handleSubmit} className="space-y-4">
                <Input 
                    name="name" 
                    type="text" 
                    label="Organization Name" 
                    value={formData.name} 
                    onChange={handleChange} 
                    required 
                    placeholder="e.g., Acme Corporation"
                />
                <Input 
                    name="admin_email" 
                    type="email" 
                    label="Admin Email" 
                    value={formData.admin_email} 
                    onChange={handleChange} 
                    required 
                    placeholder="admin@example.com"
                />
                <Input 
                    name="admin_password" 
                    type="password" 
                    label="Admin Password (min 8 chars)" 
                    value={formData.admin_password} 
                    onChange={handleChange} 
                    required 
                    minLength={8}
                    placeholder="••••••••"
                />
                <Button type="submit" loading={loading} disabled={loading}>
                    {loading ? 'Creating...' : 'Register Organization'}
                </Button>
            </form>
            {message && (
                <p className={`mt-4 text-sm font-medium ${
                    message.startsWith('❌') ? 'text-red-600' : 'text-green-600'
                }`}>
                    {message}
                </p>
            )}
        </Card>
    );
};

// User Registration via Invite Token View
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
            const result = await apiFetch('/auth/register', 'POST', formData);
            
            setMessage('✅ Registration complete! Logging you in...');
            
            setFormData({ token: '', password: '' });
            
            setTimeout(() => navigate('/dashboard', result), 1500);
            
        } catch (error) {
            console.error('Registration error:', error);
            
            if (error.message.includes('expired') || error.message.includes('invalid')) {
                setMessage('❌ Invalid or expired invite token.');
            } else if (error.message.includes('8 characters')) {
                setMessage('❌ Password must be at least 8 characters long.');
            } else {
                setMessage(`❌ Error: ${error.message}`);
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card title="Complete Registration" icon={<Key />}>
            <p className="text-sm text-gray-500 mb-4">
                Enter the invite token you received and set your password.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
                <Input 
                    name="token" 
                    type="text" 
                    label="Invite Token" 
                    value={formData.token} 
                    onChange={handleChange} 
                    required 
                    placeholder="Paste your invite token here"
                />
                <Input 
                    name="password" 
                    type="password" 
                    label="New Password (min 8 chars)" 
                    value={formData.password} 
                    onChange={handleChange} 
                    required 
                    minLength={8}
                    placeholder="••••••••"
                />
                <Button type="submit" loading={loading} disabled={loading}>
                    {loading ? 'Registering...' : 'Set Password & Login'}
                </Button>
            </form>
            {message && (
                <p className={`mt-4 text-sm font-medium ${
                    message.startsWith('❌') ? 'text-red-600' : 'text-green-600'
                }`}>
                    {message}
                </p>
            )}
        </Card>
    );
};

export { OrgCreateView, RegisterView, roles };