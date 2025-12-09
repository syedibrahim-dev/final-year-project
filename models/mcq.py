from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from utils.database import Base

class MCQTest(Base):
    """Stores generated MCQ tests that can be assigned to trainees"""
    __tablename__ = "mcq_tests"
    __table_args__ = {'extend_existing': True}  # ✅ ADD THIS
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    topic = Column(String(255), nullable=False)
    difficulty = Column(String(50), nullable=False)
    questions_json = Column(JSON, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    attempts = relationship("MCQAttempt", back_populates="test")

class MCQAttempt(Base):
    """Tracks individual trainee attempts on MCQ tests"""
    __tablename__ = "mcq_attempts"
    __table_args__ = {'extend_existing': True}  # ✅ ADD THIS
    
    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("mcq_tests.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    
    # Performance metrics
    score = Column(Float, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    time_taken_seconds = Column(Integer, nullable=True)
    
    # Detailed results
    answers_json = Column(JSON, nullable=False)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.now(timezone.utc))
    completed_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relationships
    test = relationship("MCQTest", back_populates="attempts")
    user = relationship("User")