from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from utils.database import Base

class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {'extend_existing': True}  # ✅ ADD THIS
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relationships
    users = relationship("User", back_populates="organization")
    invite_tokens = relationship("InviteToken", back_populates="organization")
    training_content = relationship("TrainingContent", back_populates="organization")