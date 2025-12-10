"""
Roleplay API Routes - AI Customer Persona Training
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone

from utils.database import get_db
from utils.security import get_current_user
from models.user import User
from models.roleplay import RoleplayPersona, RoleplaySession, RoleplayMessage, SessionStatus
from services import roleplay_service

router = APIRouter(prefix="/roleplay", tags=["Roleplay"])


# ===== Pydantic Models =====

class SessionStartRequest(BaseModel):
    persona_id: int


class MessageRequest(BaseModel):
    message: str


# ===== Persona Endpoints =====

@router.get("/personas")
def list_personas(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all available customer personas for the organization"""
    
    try:
        # Get all predefined personas + custom personas for this org
        personas = db.query(RoleplayPersona).filter(
            (RoleplayPersona.is_predefined == True) |
            (RoleplayPersona.organization_id == current_user.organization_id)
        ).order_by(RoleplayPersona.is_predefined.desc(), RoleplayPersona.name).all()
        
        print(f"📋 Found {len(personas)} personas for user {current_user.email}")
        
        return {
            "personas": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "tone": p.tone,
                    "difficulty": p.difficulty,
                    "is_predefined": p.is_predefined
                }
                for p in personas
            ]
        }
    except Exception as e:
        print(f"Error listing personas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve personas: {str(e)}"
        )


@router.get("/personas/{persona_id}")
def get_persona(
    persona_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific persona"""
    
    try:
        persona = db.query(RoleplayPersona).filter(
            RoleplayPersona.id == persona_id
        ).filter(
            (RoleplayPersona.is_predefined == True) |
            (RoleplayPersona.organization_id == current_user.organization_id)
        ).first()
        
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found"
            )
        
        return {
            "id": persona.id,
            "name": persona.name,
            "description": persona.description,
            "personality_traits": persona.personality_traits,
            "common_objections": persona.common_objections,
            "tone": persona.tone,
            "difficulty": persona.difficulty,
            "is_predefined": persona.is_predefined
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve persona: {str(e)}"
        )


# ===== Session Endpoints =====

@router.post("/sessions/start")
def start_roleplay_session(
    request: SessionStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a new roleplay conversation session"""
    
    try:
        session = roleplay_service.create_session(
            db=db,
            trainee_id=current_user.id,
            org_id=current_user.organization_id,
            persona_id=request.persona_id
        )
        
        print(f"▶️  Started roleplay session {session.id} for user {current_user.email}")
        
        return {
            "session_id": session.id,
            "persona_id": session.persona_id,
            "persona_name": session.persona_snapshot["name"],
            "status": session.status,
            "started_at": session.started_at.isoformat()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error starting session: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}"
        )


@router.post("/sessions/{session_id}/message")
def send_message(
    session_id: int,
    request: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message and get AI customer response"""
    
    try:
        # Verify session belongs to user
        session = roleplay_service.get_session(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.trainee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        # Generate AI response
        result = roleplay_service.generate_ai_response(
            db=db,
            session_id=session_id,
            trainee_message=request.message
        )
        
        print(f"💬 Message sent in session {session_id}")
        
        return {
            "success": True,
            "trainee_message_id": result["trainee_message_id"],
            "ai_message_id": result["ai_message_id"],
            "ai_response": result["response"]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error sending message: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


@router.get("/sessions/{session_id}/messages")
def get_conversation_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full conversation history for a session"""
    
    try:
        # Verify session belongs to user
        session = roleplay_service.get_session(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.trainee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        messages = roleplay_service.get_conversation_history(db, session_id)
        
        return {
            "session_id": session_id,
            "persona_name": session.persona_snapshot["name"],
            "messages": [
                {
                    "id": msg.id,
                    "sender": msg.sender,
                    "text": msg.message_text,
                    "timestamp": msg.timestamp.isoformat(),
                    "sequence": msg.sequence_number
                }
                for msg in messages
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve messages: {str(e)}"
        )


@router.post("/sessions/{session_id}/end")
def end_roleplay_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """End a roleplay session and automatically generate NLP evaluation"""
    
    try:
        # Verify session belongs to user
        session = roleplay_service.get_session(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.trainee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        # End the session
        session = roleplay_service.end_session(db, session_id)
        
        # Automatically generate NLP evaluation (fast!)
        nlp_evaluation = None
        try:
            nlp_evaluation = roleplay_service.evaluate_session_nlp(db, session_id)
            print(f"✅ Auto-generated NLP evaluation for session {session_id}")
        except ValueError as e:
            # Not enough messages for evaluation
            print(f"⚠️ Could not evaluate session {session_id}: {e}")
        except Exception as e:
            # Non-critical error - session still ended successfully
            print(f"⚠️ NLP evaluation failed for session {session_id}: {e}")
        
        print(f"⏹️  Ended session {session_id}")
        
        return {
            "success": True,
            "session_id": session.id,
            "status": session.status,
            "total_messages": session.total_messages,
            "duration_seconds": session.duration_seconds,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "nlp_evaluation": nlp_evaluation  # Include NLP results if available
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error ending session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to end session: {str(e)}"
        )


@router.get("/sessions/{session_id}")
def get_session_details(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get session metadata and details"""
    
    try:
        session = roleplay_service.get_session(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.trainee_id != current_user.id and current_user.role not in ["admin", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        return {
            "id": session.id,
            "trainee_id": session.trainee_id,
            "persona_id": session.persona_id,
            "persona_name": session.persona_snapshot["name"],
            "persona_snapshot": session.persona_snapshot,
            "status": session.status,
            "started_at": session.started_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "duration_seconds": session.duration_seconds,
            "total_messages": session.total_messages
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session: {str(e)}"
        )


@router.get("/sessions/{session_id}/evaluation/nlp")
def get_nlp_evaluation(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get fast NLP metrics (no LLM) - returns immediately"""
    
    try:
        # Verify session belongs to user
        session = roleplay_service.get_session(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.trainee_id != current_user.id and current_user.role not in ["admin", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        # Get NLP evaluation (fast!)
        nlp_results = roleplay_service.evaluate_session_nlp(db, session_id)
        
        print(f"📊 Generated NLP metrics for session {session_id}")
        
        return {
            "session_id": session_id,
            **nlp_results
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error getting NLP evaluation: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate NLP metrics: {str(e)}"
        )


@router.post("/sessions/{session_id}/evaluate")
def evaluate_roleplay_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Evaluate a completed roleplay session"""
    
    try:
        # Verify session belongs to user
        session = roleplay_service.get_session(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.trainee_id != current_user.id and current_user.role not in ["admin", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        # Run evaluation
        evaluation = roleplay_service.evaluate_session(db, session_id)
        
        print(f"✅ Evaluated session {session_id}")
        
        return {
            "success": True,
            "evaluation_id": evaluation.id,
            "overall_score": evaluation.overall_score,
            "evaluated_at": evaluation.evaluated_at.isoformat()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error evaluating session: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate session: {str(e)}"
        )


@router.get("/sessions/{session_id}/evaluation")
def get_session_evaluation(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get evaluation results for a session"""
    
    try:
        # Verify session belongs to user
        session = roleplay_service.get_session(db, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.trainee_id != current_user.id and current_user.role not in ["admin", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        # Get evaluation
        from models.roleplay import RoleplayEvaluation
        evaluation = db.query(RoleplayEvaluation).filter_by(session_id=session_id).first()
        
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evaluation not found. Please evaluate the session first."
            )
        
        return {
            "id": evaluation.id,
            "session_id": evaluation.session_id,
            "overall_score": evaluation.overall_score,
            "category_scores": evaluation.category_scores,
            "strengths": evaluation.strengths,
            "improvements": evaluation.improvements,
            "evaluated_at": evaluation.evaluated_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting evaluation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve evaluation: {str(e)}"
        )
