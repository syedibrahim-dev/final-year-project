from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from utils.database import Base

class InviteToken(Base):
    __tablename__ = "invite_tokens"
    __table_args__ = {'extend_existing': True}  # ✅ ADD THIS
    
    id = Column(Integer, primary_key=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    organization = relationship("Organization", back_populates="invite_tokens")