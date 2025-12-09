from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from utils.database import Base

class TrainingContent(Base):
    __tablename__ = "training_content"
    __table_args__ = {'extend_existing': True}  # ✅ ADD THIS
    
    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String(255), unique=True, nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    version = Column(String(50), default="1.0")
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    upload_date = Column(DateTime, default=datetime.now(timezone.utc))
    uploader_id = Column(Integer, ForeignKey("users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    
    # Relationships
    uploader = relationship("User")
    organization = relationship("Organization", back_populates="training_content")