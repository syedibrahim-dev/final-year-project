import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Generator

# IMPORTANT: Ensure you have run:
# pip install fastapi "uvicorn[standard]" sqlalchemy pydantic python-jose[cryptography] passlib[bcrypt] pymysql
# And run the upgrade command: pip install --upgrade passlib bcrypt

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, DateTime, JSON, or_
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware # Added CORS Import

# --- Configuration and Constants ---

# Security Settings
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Database Configuration (MySQL Connection)
# NOTE: Using pymysql. Password 'pokemon@1234' is correctly URL-encoded.
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://shah:pokemon1234@localhost:3306/salesforge_db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    # Optional: Pool settings for production databases
    # pool_pre_ping=True 
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Password Hashing
# Changed to sha256_crypt for dependency reliability
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
# RBAC Roles
ROLES = ["admin", "manager", "trainer", "trainee"]
ROLE_HIERARCHY = {
    "admin": ["manager", "trainer", "trainee"],
    "manager": ["trainer", "trainee"],
    "trainer": ["trainee"],
    "trainee": [],
}

# --- Database Models (SQLAlchemy) ---

Base = declarative_base()

class Organization(Base):
    """Represents a client company/organization."""
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    # FIX: Added length for VARCHAR on MySQL
    name = Column(String(255), unique=True, nullable=False)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    users = relationship("User", back_populates="organization")
    invite_tokens = relationship("InviteToken", back_populates="organization")

class User(Base):
    """Represents a user (employee) in an organization."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    # FIX: Added length for VARCHAR on MySQL
    email = Column(String(255), unique=True, nullable=False, index=True)
    # FIX: Added length for VARCHAR (accommodates SHA256 hash output)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    # FIX: Added length for VARCHAR (to hold role name)
    role = Column(String(50), default="trainee")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    organization = relationship("Organization", back_populates="users")

class InviteToken(Base):
    """Stores tokens for user invitations."""
    __tablename__ = "invite_tokens"
    id = Column(Integer, primary_key=True)
    # FIX: Added length for VARCHAR
    token = Column(String(255), unique=True, nullable=False, index=True)
    # FIX: Added length for VARCHAR
    email = Column(String(255), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    expires_at = Column(DateTime, nullable=False)
    
    organization = relationship("Organization", back_populates="invite_tokens")

# --- Pydantic Schemas (omitted for brevity, assume correct) ---
class OrgCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, example="QuickTest Inc.")
    admin_email: EmailStr = Field(..., example="admin@quicktest.com")
    admin_password: str = Field(..., min_length=8)

class UserInvite(BaseModel):
    email: EmailStr = Field(..., example="trainee@quicktest.com")
    role: str = Field(..., example="trainee", description=f"Must be one of: {ROLES}")

class UserRegisterInvite(BaseModel):
    token: str
    password: str = Field(..., min_length=8)

class UserRoleUpdate(BaseModel):
    role: str = Field(..., example="manager", description=f"Must be one of: {ROLES}")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None

class OrganizationOut(BaseModel):
    id: int
    name: str
    metadata_json: dict
    class Config:
        from_attributes = True

class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    role: str
    organization_id: int
    organization: OrganizationOut
    class Config:
        from_attributes = True

class UserSimple(BaseModel):
    id: int
    email: EmailStr
    role: str
    organization_id: int
    class Config:
        from_attributes = True
# --- End Pydantic Schemas ---

# --- Security Functions ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Generates a hash for a password using the configured scheme (sha256_crypt).
    """
    try:
        return pwd_context.hash(password)
    except Exception as e:
        # Catch and re-raise as an internal error for robust handling
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password hashing failed (Dependency Error). Please check passlib/hashing library setup. Original error: {e}"
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JSON Web Token (JWT) for authentication."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire, "sub": str(data["user_id"])})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Dependencies (omitted for brevity, assume correct) ---
def get_db() -> Generator[Session, None, None]:
    """Dependency to yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """Decodes JWT and fetches the authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

def role_required(required_roles: List[str]):
    """Dependency generator for Role-Based Access Control (RBAC)."""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{current_user.role}' does not have permission for this action.",
            )
        return current_user
    return role_checker
# --- End Dependencies ---

# --- API Setup ---

app = FastAPI(
    title="SalesForge User & Organization Management",
    description="Backend API for organization, user, and role management with RBAC.",
)

# --- CORS Configuration (Essential Fix) ---
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- End CORS Configuration ---


# Initialize database tables
def create_db_tables():
    Base.metadata.create_all(bind=engine)

# --- Routes: Authentication (omitted for brevity, assume correct) ---

@app.post("/auth/register", response_model=Token, summary="Complete user registration via invite token")
def register_with_token(user_data: UserRegisterInvite, db: Session = Depends(get_db)):
    """
    Allows a user to complete their registration by providing a valid invite token and setting a password.
    """
    invite = db.query(InviteToken).filter(InviteToken.token == user_data.token).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite token.")

    # FIX: Make the retrieved time timezone-aware before comparison.
    invite_aware_time = invite.expires_at
    if invite_aware_time.tzinfo is None:
        invite_aware_time = invite.expires_at.replace(tzinfo=timezone.utc)
        
    if invite_aware_time < datetime.now(timezone.utc):
        db.delete(invite)
        db.commit()
        raise HTTPException(status_code=400, detail="Invite token has expired.")
    # --- END FIX ---
    
    user = db.query(User).filter(User.email == invite.email).first()

    if user and user.hashed_password:
        db.delete(invite)
        db.commit()
        raise HTTPException(status_code=400, detail="User already registered.")
    
    if not user:
        raise HTTPException(status_code=400, detail="Associated user not found.")

    # Hash password and update user record
    user.hashed_password = get_password_hash(user_data.password)
    db.delete(invite)
    db.commit()

    # Generate and return access token
    access_token = create_access_token(
        data={"user_id": user.id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/login", response_model=Token, summary="User login and JWT generation")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Standard OAuth2 flow for logging in with email (username) and password."""
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not user.is_active or user.hashed_password is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})

    access_token = create_access_token(
        data={"user_id": user.id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Routes: Organization Management ---

@app.post("/orgs", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED, summary="Create a new organization and initial Admin user")
def create_organization(org_data: OrgCreate, db: Session = Depends(get_db)):
    """
    Creates a new Organization and the first user who is automatically assigned the 'admin' role.
    """
    if db.query(Organization).filter(Organization.name == org_data.name).first():
        raise HTTPException(status_code=400, detail="Organization name already exists.")
    
    if db.query(User).filter(User.email == org_data.admin_email).first():
        raise HTTPException(status_code=400, detail="Admin email is already registered.")

    # 1. Create Organization
    new_org = Organization(name=org_data.name)
    db.add(new_org)
    db.commit()
    db.refresh(new_org)

    # 2. Create Admin User
    hashed_password = get_password_hash(org_data.admin_password) 
    admin_user = User(
        email=org_data.admin_email,
        hashed_password=hashed_password,
        role="admin",
        organization_id=new_org.id
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    return new_org

@app.post("/orgs/{org_id}/invite", response_model=Token, status_code=status.HTTP_201_CREATED, summary="Invite a new user to the organization (Manager/Admin required)")
def invite_user_to_org(
    org_id: int,
    invite_data: UserInvite,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager"]))
):
    """Invites a new user."""
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized to invite to this organization.")
    if invite_data.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {ROLES}")

    existing_user = db.query(User).filter(User.email == invite_data.email).first()
    if existing_user:
        if existing_user.organization_id == org_id:
            raise HTTPException(status_code=400, detail="User already belongs to this organization.")
        else:
            raise HTTPException(status_code=400, detail="Email is registered with another organization.")

    new_user = User(
        email=invite_data.email,
        role=invite_data.role,
        organization_id=org_id,
        hashed_password=None
    )
    db.add(new_user)
    
    token_value = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    new_invite = InviteToken(
        token=token_value,
        email=invite_data.email,
        organization_id=org_id,
        expires_at=expires_at
    )
    db.add(new_invite)
    db.commit()
    db.refresh(new_user)
    
    return {"access_token": token_value, "token_type": "invite"}

# --- Routes: User Management (omitted for brevity, assume correct) ---

@app.get("/users/me", response_model=UserOut, summary="Get details of the currently authenticated user")
def get_current_user_details(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/users/{user_id}", response_model=UserSimple, summary="Get details of a specific user (Admin/Manager required)")
def get_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager", "trainer"]))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if current_user.role != "admin" and current_user.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized to view users in other organizations.")
    return user

@app.patch("/users/{user_id}/role", response_model=UserSimple, summary="Update a user's role (Admin/Manager required)")
def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager"]))
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if current_user.organization_id != target_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot modify user in a different organization.")
    if role_update.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {ROLES}")

    current_role = current_user.role
    target_role = target_user.role
    new_role = role_update.role

    if current_role == "manager":
        if target_role not in ROLE_HIERARCHY["manager"]:
             raise HTTPException(status_code=403, detail="Manager cannot modify user with equal or higher role.")
        if new_role == "admin":
             raise HTTPException(status_code=403, detail="Manager cannot assign 'admin' role.")

    if target_role == "admin" and current_role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can modify another admin's role.")
        
    target_user.role = new_role
    db.commit()
    db.refresh(target_user)
    
    return target_user

# --- Startup Event ---
@app.on_event("startup")
def on_startup():
    print("Creating database tables...")
    create_db_tables()
    print("Database ready.")

# --- Root Endpoint (Health Check) ---
@app.get("/", summary="API Health Check")
def read_root():
    return {"status": "ok", "service": "SalesForge User & Org Management"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)