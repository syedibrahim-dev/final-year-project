from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from utils.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # Core contact fields
    company_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    decision_maker_job_title = Column(String(255), nullable=True)

    # Firmographic fields
    industry = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    employee_count = Column(String(50), nullable=True)        # bucket: "1-50", "51-200", etc.
    annual_revenue_range = Column(String(50), nullable=True)   # "<$1M", "$1-10M", etc.
    website = Column(String(500), nullable=True)

    # ML scoring
    win_probability = Column(Float, nullable=True)
    allocation_decision = Column(String(50), default="PENDING")
    status = Column(String(50), default="PENDING")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", backref="leads")
    outreach = relationship("AutomatedOutreach", back_populates="lead", cascade="all, delete-orphan", uselist=False)


class AutomatedOutreach(Base):
    __tablename__ = "automated_outreach"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, unique=True)

    conversation_state = Column(JSON, nullable=True)  # list of messages [{role, content, timestamp}]
    last_message_at = Column(DateTime, nullable=True)
    escalated = Column(Boolean, default=False)
    escalated_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    outcome = Column(String(50), nullable=True)  # WON, LOST, IN_PROGRESS

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead", back_populates="outreach")
