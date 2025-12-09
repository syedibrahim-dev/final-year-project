from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from utils.database import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}  # ✅ ADD THIS
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(String(50), default="trainee")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="users")