from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from utils.database import get_db
from utils.security import get_current_user
from models.user import User
from services.knowledge_chatbot import KnowledgeChatbot

router = APIRouter(prefix="/chatbot", tags=["Knowledge Chatbot"])

# Store active chatbot sessions (in production, use Redis/database)
chatbot_sessions = {}


class ChatRequest(BaseModel):
    question: str
    use_history: bool = True
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    conversation_id: Optional[int]
    timestamp: str


@router.post("/chat", response_model=ChatResponse)
def chat_with_knowledge_base(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat with the training knowledge base
    """
    
    print(f"\n💬 Chat request from user: {current_user.email}")
    print(f"   Question: {request.question}")
    
    try:
        # Get or create chatbot session for user
        session_key = f"{current_user.id}_{current_user.organization_id}"
        
        if session_key not in chatbot_sessions:
            print(f"🆕 Creating new chatbot session for user {current_user.id}")
            chatbot_sessions[session_key] = KnowledgeChatbot(
                org_id=current_user.organization_id
            )
        
        chatbot = chatbot_sessions[session_key]
        
        # Generate response
        response = chatbot.chat(
            question=request.question,
            top_k=request.top_k,
            use_history=request.use_history
        )
        
        return response
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat: {str(e)}"
        )


@router.get("/history")
def get_conversation_history(
    current_user: User = Depends(get_current_user)
):
    """Get conversation history for current user"""
    
    session_key = f"{current_user.id}_{current_user.organization_id}"
    
    if session_key not in chatbot_sessions:
        return {
            "history": [],
            "message": "No conversation history found"
        }
    
    chatbot = chatbot_sessions[session_key]
    history = chatbot.get_history()
    
    return {
        "history": history,
        "total_messages": len(history)
    }


@router.post("/clear-history")
def clear_conversation_history(
    current_user: User = Depends(get_current_user)
):
    """Clear conversation history"""
    
    session_key = f"{current_user.id}_{current_user.organization_id}"
    
    if session_key in chatbot_sessions:
        chatbot_sessions[session_key].clear_history()
        return {"message": "Conversation history cleared"}
    
    return {"message": "No active session found"}


@router.get("/export")
def export_conversation(
    current_user: User = Depends(get_current_user)
):
    """Export conversation for download"""
    
    session_key = f"{current_user.id}_{current_user.organization_id}"
    
    if session_key not in chatbot_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No conversation to export"
        )
    
    chatbot = chatbot_sessions[session_key]
    export_data = chatbot.export_conversation()
    
    return export_data