from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models.mcq import MCQAttempt

def calculate_user_performance(user_id: int, org_id: int, db: Session) -> Dict[str, Any]:
    """Calculate overall user performance metrics"""
    
    attempts = db.query(MCQAttempt).filter(
        MCQAttempt.user_id == user_id,
        MCQAttempt.organization_id == org_id
    ).all()
    
    if not attempts:
        return {
            "total_attempts": 0,
            "average_score": 0.0,
            "total_questions_answered": 0,
            "total_correct": 0,
            "accuracy": 0.0
        }
    
    total_attempts = len(attempts)
    total_score = sum(a.score for a in attempts)
    total_questions = sum(a.total_questions for a in attempts)
    total_correct = sum(a.correct_answers for a in attempts)
    
    return {
        "total_attempts": total_attempts,
        "average_score": total_score / total_attempts,
        "total_questions_answered": total_questions,
        "total_correct": total_correct,
        "accuracy": (total_correct / total_questions * 100) if total_questions > 0 else 0.0
    }


def get_learning_insights(user_id: int, org_id: int, db: Session) -> Dict[str, Any]:
    """Generate learning insights for user"""
    
    attempts = db.query(MCQAttempt).filter(
        MCQAttempt.user_id == user_id,
        MCQAttempt.organization_id == org_id
    ).order_by(MCQAttempt.completed_at.desc()).all()
    
    if not attempts:
        return {"message": "No data available"}
    
    # Calculate trend (last 5 attempts)
    recent_attempts = attempts[:5]
    scores = [a.score for a in recent_attempts]
    
    trend = "improving" if len(scores) > 1 and scores[0] > scores[-1] else "stable"
    
    # Identify weak areas (topics with <70% accuracy)
    topic_performance = {}
    for attempt in attempts:
        # Aggregate by topic (would need test metadata)
        pass
    
    return {
        "recent_scores": scores,
        "trend": trend,
        "total_time_spent": sum(a.time_taken_seconds or 0 for a in attempts),
        "improvement_areas": []  # Placeholder
    }