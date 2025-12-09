from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt

from utils.database import get_db
from utils.security import get_password_hash, get_current_user
from models.organization import Organization
from models.user import User
from schemas.organization import OrganizationCreate, OrganizationOut
from config.settings import settings

router = APIRouter(prefix="/orgs", tags=["Organizations"])


# ✅ NEW: Direct POST to /api/orgs (what your frontend calls)
@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    org_data: OrganizationCreate,
    db: Session = Depends(get_db)
):
    """Create a new organization with admin user (direct endpoint)"""
    
    # Check if org name exists
    existing_org = db.query(Organization).filter(
        Organization.name == org_data.name
    ).first()
    
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name already exists"
        )
    
    # Check if admin email exists
    existing_user = db.query(User).filter(
        User.email == org_data.admin_email
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    try:
        # Create organization
        new_org = Organization(name=org_data.name)
        db.add(new_org)
        db.flush()
        
        # Create admin user
        admin_user = User(
            email=org_data.admin_email,
            hashed_password=get_password_hash(org_data.admin_password),
            role="admin",
            organization_id=new_org.id,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(new_org)
        
        print(f"✅ Organization '{new_org.name}' created with admin: {admin_user.email}")
        
        return new_org
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create organization: {str(e)}"
        )


# ✅ EXISTING: Alternative /register endpoint (kept for compatibility)
@router.post("/register", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def register_organization(
    org_data: OrganizationCreate,
    db: Session = Depends(get_db)
):
    """Register a new organization with admin user"""
    
    # Check if org name exists
    existing_org = db.query(Organization).filter(
        Organization.name == org_data.name
    ).first()
    
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name already exists"
        )
    
    # Check if admin email exists
    existing_user = db.query(User).filter(
        User.email == org_data.admin_email
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create organization
    new_org = Organization(name=org_data.name)
    db.add(new_org)
    db.flush()
    
    # Create admin user
    admin_user = User(
        email=org_data.admin_email,
        hashed_password=get_password_hash(org_data.admin_password),
        role="admin",
        organization_id=new_org.id,
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(new_org)
    
    return new_org


# ✅ EXISTING: Invite endpoint (unchanged)
@router.post("/{org_id}/users/invite")
def invite_user(
    org_id: int,
    email: str,
    role: str = "trainee",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Invite a new user to the organization"""
    
    print(f"📧 Invite request:")
    print(f"   Org: {org_id}")
    print(f"   Email: {email}")
    print(f"   Role: {role}")
    print(f"   Requester: {current_user.email}")
    
    # Check user belongs to org
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization"
        )
    
    # Check user has permission
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers can invite users"
        )
    
    # Check org exists
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Check email doesn't exist
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email {email} already exists"
        )
    
    # Validate role
    valid_roles = ["admin", "manager", "trainer", "trainee"]
    if role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )
    
    # Create invite token
    try:
        expire = datetime.utcnow() + timedelta(days=7)
        token_data = {
            "sub": email,
            "role": role,
            "org_id": org_id,
            "type": "invite",
            "exp": expire
        }
        
        invite_token = jwt.encode(
            token_data, 
            settings.SECRET_KEY, 
            algorithm=settings.ALGORITHM
        )
        
        print(f"✅ Token generated for {email}")
        
        return {
            "invite_token": invite_token,
            "token": invite_token,
            "email": email,
            "role": role,
            "organization_id": org_id,
            "expires_in": "7 days",
            "message": f"Send this token to {email} to complete registration"
        }
        
    except Exception as e:
        print(f"❌ Token generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create invite token: {str(e)}"
        )