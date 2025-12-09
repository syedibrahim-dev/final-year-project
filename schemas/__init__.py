"""
Schemas Package
Pydantic models for request/response validation
"""

# Auth schemas
from schemas.auth import (
    Token as AuthToken,
    TokenData as AuthTokenData,
    UserRegisterInvite
)

# Organization schemas
from schemas.organization import (
    OrganizationCreate,
    OrganizationOut
)

# User schemas
from schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserOut,
    UserInDB,
    UserLogin,
    UserPasswordChange,
    Token,
    TokenData,
    UserListResponse,
    UserRoleUpdate,
    UserStatusUpdate
)

# Content schemas
from schemas.content import (
    ContentUpload,
    ContentUploadResponse,
    ContentOut,
    ContentRetrieveRequest,
    ContentChunk,
    RetrievalResult,
    ContentDeleteResponse,
    ContentListResponse,
    ContentStatsResponse
)

# MCQ schemas
from schemas.mcq import (
    MCQGenerateRequest,
    MCQOption,
    MCQQuestion,
    MCQTestCreate,
    MCQTestOut,
    MCQAttemptSubmit,
    MCQAttemptOut
)

__all__ = [
    # Auth schemas
    "AuthToken",
    "AuthTokenData",
    "UserRegisterInvite",
    
    # Organization schemas
    "OrganizationCreate",
    "OrganizationOut",
    
    # User schemas
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserOut",
    "UserInDB",
    "UserLogin",
    "UserPasswordChange",
    "Token",
    "TokenData",
    "UserListResponse",
    "UserRoleUpdate",
    "UserStatusUpdate",
    
    # Content schemas
    "ContentUpload",
    "ContentUploadResponse",
    "ContentOut",
    "ContentRetrieveRequest",
    "ContentChunk",
    "RetrievalResult",
    "ContentDeleteResponse",
    "ContentListResponse",
    "ContentStatsResponse",
    
    # MCQ schemas
    "MCQGenerateRequest",
    "MCQOption",
    "MCQQuestion",
    "MCQTestCreate",
    "MCQTestOut",
    "MCQAttemptSubmit",
    "MCQAttemptOut"
]