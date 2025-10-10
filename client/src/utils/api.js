// src/utils/api.js

const API_BASE_URL = 'http://localhost:8000'; // Assumes FastAPI is running on port 8000

export const apiFetch = async (endpoint, method = 'GET', body = null, token = null) => {
    const headers = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    let config = {
        method,
        headers,
        body: body ? JSON.stringify(body) : null,
    };

    // --- Special handling for OAuth2 login (x-www-form-urlencoded) ---
    if (endpoint === '/auth/login' && method === 'POST') {
        const formBody = new URLSearchParams();
        formBody.append('username', body.username);
        formBody.append('password', body.password);
        
        config = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formBody.toString(),
        };
    }
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || response.statusText || 'An unknown error occurred.');
    }

    // Default handling for JSON responses
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.indexOf("application/json") !== -1) {
        return await response.json();
    }

    return response; // Return response object for non-json or successful 204
};