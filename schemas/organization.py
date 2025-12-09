from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime


class OrganizationCreate(BaseModel):
    """Schema for creating a new organization"""
    name: str = Field(..., min_length=2, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)
    admin_name: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Sales Corp",
                "admin_email": "admin@acme.com",
                "admin_password": "SecurePass123!",
                "admin_name": "John Doe",
                "industry": "Technology"
            }
        }


class OrganizationOut(BaseModel):
    """Schema for organization output"""
    id: int
    name: str
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Acme Sales Corp",
                "metadata_json": {"industry": "Technology"},
                "created_at": "2025-12-08T10:30:00"
            }
        }


class InviteUserRequest(BaseModel):
    """Schema for inviting a user to organization"""
    email: EmailStr
    role: str = Field(..., pattern="^(admin|manager|trainer|trainee)$")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "newuser@acme.com",
                "role": "trainer"
            }
        }


class InviteTokenResponse(BaseModel):
    """Response with invite token"""
    invite_token: str
    email: str
    role: str
    organization_id: int
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "invite_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "email": "newuser@acme.com",
                "role": "trainer",
                "organization_id": 1,
                "message": "Send this token to complete registration"
            }
        }


class UserRoleUpdate(BaseModel):
    """Schema for updating user role in organization"""
    new_role: str = Field(..., pattern="^(admin|manager|trainer|trainee)$")
    
    class Config:
        json_schema_extra = {
            "example": {
                "new_role": "manager"
            }
        }