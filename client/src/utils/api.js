const API_BASE_URL = 'http://localhost:8000'; // FastAPI backend URL

/**
 * Main API fetch helper.
 * Handles JSON, FormData, and URL-encoded login requests.
 */
export const apiFetch = async (endpoint, method = 'POST', body = null, token = null) => {
    const headers = {};
    let finalBody = body;
    let fetchUrl = `${API_BASE_URL}${endpoint}`;

    // --- Special Handling for Login (x-www-form-urlencoded) ---
    if (endpoint === '/auth/login') {
        headers['Content-Type'] = 'application/x-www-form-urlencoded';
        const formBody = new URLSearchParams();
        formBody.append('username', body.username);
        formBody.append('password', body.password);
        finalBody = formBody.toString();
    
    // --- Handling for FormData (File Uploads) ---
    } else if (body instanceof FormData) {
        // Let the browser set the Content-Type header automatically
        // It will include the correct 'boundary' for multipart
        finalBody = body;
    
    // --- Default Handling for JSON ---
    } else if (body) {
        headers['Content-Type'] = 'application/json';
        finalBody = JSON.stringify(body);
    }

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    try {
        const response = await fetch(fetchUrl, {
            method,
            headers,
            body: finalBody,
        });

        // Handle 204 No Content (e.g., DELETE success)
        if (response.status === 204) {
            return { message: 'Success' }; // Return a success object
        }

        const data = await response.json();

        if (!response.ok) {
            let errorMessage = data.detail || 'An unknown server error occurred.';
            // Format FastAPI 422 validation errors
            if (Array.isArray(data.detail)) {
                errorMessage = data.detail.map(err => {
                    const loc = err.loc[err.loc.length - 1]; // Get the field name
                    return `${loc}: ${err.msg}`;
                }).join(', ');
            }
            throw new Error(errorMessage);
        }
        
        return data;

    } catch (error) {
        // Handle network errors or if response isn't JSON
        console.error("API Fetch Error:", error);
        throw new Error(error.message || 'A network error occurred.');
    }
};

// --- Authentication Endpoints ---
export const auth = {
    // FIX: Simplified to just pass credentials to apiFetch
    login: (username, password) => 
        apiFetch('/auth/login', 'POST', { username, password }),

    register: (token, password) => 
        apiFetch('/auth/register', 'POST', { token, password }),

    getMe: (token) => 
        apiFetch('/users/me', 'GET', null, token),

    createOrg: (orgData) => 
        apiFetch('/orgs', 'POST', orgData),
};

// --- Content and RAG Endpoints ---
export const content = {
    /**
     * Uploads a file and metadata. Now uses apiFetch.
     */
    upload: (orgId, metadata, file, token) => {
        const formData = new FormData();
        formData.append('product_name', metadata.product_name);
        formData.append('version', metadata.version);
        formData.append('file', file);
        
        // apiFetch will correctly handle FormData
        return apiFetch(`/orgs/${orgId}/content/upload`, 'POST', formData, token);
    },

    /**
     * Retrieves relevant chunks from the vector store.
     */
    retrieve: (orgId, query, k, token) => 
        apiFetch(`/orgs/${orgId}/retriever?q=${encodeURIComponent(query)}&k=${k}`, 'GET', null, token),

    /**
     * NEW: Lists all uploaded documents for an org.
     * FIX: Corrected variable name from org_id to orgId
     */
    listContent: (orgId, token) =>
        apiFetch(`/orgs/${orgId}/content`, 'GET', null, token),

    /**
     * NEW: Deletes a document (from SQL and Chroma).
     * FIX: Corrected variable name from org_id to orgId
     */
    deleteContent: (orgId, contentId, token) =>
        apiFetch(`/orgs/${orgId}/content/${contentId}`, 'DELETE', null, token),
};
