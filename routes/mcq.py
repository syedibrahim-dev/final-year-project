from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
import json

from utils.database import get_db
from utils.security import get_current_user
from models.user import User
from models.mcq import MCQTest, MCQAttempt
from mcq.pipeline import MCQPipeline

router = APIRouter(prefix="/mcq", tags=["MCQ"])


# ===== Pydantic Models for Request Bodies =====

class MCQTestCreate(BaseModel):
    title: str
    topic: str
    difficulty: str
    description: str = ""
    questions: List[Dict[str, Any]]


class AnswerSubmission(BaseModel):
    answers: List[Dict[str, Any]]


# ...existing generate_mcqs endpoint...

@router.post("/generate")
def generate_mcqs(
    topic: str,
    difficulty: str = "medium",
    num_questions: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate MCQs using AI pipeline - Does NOT save to database yet"""
    
    print(f"📝 MCQ Generation Request:")
    print(f"   User: {current_user.email}")
    print(f"   Topic: {topic}")
    print(f"   Difficulty: {difficulty}")
    print(f"   Questions: {num_questions}")
    
    # Validate inputs
    if num_questions < 1 or num_questions > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Number of questions must be between 1 and 10"
        )
    
    if difficulty not in ["easy", "medium", "hard"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Difficulty must be easy, medium, or hard"
        )
    
    try:
        pipeline = MCQPipeline()
        
        questions = pipeline.generate_mcqs(
            topic=topic,
            difficulty=difficulty,
            num_questions=num_questions,
            org_id=current_user.organization_id,
            include_explanations=True
        )
        
        if not questions:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate questions. Please try again."
            )
        
        print(f"✅ Generated {len(questions)} questions successfully")
        
        return {
            "success": True,
            "questions": questions,
            "count": len(questions),
            "topic": topic,
            "difficulty": difficulty
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        print(f"❌ MCQ generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCQ generation failed: {str(e)}"
        )


@router.post("/tests")
def create_mcq_test(
    test_data: MCQTestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create and save an MCQ test with generated questions"""
    
    print(f"💾 Creating MCQ Test:")
    print(f"   Title: {test_data.title}")
    print(f"   Topic: {test_data.topic}")
    print(f"   Questions: {len(test_data.questions) if test_data.questions else 0}")
    
    if not test_data.questions or len(test_data.questions) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Questions are required to create a test"
        )
    
    try:
        test = MCQTest(
            title=test_data.title,
            description=test_data.description,
            topic=test_data.topic,
            difficulty=test_data.difficulty,
            questions_json=test_data.questions,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        
        db.add(test)
        db.commit()
        db.refresh(test)
        
        print(f"✅ Test created with ID: {test.id}")
        
        return {
            "success": True,
            "test_id": test.id,
            "title": test.title,
            "topic": test.topic,
            "difficulty": test.difficulty,
            "questions_count": len(test_data.questions),
            "questions_json": test_data.questions,  # ✅ ADDED: Return questions for frontend
            "created_at": test.created_at.isoformat()
        }
    
    except Exception as e:
        db.rollback()
        print(f"❌ Test creation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create test: {str(e)}"
        )


@router.get("/tests")
def list_mcq_tests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all MCQ tests for user's organization"""
    
    try:
        tests = db.query(MCQTest).filter(
            MCQTest.organization_id == current_user.organization_id
        ).order_by(MCQTest.created_at.desc()).all()
        
        print(f"📋 Found {len(tests)} tests for org {current_user.organization_id}")
        
        return {
            "tests": [
                {
                    "id": test.id,
                    "title": test.title,
                    "topic": test.topic,
                    "difficulty": test.difficulty,
                    "questions_count": len(test.questions_json) if test.questions_json else 0,
                    "created_at": test.created_at.isoformat(),
                    "created_by": test.created_by
                }
                for test in tests
            ]
        }
    except Exception as e:
        print(f"❌ Error listing tests: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve tests: {str(e)}"
        )


@router.get("/tests/{test_id}")
def get_mcq_test(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific MCQ test with all questions"""
    
    try:
        test = db.query(MCQTest).filter(
            MCQTest.id == test_id,
            MCQTest.organization_id == current_user.organization_id
        ).first()
        
        if not test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test not found"
            )
        
        print(f"📖 Retrieved test {test_id}: {test.title}")
        
        return {
            "id": test.id,
            "title": test.title,
            "description": test.description,
            "topic": test.topic,
            "difficulty": test.difficulty,
            "created_at": test.created_at.isoformat(),
            "questions": test.questions_json if test.questions_json else []
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting test {test_id}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve test: {str(e)}"
        )


@router.delete("/tests/{test_id}")
def delete_mcq_test(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an MCQ test (only creator or admin)"""
    
    test = db.query(MCQTest).filter(
        MCQTest.id == test_id,
        MCQTest.organization_id == current_user.organization_id
    ).first()
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    # Check permissions
    if test.created_by != current_user.id and current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this test"
        )
    
    try:
        # Delete all related attempts first
        attempt_count = db.query(MCQAttempt).filter(MCQAttempt.test_id == test_id).delete()
        db.delete(test)
        db.commit()
        print(f"🗑️ Deleted test {test_id}: {test.title} (and {attempt_count} attempts)")
        return {"success": True, "message": f"Test and {attempt_count} related attempts deleted successfully"}
    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting test {test_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete test: {str(e)}"
        )


# ===== Test Attempt Endpoints =====

@router.post("/tests/{test_id}/start")
def start_test_attempt(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a new test attempt"""
    
    test = db.query(MCQTest).filter(
        MCQTest.id == test_id,
        MCQTest.organization_id == current_user.organization_id
    ).first()
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    try:
        attempt = MCQAttempt(
            test_id=test_id,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            total_questions=len(test.questions_json) if test.questions_json else 0,
            correct_answers=0,
            score=0.0,
            answers_json={},
            started_at=datetime.now(timezone.utc),
            completed_at=None  # ✅ FIXED: Set to None initially
        )
        
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        
        print(f"▶️  Started attempt {attempt.id} for test {test_id}")
        
        return {
            "attempt_id": attempt.id,
            "test_id": test_id,
            "total_questions": attempt.total_questions,
            "started_at": attempt.started_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Error starting attempt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start test attempt: {str(e)}"
        )


@router.post("/attempts/{attempt_id}/submit")
def submit_test_attempt(
    attempt_id: int,
    submission: AnswerSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit answers for a test attempt"""
    
    attempt = db.query(MCQAttempt).filter(
        MCQAttempt.id == attempt_id,
        MCQAttempt.user_id == current_user.id
    ).first()
    
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found"
        )
    
    # Get test with questions
    test = db.query(MCQTest).filter(MCQTest.id == attempt.test_id).first()
    
    if not test or not test.questions_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test questions not found"
        )
    
    try:
        # Process answers
        correct_count = 0
        processed_answers = {}
        
        for answer in submission.answers:
            question_idx = answer.get("question_index", 0)
            selected = answer.get("selected_answer", "")
            
            if question_idx < len(test.questions_json):
                question = test.questions_json[question_idx]
                correct_answer = question.get("correct_answer", "")
                
                is_correct = selected == correct_answer
                if is_correct:
                    correct_count += 1
                
                processed_answers[str(question_idx)] = {
                    "selected": selected,
                    "correct": correct_answer,
                    "is_correct": is_correct
                }
        
        # Update attempt
        # Lines 390-400
        attempt.correct_answers = correct_count
        attempt.score = (correct_count / attempt.total_questions * 100) if attempt.total_questions > 0 else 0
        attempt.answers_json = processed_answers
        attempt.completed_at = datetime.now(timezone.utc)

        if attempt.started_at:
            # Make started_at timezone-aware if it isn't already
            if attempt.started_at.tzinfo is None:
                started_at = attempt.started_at.replace(tzinfo=timezone.utc)
            else:
                started_at = attempt.started_at
            
            time_taken = (attempt.completed_at - started_at).total_seconds()
            attempt.time_taken_seconds = int(time_taken)
        
        db.commit()
        
        print(f"✅ Submitted attempt {attempt_id}: {correct_count}/{attempt.total_questions} correct")
        
        return {
            "success": True,
            "score": attempt.score,
            "correct_answers": correct_count,
            "total_questions": attempt.total_questions,
            "percentage": attempt.score,
            "time_taken_seconds": attempt.time_taken_seconds
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Error submitting attempt: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit answers: {str(e)}"
        )


@router.get("/attempts/{attempt_id}")
def get_attempt_results(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get results of a completed attempt"""
    
    attempt = db.query(MCQAttempt).filter(
        MCQAttempt.id == attempt_id,
        MCQAttempt.user_id == current_user.id
    ).first()
    
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found"
        )
    
    return {
        "id": attempt.id,
        "test_id": attempt.test_id,
        "score": attempt.score,
        "correct_answers": attempt.correct_answers,
        "total_questions": attempt.total_questions,
        "percentage": attempt.score,
        "time_taken_seconds": attempt.time_taken_seconds,
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        "answers": attempt.answers_json
    }


# ✅ NEW: List all attempts for a test (for Performance Dashboard)
@router.get("/tests/{test_id}/attempts")
def list_test_attempts(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all attempts for a specific test"""
    
    # Verify test exists and belongs to user's org
    test = db.query(MCQTest).filter(
        MCQTest.id == test_id,
        MCQTest.organization_id == current_user.organization_id
    ).first()
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )
    
    try:
        attempts = db.query(MCQAttempt).filter(
            MCQAttempt.test_id == test_id,
            MCQAttempt.completed_at.isnot(None)  # Only completed attempts
        ).order_by(MCQAttempt.completed_at.desc()).all()
        
        print(f"📊 Found {len(attempts)} attempts for test {test_id}")
        
        return [
            {
                "id": attempt.id,
                "user_id": attempt.user_id,
                "score": attempt.score,
                "correct_answers": attempt.correct_answers,
                "total_questions": attempt.total_questions,
                "time_taken_seconds": attempt.time_taken_seconds,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None
            }
            for attempt in attempts
        ]
    except Exception as e:
        print(f"❌ Error listing attempts: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve attempts: {str(e)}"
        )