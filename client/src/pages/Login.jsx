import React, { useState } from 'react';
import { LogIn } from 'lucide-react';
import { apiFetch } from '../utils/api';
// Assuming App.jsx exports Card, Input, and Button for UI consistency
import { Card, Input, Button } from '../App'; 

const LoginView = ({ navigate }) => {
    const [formData, setFormData] = useState({ username: '', password: '' });
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
            const result = await apiFetch('/auth/login', 'POST', {
                username: formData.username,
                password: formData.password
            });
            setMessage('Login successful!');
            navigate('dashboard', result);
        } catch (error) {
            setMessage(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card title="User Login" icon={<LogIn />}>
            <form onSubmit={handleSubmit} className="space-y-4">
                <Input name="username" type="email" label="Email" value={formData.username} onChange={handleChange} required />
                <Input name="password" type="password" label="Password" value={formData.password} onChange={handleChange} required />
                <Button type="submit" loading={loading}>
                    {loading ? 'Logging in...' : 'Login'}
                </Button>
            </form>
            {message && <p className={`mt-4 text-sm font-medium ${message.startsWith('Error') ? 'text-red-600' : 'text-green-600'}`}>{message}</p>}
            
            <div className="mt-6 pt-4 border-t border-gray-100 text-sm text-center">
                <p>New Company? <button onClick={() => navigate('org_create')} className="text-indigo-600 hover:text-indigo-800 font-medium">Create Organization</button></p>
                <p>Invited? <button onClick={() => navigate('register')} className="text-indigo-600 hover:text-indigo-800 font-medium">Complete Registration</button></p>
            </div>
        </Card>
    );
};

export default LoginView;