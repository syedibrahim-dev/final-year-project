from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, DateTime, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from utils.database import Base
import enum

class SessionStatus(str, enum.Enum):
    """Enum for session status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

class MessageSender(str, enum.Enum):
    """Enum for message sender"""
    TRAINEE = "trainee"
    AI_CUSTOMER = "ai_customer"

class RoleplayPersona(Base):
    """Stores customer personas for roleplay sessions"""
    __tablename__ = "roleplay_personas"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    scenario_brief = Column(Text, nullable=True)   # Short briefing shown to trainee before session starts
    personality_traits = Column(JSON, nullable=False)  # {"patience": "medium", "rag_probing_style": "challenge"}
    trigger_topics = Column(JSON, nullable=True)   # {"topic_key": "how this persona reacts when topic is raised"}
    company_context = Column(JSON, nullable=True)  # {"industry", "company_size", "tech_stack", "business_problems", ...}
    common_objections = Column(JSON, nullable=False)  # Natural-language spoken objections
    tone = Column(String(50), nullable=False)  # casual, formal
    difficulty = Column(String(50), nullable=False)  # beginner, intermediate, advanced
    scenario_type = Column(String(50), nullable=True, default="acquisition")  # acquisition, expansion, displacement
    is_predefined = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relationships
    sessions = relationship("RoleplaySession", back_populates="persona")

class RoleplaySession(Base):
    """Tracks individual practice sessions"""
    __tablename__ = "roleplay_sessions"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    trainee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    persona_id = Column(Integer, ForeignKey("roleplay_personas.id"), nullable=False, index=True)
    persona_snapshot = Column(JSON, nullable=False)  # Snapshot of persona config at session start
    status = Column(String(50), nullable=False, default=SessionStatus.ACTIVE.value)
    started_at = Column(DateTime, default=datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    total_messages = Column(Integer, default=0)
    agent_cache = Column(JSON, nullable=True)  # Latest analyst agent results (stage, hint) for resume
    
    # Relationships
    persona = relationship("RoleplayPersona", back_populates="sessions")
    trainee = relationship("User")
    messages = relationship("RoleplayMessage", back_populates="session", cascade="all, delete-orphan")
    evaluation = relationship("RoleplayEvaluation", back_populates="session", uselist=False)

class RoleplayMessage(Base):
    """Stores conversation transcript"""
    __tablename__ = "roleplay_messages"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("roleplay_sessions.id"), nullable=False, index=True)
    sender = Column(String(50), nullable=False)  # trainee or ai_customer
    message_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    sequence_number = Column(Integer, nullable=False)
    stage_snapshot = Column(JSON, nullable=True)  # Stage info at time of message (for analytics/replay)
    
    # Relationships
    session = relationship("RoleplaySession", back_populates="messages")

class RoleplayEvaluation(Base):
    """Stores AI-generated feedback for sessions"""
    __tablename__ = "roleplay_evaluations"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("roleplay_sessions.id"), nullable=False, unique=True, index=True)
    overall_score = Column(Float, nullable=False)  # 0-100 (from NLP)
    category_scores = Column(JSON, nullable=False)  # From NLP: {rapport: 15, discovery: 18, ...}
    summary = Column(Text, nullable=True)  # LLM: 2-3 sentence qualitative summary
    detailed_feedback = Column(JSON, nullable=False)  # Full structured feedback (NLP + LLM)
    strengths = Column(JSON, nullable=False)  # Array of 3-5 strengths (from LLM)
    improvement_areas = Column(JSON, nullable=False)  # Array of 3-5 improvements (from LLM)
    nlp_metrics = Column(JSON, nullable=False)  # Detailed NLP metrics (questions, keywords, etc)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relationships
    session = relationship("RoleplaySession", back_populates="evaluation")
