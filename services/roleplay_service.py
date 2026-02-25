"""
Roleplay service for session and conversation management
Handles session creation, message storage, and AI response generation
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from models.roleplay import (
    RoleplayPersona, 
    RoleplaySession, 
    RoleplayMessage,
    SessionStatus,
    MessageSender
)
from roleplay.llm_client import generate_customer_response
from roleplay.evaluator import evaluate_session_conversation
from models.roleplay import RoleplayEvaluation
from roleplay.nlp_evaluator import NLPEvaluator
import json

# Singleton NLP evaluator — avoids reloading heavy ML models per call
_nlp_evaluator_instance = None

def _get_nlp_evaluator():
    global _nlp_evaluator_instance
    if _nlp_evaluator_instance is None:
        _nlp_evaluator_instance = NLPEvaluator()
    return _nlp_evaluator_instance


def create_session(
    db: Session,
    trainee_id: int,
    org_id: int,
    persona_id: int
) -> RoleplaySession:
    """
    Create a new roleplay session
    
    Args:
        db: Database session
        trainee_id: User ID of trainee
        org_id: Organization ID
        persona_id: Selected persona ID
    
    Returns:
        Created RoleplaySession instance
    """
    
    # Load persona
    persona = db.query(RoleplayPersona).filter_by(id=persona_id).first()
    if not persona:
        raise ValueError(f"Persona with id {persona_id} not found")
    
    # Create persona snapshot
    persona_snapshot = {
        "name": persona.name,
        "description": persona.description,
        "personality_traits": persona.personality_traits,
        "common_objections": persona.common_objections,
        "tone": persona.tone,
        "difficulty": persona.difficulty
    }
    
    # Create session
    session = RoleplaySession(
        trainee_id=trainee_id,
        organization_id=org_id,
        persona_id=persona_id,
        persona_snapshot=persona_snapshot,
        status=SessionStatus.ACTIVE.value,
        started_at=datetime.now(timezone.utc),
        total_messages=0
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return session


def add_message(
    db: Session,
    session_id: int,
    sender: str,
    text: str
) -> RoleplayMessage:
    """
    Add a message to the conversation
    
    Args:
        db: Database session
        session_id: Session ID
        sender: 'trainee' or 'ai_customer'
        text: Message content
    
    Returns:
        Created RoleplayMessage instance
    """
    
    # Get current message count for sequence number
    current_count = db.query(RoleplayMessage).filter_by(session_id=session_id).count()
    
    # Create message
    message = RoleplayMessage(
        session_id=session_id,
        sender=sender,
        message_text=text,
        sequence_number=current_count + 1,
        timestamp=datetime.now(timezone.utc)
    )
    
    db.add(message)
    
    # Update session message count
    session = db.query(RoleplaySession).filter_by(id=session_id).first()
    if session:
        session.total_messages += 1
    
    db.commit()
    db.refresh(message)
    
    return message


def get_conversation_history(
    db: Session,
    session_id: int
) -> List[RoleplayMessage]:
    """
    Get full conversation history for a session
    
    Args:
        db: Database session
        session_id: Session ID
    
    Returns:
        List of RoleplayMessage instances ordered by sequence
    """
    
    messages = db.query(RoleplayMessage).filter_by(
        session_id=session_id
    ).order_by(RoleplayMessage.sequence_number).all()
    
    return messages


def generate_ai_response(
    db: Session,
    session_id: int,
    trainee_message: str
) -> Dict[str, Any]:
    """
    Generate AI customer response to trainee message
    
    Args:
        db: Database session
        session_id: Session ID
        trainee_message: Message from trainee
    
    Returns:
        Dict with response text and message IDs
    """
    
    # Get session
    session = db.query(RoleplaySession).filter_by(id=session_id).first()
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    if session.status != SessionStatus.ACTIVE.value:
        raise ValueError(f"Session {session_id} is not active")
    
    # Save trainee message
    trainee_msg = add_message(db, session_id, MessageSender.TRAINEE.value, trainee_message)
    
    # Get persona
    persona = db.query(RoleplayPersona).filter_by(id=session.persona_id).first()
    
    # Get conversation history (excluding the just-added trainee message for context)
    history = db.query(RoleplayMessage).filter(
        RoleplayMessage.session_id == session_id,
        RoleplayMessage.id < trainee_msg.id
    ).order_by(RoleplayMessage.sequence_number).all()
    
    # Generate AI response
    try:
        ai_response_text = generate_customer_response(
            persona=persona,
            history=history,
            trainee_message=trainee_message,
            org_id=session.organization_id
        )
    except Exception as e:
        # Rollback trainee message if AI generation fails
        db.delete(trainee_msg)
        db.commit()
        raise Exception(f"Failed to generate AI response: {str(e)}")
    
    # Save AI response
    ai_msg = add_message(db, session_id, MessageSender.AI_CUSTOMER.value, ai_response_text)
    
    return {
        "response": ai_response_text,
        "trainee_message_id": trainee_msg.id,
        "ai_message_id": ai_msg.id
    }


def end_session(
    db: Session,
    session_id: int
) -> RoleplaySession:
    """
    End a roleplay session
    
    Args:
        db: Database session
        session_id: Session ID
    
    Returns:
        Updated RoleplaySession instance
    """
    
    session = db.query(RoleplaySession).filter_by(id=session_id).first()
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    # Update status and completion time
    session.status = SessionStatus.COMPLETED.value
    session.completed_at = datetime.now(timezone.utc)
    
    # Calculate duration - ensure both datetimes are timezone-aware
    if session.started_at and session.completed_at:
        # Make started_at timezone-aware if it isn't
        started_at = session.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        
        duration = (session.completed_at - started_at).total_seconds()
        session.duration_seconds = int(duration)
    
    db.commit()
    db.refresh(session)
    
    return session


def get_session(
    db: Session,
    session_id: int
) -> Optional[RoleplaySession]:
    """
    Get session by ID
    
    Args:
        db: Database session
        session_id: Session ID
    
    Returns:
        RoleplaySession instance or None
    """
    return db.query(RoleplaySession).filter_by(id=session_id).first()


def evaluate_session_nlp(
    db: Session,
    session_id: int
) -> dict:
    """
    Fast NLP-based evaluation (Tier 1 - no LLM)
    Returns immediately with objective metrics
    
    Args:
        db: Database session
        session_id: Session ID
    
    Returns:
        NLP evaluation results
    """
    
    # Get conversation history
    messages = get_conversation_history(db, session_id)
    
    # Minimum message check
    MIN_MESSAGES = 6
    if len(messages) < MIN_MESSAGES:
        raise ValueError(
            f"Conversation is not long enough to perform analysis. "
            f"Need at least {MIN_MESSAGES} messages, found {len(messages)}."
        )
    
    # Convert to format expected by NLP evaluator
    message_dicts = [
        {"sender": msg.sender, "text": msg.message_text}
        for msg in messages
    ]
    
    # Run NLP evaluation (fast!) — uses singleton to avoid model reloads
    nlp_evaluator = _get_nlp_evaluator()
    nlp_results = nlp_evaluator.evaluate(message_dicts)
    
    return nlp_results


def evaluate_session(
    db: Session,
    session_id: int
) -> RoleplayEvaluation:
    """
    Evaluate a completed roleplay session with LLM qualitative feedback
    (NLP scores should already be available via evaluate_session_nlp)
    
    Args:
        db: Database session
        session_id: Session ID
    
    Returns:
        Created RoleplayEvaluation instance with NLP scores + LLM feedback
    """
    
    # Get session
    session = db.query(RoleplaySession).filter_by(id=session_id).first()
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    if session.status != SessionStatus.COMPLETED.value:
        raise ValueError(f"Session must be completed before evaluation")
    
    # Check if already evaluated - delete and re-evaluate
    existing_eval = db.query(RoleplayEvaluation).filter_by(session_id=session_id).first()
    if existing_eval:
        db.delete(existing_eval)
        db.commit()
    
    # Get conversation history
    messages = get_conversation_history(db, session_id)
    
    # Require at least 6 messages (3 exchanges) for meaningful evaluation
    MIN_MESSAGES = 6
    if len(messages) < MIN_MESSAGES:
        raise ValueError(
            f"Conversation is not long enough to perform analysis. "
            f"Need at least {MIN_MESSAGES} messages ({MIN_MESSAGES//2} exchanges), "
            f"but only found {len(messages)} message(s)."
        )
    
    # Get persona
    persona = db.query(RoleplayPersona).filter_by(id=session.persona_id).first()
    
    # Step 1: Get NLP scores (fast, objective)
    nlp_results = evaluate_session_nlp(db, session_id)
    
    # Step 2: Get LLM qualitative feedback (slow, subjective)
    try:
        llm_feedback = evaluate_session_conversation(messages, persona, org_id=session.organization_id)
    except Exception as e:
        raise Exception(f"LLM evaluation failed: {str(e)}")
    
    # Combine both evaluations
    # Hybrid scoring: blend NLP scores (60%) with LLM scores (40%) when available
    llm_category_scores = llm_feedback.get('llm_category_scores', {})
    final_category_scores = nlp_results['category_scores'].copy()
    
    if llm_category_scores:
        for cat_key in final_category_scores:
            if cat_key in llm_category_scores:
                nlp_val = final_category_scores[cat_key]
                llm_val = llm_category_scores[cat_key]
                # Weighted blend: 60% NLP (objective) + 40% LLM (contextual)
                final_category_scores[cat_key] = round(nlp_val * 0.6 + llm_val * 0.4)
    
    final_overall_score = sum(final_category_scores.values())
    
    evaluation = RoleplayEvaluation(
        session_id=session_id,
        overall_score=final_overall_score,
        category_scores=final_category_scores,
        summary=llm_feedback.get('summary'),
        strengths=llm_feedback['strengths'],
        improvement_areas=llm_feedback['improvements'],
        nlp_metrics=nlp_results['detailed_metrics'],
        detailed_feedback={
            'nlp': nlp_results,
            'llm': llm_feedback,
            'hybrid_scores': final_category_scores,
            'coaching_tip': llm_feedback.get('coaching_tip', ''),
            'category_feedback': llm_feedback.get('category_feedback', {})
        }
    )
    
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    
    return evaluation
