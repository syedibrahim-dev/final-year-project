from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)


class UserCreate(UserBase):
    """Schema for creating a user"""
    password: str = Field(..., min_length=8, max_length=100)
    role: str = Field(default="trainee")
    organization_id: int = Field(..., gt=0)
    
    @validator('role')
    def validate_role(cls, v):
        """Validate role is one of the allowed values"""
        allowed_roles = ['admin', 'manager', 'trainer', 'trainee']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "full_name": "John Doe",
                "password": "SecurePass123!",
                "role": "trainee",
                "organization_id": 1
            }
        }


class UserUpdate(BaseModel):
    """Schema for updating user profile"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    
    @validator('full_name')
    def validate_full_name(cls, v):
        """Validate full name if provided"""
        if v is not None and v.strip() == "":
            raise ValueError('Full name cannot be empty')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "newemail@example.com",
                "full_name": "New Name"
            }
        }


class UserOut(BaseModel):
    """Schema for user output (no password)"""
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    organization_id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "email": "user@example.com",
                "full_name": "John Doe",
                "role": "admin",
                "organization_id": 1,
                "is_active": True,
                "created_at": "2025-12-08T10:30:00"
            }
        }


class UserInDB(UserBase):
    """User as stored in database"""
    id: int
    hashed_password: str
    role: str
    organization_id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "yourpassword"
            }
        }


class UserPasswordChange(BaseModel):
    """Schema for changing password"""
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Validate that new password and confirm password match"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('new_password')
    def password_strength(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        
        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                'Password must contain at least one uppercase letter, '
                'one lowercase letter, and one digit'
            )
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "OldPass123!",
                "new_password": "NewPass123!",
                "confirm_password": "NewPass123!"
            }
        }


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }


class TokenData(BaseModel):
    """Schema for token data"""
    email: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    organization_id: Optional[int] = None


class UserListResponse(BaseModel):
    """Schema for list of users"""
    users: list[UserOut]
    total: int
    page: int = 1
    page_size: int = 50
    
    class Config:
        json_schema_extra = {
            "example": {
                "users": [
                    {
                        "id": 1,
                        "email": "user@example.com",
                        "full_name": "John Doe",
                        "role": "admin",
                        "organization_id": 1,
                        "is_active": True,
                        "created_at": "2025-12-08T10:30:00"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 50
            }
        }


class UserRoleUpdate(BaseModel):
    """Schema for updating user role"""
    role: str = Field(...)
    
    @validator('role')
    def validate_role(cls, v):
        """Validate role is one of the allowed values"""
        allowed_roles = ['admin', 'manager', 'trainer', 'trainee']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "manager"
            }
        }


class UserStatusUpdate(BaseModel):
    """Schema for updating user active status"""
    is_active: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_active": False
            }
        }