import React, { useState } from 'react';
import { LogIn } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { Card, Input, Button } from '../App'; 

const LoginView = ({ navigate }) => {
    const [formData, setFormData] = useState({ email: '', password: '' });
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        // Clear message when user starts typing
        if (message) setMessage('');
    };

    const validateForm = () => {
        if (!formData.email.includes('@')) {
            setMessage('Please enter a valid email address');
            return false;
        }
        if (formData.password.length < 6) {
            setMessage('Password must be at least 6 characters');
            return false;
        }
        return true;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!validateForm()) {
            return;
        }
        
        setLoading(true);
        setMessage('');
        
        try {
            const result = await apiFetch('/auth/login', 'POST', {
                username: formData.email, // Backend expects 'username' field
                password: formData.password
            });
            setMessage('Login successful! Redirecting...');
            setTimeout(() => navigate('dashboard', result), 500);
        } catch (error) {
            setMessage(`Login failed: ${error.message || 'Invalid credentials'}`);
            setFormData(prev => ({ ...prev, password: '' })); // Clear password
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card title="User Login" icon={<LogIn />}>
            <form onSubmit={handleSubmit} className="space-y-4">
                <Input 
                    name="email" 
                    type="email" 
                    label="Email" 
                    value={formData.email} 
                    onChange={handleChange} 
                    required 
                    placeholder="you@example.com"
                />
                <Input 
                    name="password" 
                    type="password" 
                    label="Password" 
                    value={formData.password} 
                    onChange={handleChange} 
                    required 
                    placeholder="Enter your password"
                />
                <Button type="submit" loading={loading}>
                    {loading ? 'Logging in...' : 'Login'}
                </Button>
            </form>
            
            {message && (
                <div className={`mt-4 p-3 rounded-lg text-sm font-medium ${
                    message.includes('successful') 
                        ? 'bg-green-50 text-green-700' 
                        : 'bg-red-50 text-red-700'
                }`}>
                    {message}
                </div>
            )}
            
            <div className="mt-6 pt-4 border-t border-gray-100 text-sm text-center space-y-2">
                <p className="text-gray-600">
                    New Company? {' '}
                    <button 
                        type="button"
                        onClick={() => navigate('org_create')} 
                        className="text-indigo-600 hover:text-indigo-800 font-medium underline"
                    >
                        Create Organization
                    </button>
                </p>
                <p className="text-gray-600">
                    Have an invite? {' '}
                    <button 
                        type="button"
                        onClick={() => navigate('register')} 
                        className="text-indigo-600 hover:text-indigo-800 font-medium underline"
                    >
                        Complete Registration
                    </button>
                </p>
            </div>
        </Card>
    );
};

export default LoginView;