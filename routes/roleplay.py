"""
Roleplay API Routes - AI Customer Persona Training
Enhanced with: session history, analytics, user progress tracking
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from utils.database import get_db
from utils.security import get_current_user
from models.user import User
from models.roleplay import RoleplayPersona, RoleplaySession, RoleplayMessage, RoleplayEvaluation, SessionStatus
from services import roleplay_service

router = APIRouter(prefix="/roleplay", tags=["Roleplay"])


# ===== Pydantic Models =====

class SessionStartRequest(BaseModel):
    persona_id: int


class MessageRequest(BaseModel):
    message: str

    @classmethod
    def __get_validators__(cls):
        yield from super().__get_validators__()

    def __init__(self, **data):
        if "message" in data:
            data["message"] = data["message"].strip()
            if len(data["message"]) < 1:
                raise ValueError("Message cannot be empty")
            if len(data["message"]) > 3000:
                raise ValueError("Message too long (max 3000 characters)")
        super().__init__(**data)


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
            "ai_response": result["response"],
            "stage_info": result.get("stage_info"),
            "coaching_hint": result.get("coaching_hint"),
            "eq_data": result.get("eq_data"),
            "accuracy_data": result.get("accuracy_data"),
            "lstm_risk": result.get("lstm_risk"),
            "conversion_data": result.get("conversion_data"),
            "trained_models": result.get("trained_models"),
            "deal_intelligence": result.get("deal_intelligence"),
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


@router.post("/sessions/{session_id}/voice-message")
async def send_voice_message(
    session_id: int,
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a voice message: transcribe with Whisper, extract voice metrics,
    then process through the same roleplay pipeline as text messages.
    """
    import tempfile, os

    try:
        session = roleplay_service.get_session(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.trainee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Save uploaded audio to temp file
        suffix = os.path.splitext(audio.filename or ".webm")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Transcribe + analyze voice
            from services.voice_analytics import transcribe_audio
            voice_result = transcribe_audio(tmp_path)
        finally:
            os.unlink(tmp_path)

        transcribed_text = voice_result["text"]
        if not transcribed_text or len(transcribed_text.strip()) < 2:
            return {
                "success": False,
                "error": "Could not transcribe audio. Please speak clearly and try again.",
                "voice_metrics": voice_result.get("metrics"),
            }

        # Process through standard roleplay pipeline
        result = roleplay_service.generate_ai_response(
            db=db,
            session_id=session_id,
            trainee_message=transcribed_text
        )

        return {
            "success": True,
            "trainee_message_id": result["trainee_message_id"],
            "ai_message_id": result["ai_message_id"],
            "ai_response": result["response"],
            "transcribed_text": transcribed_text,
            "voice_metrics": voice_result["metrics"],
            "voice_coaching": voice_result["coaching"],
            "stage_info": result.get("stage_info"),
            "coaching_hint": result.get("coaching_hint"),
            "eq_data": result.get("eq_data"),
            "accuracy_data": result.get("accuracy_data"),
            "lstm_risk": result.get("lstm_risk"),
            "conversion_data": result.get("conversion_data"),
            "trained_models": result.get("trained_models"),
            "deal_intelligence": result.get("deal_intelligence"),
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in voice message: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None   # "female", "male", preset key, or full voice name
    rate: Optional[str] = "+0%"   # speed adjustment: "-10%", "+5%", etc.


@router.post("/tts")
def text_to_speech(
    req: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate natural-sounding speech from text using Edge TTS (Microsoft Neural).
    Returns MP3 audio bytes.
    """
    from services.tts_service import synthesize_speech

    if not req.text or len(req.text.strip()) < 1:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        audio_bytes = synthesize_speech(
            text=req.text,
            voice_hint=req.voice,
            rate=req.rate or "+0%",
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=tts.mp3"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


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
            "evaluated_at": evaluation.created_at.isoformat()
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
            "summary": evaluation.summary,
            "strengths": evaluation.strengths,
            "improvement_areas": evaluation.improvement_areas,
            "coaching_tip": evaluation.detailed_feedback.get('coaching_tip', '') if evaluation.detailed_feedback else '',
            "category_feedback": evaluation.detailed_feedback.get('category_feedback', {}) if evaluation.detailed_feedback else {},
            "stage_performance": evaluation.detailed_feedback.get('stage_performance', {}) if evaluation.detailed_feedback else {},
            "missed_opportunities": evaluation.detailed_feedback.get('missed_opportunities', []) if evaluation.detailed_feedback else [],
            "eq_summary": evaluation.detailed_feedback.get('eq_summary', {}) if evaluation.detailed_feedback else {},
            "replay": evaluation.detailed_feedback.get('replay', {}) if evaluation.detailed_feedback else {},
            "evaluated_at": evaluation.created_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting evaluation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve evaluation: {str(e)}"
        )


# ===== Session History & Analytics Endpoints (NEW) =====

@router.get("/sessions")
def list_user_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all roleplay sessions for the current user with pagination"""
    
    try:
        query = db.query(RoleplaySession).filter(
            RoleplaySession.trainee_id == current_user.id
        )
        
        if status_filter:
            query = query.filter(RoleplaySession.status == status_filter)
        
        total = query.count()
        
        sessions = query.order_by(
            desc(RoleplaySession.started_at)
        ).offset(offset).limit(limit).all()
        
        session_list = []
        for s in sessions:
            # Get evaluation score if available
            eval_data = db.query(RoleplayEvaluation).filter_by(session_id=s.id).first()
            
            session_list.append({
                "id": s.id,
                "persona_name": s.persona_snapshot.get("name", "Unknown"),
                "persona_difficulty": s.persona_snapshot.get("difficulty", "unknown"),
                "status": s.status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "duration_seconds": s.duration_seconds,
                "total_messages": s.total_messages,
                "overall_score": eval_data.overall_score if eval_data else None,
                "has_evaluation": eval_data is not None
            })
        
        return {
            "sessions": session_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        print(f"Error listing sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.get("/analytics/user")
def get_user_roleplay_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive roleplay analytics for the current user"""
    
    try:
        # Get all completed sessions with evaluations
        sessions = db.query(RoleplaySession).filter(
            RoleplaySession.trainee_id == current_user.id,
            RoleplaySession.status == SessionStatus.COMPLETED.value
        ).order_by(RoleplaySession.started_at).all()
        
        if not sessions:
            return {
                "total_sessions": 0,
                "total_practice_time": 0,
                "average_score": 0,
                "score_trend": [],
                "category_averages": {},
                "persona_performance": [],
                "improvement_velocity": "N/A",
                "strongest_category": None,
                "weakest_category": None
            }
        
        # Aggregate metrics
        total_sessions = len(sessions)
        total_time = sum(s.duration_seconds or 0 for s in sessions)
        
        # Get evaluations
        session_ids = [s.id for s in sessions]
        evaluations = db.query(RoleplayEvaluation).filter(
            RoleplayEvaluation.session_id.in_(session_ids)
        ).all()
        
        eval_map = {e.session_id: e for e in evaluations}
        
        # Score trend over time
        score_trend = []
        category_totals = {
            "rapport_building": [], "needs_discovery": [],
            "product_presentation": [], "objection_handling": [], "closing": []
        }
        
        for s in sessions:
            ev = eval_map.get(s.id)
            if ev:
                score_trend.append({
                    "session_id": s.id,
                    "date": s.started_at.isoformat() if s.started_at else None,
                    "score": ev.overall_score,
                    "persona": s.persona_snapshot.get("name", "Unknown"),
                    "difficulty": s.persona_snapshot.get("difficulty", "unknown")
                })
                
                if ev.category_scores:
                    for cat, val in ev.category_scores.items():
                        if cat in category_totals:
                            category_totals[cat].append(val)
        
        # Category averages
        category_averages = {}
        for cat, scores in category_totals.items():
            category_averages[cat] = round(sum(scores) / len(scores), 1) if scores else 0
        
        # Best and worst categories
        strongest = max(category_averages, key=category_averages.get) if category_averages else None
        weakest = min(category_averages, key=category_averages.get) if category_averages else None
        
        # Per-persona performance
        persona_perf = {}
        for s in sessions:
            ev = eval_map.get(s.id)
            if ev:
                persona_name = s.persona_snapshot.get("name", "Unknown")
                if persona_name not in persona_perf:
                    persona_perf[persona_name] = {"scores": [], "difficulty": s.persona_snapshot.get("difficulty", "unknown")}
                persona_perf[persona_name]["scores"].append(ev.overall_score)
        
        persona_performance = [
            {
                "persona": name,
                "difficulty": data["difficulty"],
                "attempts": len(data["scores"]),
                "avg_score": round(sum(data["scores"]) / len(data["scores"]), 1),
                "best_score": max(data["scores"]),
                "latest_score": data["scores"][-1]
            }
            for name, data in persona_perf.items()
        ]
        
        # Improvement velocity (compare first 3 vs last 3 evaluated sessions)
        evaluated_scores = [ev.overall_score for ev in evaluations]
        if len(evaluated_scores) >= 4:
            early_avg = sum(evaluated_scores[:3]) / 3
            late_avg = sum(evaluated_scores[-3:]) / 3
            velocity = round(late_avg - early_avg, 1)
            velocity_label = "improving" if velocity > 5 else "declining" if velocity < -5 else "stable"
        else:
            velocity = 0
            velocity_label = "insufficient data"
        
        avg_score = round(sum(evaluated_scores) / len(evaluated_scores), 1) if evaluated_scores else 0
        
        return {
            "total_sessions": total_sessions,
            "evaluated_sessions": len(evaluations),
            "total_practice_time": total_time,
            "average_score": avg_score,
            "score_trend": score_trend,
            "category_averages": category_averages,
            "persona_performance": persona_performance,
            "improvement_velocity": velocity,
            "improvement_direction": velocity_label,
            "strongest_category": strongest,
            "weakest_category": weakest
        }
    except Exception as e:
        print(f"Error getting analytics: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}"
        )


@router.get("/analytics/org")
def get_org_roleplay_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization-wide roleplay analytics (admin/manager only)"""
    
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can view org analytics"
        )
    
    try:
        org_id = current_user.organization_id
        
        # Total org stats
        total_sessions = db.query(func.count(RoleplaySession.id)).filter(
            RoleplaySession.organization_id == org_id,
            RoleplaySession.status == SessionStatus.COMPLETED.value
        ).scalar()
        
        # Average score across all evaluations
        avg_score_result = db.query(
            func.avg(RoleplayEvaluation.overall_score)
        ).join(
            RoleplaySession, RoleplaySession.id == RoleplayEvaluation.session_id
        ).filter(
            RoleplaySession.organization_id == org_id
        ).scalar()
        
        avg_score = round(float(avg_score_result), 1) if avg_score_result else 0
        
        # Active trainees (users who have completed at least 1 session)
        active_trainees = db.query(
            func.count(func.distinct(RoleplaySession.trainee_id))
        ).filter(
            RoleplaySession.organization_id == org_id,
            RoleplaySession.status == SessionStatus.COMPLETED.value
        ).scalar()
        
        # Top performers
        top_performers = db.query(
            User.id,
            User.email,
            func.avg(RoleplayEvaluation.overall_score).label("avg_score"),
            func.count(RoleplayEvaluation.id).label("sessions_evaluated")
        ).join(
            RoleplaySession, RoleplaySession.trainee_id == User.id
        ).join(
            RoleplayEvaluation, RoleplayEvaluation.session_id == RoleplaySession.id
        ).filter(
            RoleplaySession.organization_id == org_id
        ).group_by(
            User.id, User.email
        ).order_by(
            desc(func.avg(RoleplayEvaluation.overall_score))
        ).limit(5).all()
        
        return {
            "total_sessions": total_sessions,
            "average_score": avg_score,
            "active_trainees": active_trainees,
            "top_performers": [
                {
                    "user_id": u.id,
                    "email": u.email,
                    "avg_score": round(float(u.avg_score), 1),
                    "sessions": u.sessions_evaluated
                }
                for u in top_performers
            ]
        }
    except Exception as e:
        print(f"Error getting org analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get org analytics: {str(e)}"
        )
