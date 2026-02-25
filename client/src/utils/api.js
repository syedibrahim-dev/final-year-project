const API_BASE_URL = 'http://localhost:8000';

export const apiFetch = async (endpoint, method = 'POST', body = null, token = null) => {
    const headers = {};
    let finalBody = body;
    let fetchUrl = `${API_BASE_URL}${endpoint}`;

    if (endpoint === '/auth/login') {
        headers['Content-Type'] = 'application/x-www-form-urlencoded';
        const formBody = new URLSearchParams();
        formBody.append('username', body.username);
        formBody.append('password', body.password);
        finalBody = formBody.toString();
    } else if (body instanceof FormData) {
        finalBody = body;
    } else if (body) {
        headers['Content-Type'] = 'application/json';
        finalBody = JSON.stringify(body);
    }

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const options = { method, headers };
    if (finalBody && method !== 'GET') {
        options.body = finalBody;
    }

    try {
        const response = await fetch(fetchUrl, options);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("API Fetch Error:", error);
        throw new Error(error.message || 'A network error occurred.');
    }
};

// ========== AUTH APIs ==========
export const auth = {
    login: (username, password) => 
        apiFetch('/auth/login', 'POST', { username, password }),
    
    register: (token, password) => 
        apiFetch('/auth/register', 'POST', { token, password }),
    
    getMe: (token) => 
        apiFetch('/users/me', 'GET', null, token),
    
    createOrg: (orgData) => 
        apiFetch('/orgs/register', 'POST', orgData),
};

// ========== ORGANIZATION APIs ==========
export const organization = {
    get: (orgId, token) => 
        apiFetch(`/orgs/${orgId}`, 'GET', null, token),
    
    inviteUser: (orgId, inviteData, token) => 
        apiFetch(`/orgs/${orgId}/users/invite`, 'POST', inviteData, token),
    
    listUsers: (orgId, token) => 
        apiFetch(`/orgs/${orgId}/users/`, 'GET', null, token),
    
    updateUserRole: (orgId, userId, newRole, token) => 
        apiFetch(`/orgs/${orgId}/users/${userId}/role`, 'PATCH', { new_role: newRole }, token),
    
    removeUser: (orgId, userId, token) => 
        apiFetch(`/orgs/${orgId}/users/${userId}`, 'DELETE', null, token),
};

// ========== CONTENT APIs ==========
export const content = {
    upload: (orgId, file, version, token) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('version', version);
        
        console.log('📤 API Upload - FormData contents:');
        for (let pair of formData.entries()) {
            console.log(`   ${pair[0]}:`, pair[1]);
        }
        
        return apiFetch(`/orgs/${orgId}/content/upload`, 'POST', formData, token);
    },

    listContent: (orgId, token) =>
        apiFetch(`/orgs/${orgId}/content/`, 'GET', null, token),

    retrieve: (orgId, query, k, token) => 
        apiFetch(`/orgs/${orgId}/content/retrieve?query=${encodeURIComponent(query)}&k=${k}`, 'GET', null, token),

    deleteContent: (orgId, contentId, token) => {
        console.log('🗑️ API: Deleting content:', { orgId, contentId });
        return apiFetch(`/orgs/${orgId}/content/${contentId}`, 'DELETE', null, token);
    },
};

// ========== MCQ APIs (FIXED) ==========
export const mcq = {
    // ✅ FIXED: Removed /orgs/{orgId} prefix - backend uses /mcq directly
    generate: (orgId, requestData, token) => {
        const params = new URLSearchParams({
            topic: requestData.topic,
            difficulty: requestData.difficulty,
            num_questions: requestData.num_questions
        });
        return apiFetch(`/mcq/generate?${params.toString()}`, 'POST', null, token);
    },
    
    createTest: (orgId, testData, token) =>
        apiFetch('/mcq/tests', 'POST', testData, token),
    
    listTests: (orgId, token) =>
        apiFetch('/mcq/tests', 'GET', null, token),
    
    getTest: (orgId, testId, token) =>
        apiFetch(`/mcq/tests/${testId}`, 'GET', null, token),
    
    deleteTest: (orgId, testId, token) =>
        apiFetch(`/mcq/tests/${testId}`, 'DELETE', null, token),
    
    // ✅ FIXED: Submit attempt
    submitAttempt: (orgId, attemptData, token) => {
        // Start attempt first to get attempt_id
        return apiFetch(`/mcq/tests/${attemptData.test_id}/start`, 'POST', null, token)
            .then(response => {
                // Then submit answers
                return apiFetch(
                    `/mcq/attempts/${response.attempt_id}/submit`,
                    'POST',
                    { answers: attemptData.answers.map((ans, idx) => ({
                        question_index: idx,
                        selected_answer: ans
                    }))},
                    token
                );
            });
    },
    
    // ✅ FIXED: List attempts for a test
    listAttempts: (orgId, testId, token) =>
        apiFetch(`/mcq/tests/${testId}/attempts`, 'GET', null, token),
    
    getAttempt: (orgId, attemptId, token) =>
        apiFetch(`/mcq/attempts/${attemptId}`, 'GET', null, token),
};

// ========== ROLEPLAY APIs ==========
export const roleplay = {
    listPersonas: (token) =>
        apiFetch('/roleplay/personas', 'GET', null, token),
    
    getPersona: (personaId, token) =>
        apiFetch(`/roleplay/personas/${personaId}`, 'GET', null, token),
    
    startSession: (personaId, token) =>
        apiFetch('/roleplay/sessions/start', 'POST', { persona_id: personaId }, token),
    
    sendMessage: (sessionId, message, token) =>
        apiFetch(`/roleplay/sessions/${sessionId}/message`, 'POST', { message }, token),
    
    getMessages: (sessionId, token) =>
        apiFetch(`/roleplay/sessions/${sessionId}/messages`, 'GET', null, token),
    
    endSession: (sessionId, token) =>
        apiFetch(`/roleplay/sessions/${sessionId}/end`, 'POST', null, token),
    
    getSession: (sessionId, token) =>
        apiFetch(`/roleplay/sessions/${sessionId}`, 'GET', null, token),
    
    getNlpEvaluation: (sessionId, token) =>
        apiFetch(`/roleplay/sessions/${sessionId}/evaluation/nlp`, 'GET', null, token),
    
    triggerEvaluation: (sessionId, token) =>
        apiFetch(`/roleplay/sessions/${sessionId}/evaluate`, 'POST', null, token),
    
    getEvaluation: (sessionId, token) =>
        apiFetch(`/roleplay/sessions/${sessionId}/evaluation`, 'GET', null, token),
    
    listSessions: (token, limit = 20, offset = 0, status = null) => {
        let url = `/roleplay/sessions?limit=${limit}&offset=${offset}`;
        if (status) url += `&status=${status}`;
        return apiFetch(url, 'GET', null, token);
    },
    
    getUserAnalytics: (token) =>
        apiFetch('/roleplay/analytics/user', 'GET', null, token),
    
    getOrgAnalytics: (token) =>
        apiFetch('/roleplay/analytics/org', 'GET', null, token),
};