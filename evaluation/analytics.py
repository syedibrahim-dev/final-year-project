from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.mcq import MCQAttempt, MCQTest
from models.user import User

def generate_performance_report(org_id: int, db: Session) -> Dict[str, Any]:
    """Generate organization-wide performance report"""
    
    # Total attempts
    total_attempts = db.query(func.count(MCQAttempt.id)).filter(
        MCQAttempt.organization_id == org_id
    ).scalar()
    
    # Average score
    avg_score = db.query(func.avg(MCQAttempt.score)).filter(
        MCQAttempt.organization_id == org_id
    ).scalar() or 0.0
    
    # Total users
    total_users = db.query(func.count(User.id)).filter(
        User.organization_id == org_id,
        User.is_active == True
    ).scalar()
    
    # Total tests
    total_tests = db.query(func.count(MCQTest.id)).filter(
        MCQTest.organization_id == org_id,
        MCQTest.is_active == True
    ).scalar()
    
    # Top performers
    top_performers = db.query(
        User.id,
        User.email,
        func.avg(MCQAttempt.score).label("avg_score")
    ).join(
        MCQAttempt, User.id == MCQAttempt.user_id
    ).filter(
        User.organization_id == org_id
    ).group_by(
        User.id, User.email
    ).order_by(
        func.avg(MCQAttempt.score).desc()
    ).limit(5).all()
    
    return {
        "total_attempts": total_attempts,
        "average_score": float(avg_score),
        "total_active_users": total_users,
        "total_tests": total_tests,
        "top_performers": [
            {"user_id": u.id, "email": u.email, "avg_score": float(u.avg_score)}
            for u in top_performers
        ]
    }