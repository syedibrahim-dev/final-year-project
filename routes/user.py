from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from utils.database import get_db
from utils.dependencies import get_current_user, role_required
from models.user import User
from schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current logged-in user information
    This is called after login to fetch user details
    """
    print(f"\n👤 Fetching user info for: {current_user.email}")
    print(f"   User ID: {current_user.id}")
    print(f"   Role: {current_user.role}")
    print(f"   Org ID: {current_user.organization_id}\n")
    
    return current_user


@router.get("/{user_id}", response_model=UserOut)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager"]))
):
    """
    Get user by ID (admin/manager only)
    """
    # Verify user is in same organization
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return user


@router.patch("/me", response_model=UserOut)
def update_current_user(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update current user's profile
    """
    print(f"\n🔄 Updating user: {current_user.email}")
    
    # Update allowed fields
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
        print(f"   Updated name: {user_update.full_name}")
    
    if user_update.email is not None:
        # Check if email is already taken
        existing = db.query(User).filter(
            User.email == user_update.email,
            User.id != current_user.id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        
        current_user.email = user_update.email
        print(f"   Updated email: {user_update.email}")
    
    db.commit()
    db.refresh(current_user)
    
    print(f"✅ User updated successfully\n")
    
    return current_user


@router.delete("/me")
def delete_current_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete current user account
    """
    # Prevent last admin from deleting themselves
    if current_user.role == "admin":
        admin_count = db.query(User).filter(
            User.organization_id == current_user.organization_id,
            User.role == "admin"
        ).count()
        
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last admin account"
            )
    
    print(f"\n🗑️  Deleting user: {current_user.email}")
    
    db.delete(current_user)
    db.commit()
    
    print(f"✅ User deleted successfully\n")
    
    return {"message": "Account deleted successfully"}