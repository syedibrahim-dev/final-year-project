import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { auth as authApi } from '../utils/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [token, setToken] = useState(null);
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true); // true on first load

    // Fetch /users/me whenever token changes
    useEffect(() => {
        if (!token) {
            setUser(null);
            setLoading(false);
            return;
        }
        let cancelled = false;
        setLoading(true);
        authApi.getMe(token)
            .then(u => { if (!cancelled) setUser(u); })
            .catch(() => {
                if (!cancelled) {
                    setToken(null);
                    setUser(null);
                    localStorage.removeItem('sf_token');
                }
            })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [token]);

    // Restore token from localStorage on mount
    useEffect(() => {
        const stored = localStorage.getItem('sf_token');
        if (stored) setToken(stored);
        else setLoading(false);
    }, []);

    const login = useCallback((accessToken) => {
        localStorage.setItem('sf_token', accessToken);
        setToken(accessToken);
    }, []);

    const logout = useCallback(() => {
        localStorage.removeItem('sf_token');
        setToken(null);
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider value={{ token, user, loading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
    return ctx;
}
