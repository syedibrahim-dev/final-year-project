from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from jose import JWTError, jwt
from pydantic import BaseModel

from utils.database import get_db
from utils.security import verify_password, create_access_token, get_password_hash
from models.user import User
from models.organization import Organization
from schemas.user import Token
from config.settings import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ✅ NEW: Request model for registration
class RegisterRequest(BaseModel):
    token: str
    password: str


# ✅ EXISTING: Login endpoint (unchanged)
@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login endpoint"""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id, "email": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# ✅ NEW: Register endpoint (for invite token)
@router.post("/register", response_model=Token)
def register_with_invite(
    registration: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user using an invite token
    
    Request body:
    {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "password": "securePassword123"
    }
    """
    
    print(f"📝 Registration attempt")
    
    try:
        # Decode invite token
        payload = jwt.decode(
            registration.token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        email = payload.get("sub")
        role = payload.get("role")
        org_id = payload.get("org_id")
        token_type = payload.get("type")
        
        # Validate token type
        if token_type != "invite":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )
        
        print(f"   Email: {email}")
        print(f"   Role: {role}")
        print(f"   Org ID: {org_id}")
        
    except JWTError as e:
        print(f"❌ Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        print(f"❌ User already exists: {email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Validate organization
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        print(f"❌ Organization not found: {org_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Validate password
    if len(registration.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    try:
        # Create new user
        new_user = User(
            email=email,
            hashed_password=get_password_hash(registration.password),
            role=role,
            organization_id=org_id,
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"✅ User created: {email} (role: {role})")
        
        # Create access token for automatic login
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"user_id": new_user.id, "email": new_user.email, "role": new_user.role},
            expires_delta=access_token_expires
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
        
    except Exception as e:
        db.rollback()
        print(f"❌ Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )