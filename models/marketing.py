from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from utils.database import Base


class MarketingPost(Base):
    """Stores AI-generated social media posts"""
    __tablename__ = "marketing_posts"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Content
    caption = Column(Text, nullable=False)
    image_prompt = Column(Text, nullable=False)
    image_filename = Column(String(255), nullable=True)   # UUID .png stored in media/marketing/
    image_seed = Column(Integer, nullable=True)

    # Targeting
    platforms = Column(JSON, nullable=False, default=list)  # ["facebook", "instagram", "linkedin"]

    # Lifecycle: draft → scheduled → published | failed
    status = Column(String(50), nullable=False, default="draft")
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    publish_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    creator = relationship("User")
    organization = relationship("Organization")
