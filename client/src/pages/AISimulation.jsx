import React, { useState } from 'react';
import RoleplayPersonas from './RoleplayPersonas';
import RoleplayChat from './RoleplayChat';
import RoleplayFeedback from './RoleplayFeedback';

/**
 * AISimulationView — wrapper that composes the full roleplay flow using
 * the correct /roleplay/* API endpoints.
 *
 * Previously used /orgs/{orgId}/simulation/* (404s). Now delegates to the
 * dedicated RoleplayPersonas → RoleplayChat → RoleplayFeedback pages.
 */
const AISimulationView = ({ orgId, token }) => {
    const [view, setView] = useState('personas'); // 'personas' | 'chat' | 'feedback'
    const [sessionData, setSessionData] = useState(null); // { sessionId }
    const [nlpData, setNlpData] = useState(null);

    if (view === 'personas') {
        return (
            <RoleplayPersonas
                token={token}
                navigate={(newView, data) => {
                    // RoleplayPersonas calls navigate('roleplay-chat', { sessionId })
                    setSessionData(data);
                    setView('chat');
                }}
            />
        );
    }

    if (view === 'chat') {
        return (
            <RoleplayChat
                sessionId={sessionData?.sessionId}
                token={token}
                onEnd={(receivedNlpData) => {
                    setNlpData(receivedNlpData || null);
                    setView('feedback');
                }}
            />
        );
    }

    if (view === 'feedback') {
        return (
            <RoleplayFeedback
                sessionId={sessionData?.sessionId}
                token={token}
                initialNlpData={nlpData}
                onBack={() => {
                    setView('personas');
                    setSessionData(null);
                    setNlpData(null);
                }}
            />
        );
    }

    return null;
};

export default AISimulationView;