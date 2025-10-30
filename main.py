import os
import secrets
import io
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Generator, Union

# --- RAG/LangChain Imports ---
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma

from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, DateTime, JSON, or_
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware 

# --- RAG Configuration ---
CHROMA_PERSIST_DIR = "./chroma_data" 
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2" 

# --- Configuration and Constants ---
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://shah:pokemon1234@localhost:3306/salesforge_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
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
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    users = relationship("User", back_populates="organization")
    invite_tokens = relationship("InviteToken", back_populates="organization")
    training_content = relationship("TrainingContent", back_populates="organization")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(String(50), default="trainee")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    organization = relationship("Organization", back_populates="users")

class InviteToken(Base):
    __tablename__ = "invite_tokens"
    id = Column(Integer, primary_key=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    expires_at = Column(DateTime, nullable=False)
    organization = relationship("Organization", back_populates="invite_tokens")

class TrainingContent(Base):
    __tablename__ = "training_content"
    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String(255), unique=True, nullable=False, index=True) # This is the ID for Chroma
    file_name = Column(String(255), nullable=False)
    version = Column(String(50), default="1.0")
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    upload_date = Column(DateTime, default=datetime.now(timezone.utc))
    uploader_id = Column(Integer, ForeignKey("users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    uploader = relationship("User") 
    organization = relationship("Organization", back_populates="training_content")

# --- Pydantic Schemas ---
# FIX: Restored all Pydantic models that were abbreviated

class OrgCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)

class UserInvite(BaseModel):
    email: EmailStr
    role: str

class UserRegisterInvite(BaseModel):
    token: str
    password: str = Field(..., min_length=8)

# FIX: Added missing UserRoleUpdate model
class UserRoleUpdate(BaseModel):
    role: str = Field(..., example="manager")

class Token(BaseModel):
    access_token: str
    token_type: str

# FIX: Added missing TokenData model
class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None

class OrganizationOut(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool # Added is_active back
    role: str
    organization: OrganizationOut
    class Config:
        from_attributes = True

class UserSimple(BaseModel):
    id: int
    email: EmailStr
    role: str
    class Config:
        from_attributes = True

class ContentMetadata(BaseModel):
    product_name: str = Field(..., max_length=100)
    version: str = Field(..., max_length=50) # Default is now handled by Form()

class RetrievalResult(BaseModel):
    chunk: str
    source: str
    page: int
    score: Optional[float] = None

class TrainingContentOut(BaseModel):
    id: int # The SQL ID, used for deletion
    content_id: str # The Chroma ID
    file_name: str
    version: str
    upload_date: datetime
    chunk_count: int
    class Config:
        from_attributes = True

# --- Security, Dependencies, API Setup, CORS (Omitted for brevity) ---
def verify_password(plain_password: str, hashed_password: str) -> bool: return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password: str) -> str:
    try: return pwd_context.hash(password)
    except Exception as e: raise HTTPException(status_code=500, detail=f"Password hashing failed: {e}")
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta: expire = datetime.now(timezone.utc) + expires_delta
    else: expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "sub": str(data["user_id"])})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try: yield db
    finally: db.close()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None: raise credentials_exception
        token_data = TokenData(user_id=user_id) # This line also needs TokenData
    except JWTError: raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active: raise credentials_exception
    return user
def role_required(required_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(status_code=403, detail=f"User role '{current_user.role}' does not have permission.")
        return current_user
    return role_checker
app = FastAPI(title="SalesForge API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def create_db_tables(): Base.metadata.create_all(bind=engine)

# --- RAG Ingestion Pipeline (omitted for brevity) ---
def ingest_document_pipeline(file_path: str, org_id: int, content_id: str):
    try:
        loader = PyPDFLoader(file_path); docs = loader.load(); page_count = len(docs)
    except Exception as e:
        if os.path.exists(file_path): os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to load document: {e}")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs); num_chunks = len(chunks)
    if num_chunks == 0:
        if os.path.exists(file_path): os.remove(file_path)
        raise HTTPException(status_code=400, detail="Document appears to be empty or unreadable.")
    for chunk in chunks:
        page_num = chunk.metadata.get("page", 0) + 1 
        chunk.metadata.update({"org_id": str(org_id), "content_id": content_id, "source_file": os.path.basename(file_path), "page": page_num})
    try:
        emb = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
        collection_name = f"org_{org_id}_collection"
        vstore = Chroma.from_documents(chunks, embedding=emb, persist_directory=CHROMA_PERSIST_DIR, collection_name=collection_name)
        return num_chunks, page_count
    except Exception as e:
        if os.path.exists(file_path): os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)

# --- Routes: Authentication (omitted for brevity) ---
@app.post("/auth/register", response_model=Token)
def register_with_token(user_data: UserRegisterInvite, db: Session = Depends(get_db)):
    invite = db.query(InviteToken).filter(InviteToken.token == user_data.token).first()
    if not invite: raise HTTPException(status_code=404, detail="Invalid or expired invite token.")
    invite_aware_time = invite.expires_at
    if invite_aware_time.tzinfo is None: invite_aware_time = invite.expires_at.replace(tzinfo=timezone.utc)
    if invite_aware_time < datetime.now(timezone.utc):
        db.delete(invite); db.commit(); raise HTTPException(status_code=400, detail="Invite token has expired.")
    user = db.query(User).filter(User.email == invite.email).first()
    if user and user.hashed_password:
        db.delete(invite); db.commit(); raise HTTPException(status_code=400, detail="User already registered.")
    if not user: raise HTTPException(status_code=400, detail="Associated user not found.")
    user.hashed_password = get_password_hash(user_data.password)
    db.delete(invite); db.commit()
    access_token = create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}
@app.post("/auth/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not user.is_active or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    access_token = create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

# --- Routes: Organization Management (omitted for brevity) ---
@app.post("/orgs", response_model=OrganizationOut, status_code=201)
def create_organization(org_data: OrgCreate, db: Session = Depends(get_db)):
    if db.query(Organization).filter(Organization.name == org_data.name).first():
        raise HTTPException(status_code=400, detail="Organization name already exists.")
    if db.query(User).filter(User.email == org_data.admin_email).first():
        raise HTTPException(status_code=400, detail="Admin email is already registered.")
    new_org = Organization(name=org_data.name)
    db.add(new_org); db.commit(); db.refresh(new_org)
    hashed_password = get_password_hash(org_data.admin_password) 
    admin_user = User(email=org_data.admin_email, hashed_password=hashed_password, role="admin", organization_id=new_org.id)
    db.add(admin_user); db.commit(); db.refresh(admin_user)
    return new_org
@app.post("/orgs/{org_id}/invite", response_model=Token, status_code=201)
def invite_user_to_org(org_id: int, invite_data: UserInvite, db: Session = Depends(get_db), current_user: User = Depends(role_required(["admin", "manager"]))):
    if current_user.organization_id != org_id: raise HTTPException(status_code=403, detail="Not authorized.")
    if invite_data.role not in ROLES: raise HTTPException(status_code=400, detail="Invalid role.")
    existing_user = db.query(User).filter(User.email == invite_data.email).first()
    if existing_user:
        if existing_user.organization_id == org_id: raise HTTPException(status_code=400, detail="User already belongs to this organization.")
        else: raise HTTPException(status_code=400, detail="Email is registered with another organization.")
    new_user = User(email=invite_data.email, role=invite_data.role, organization_id=org_id, hashed_password=None)
    db.add(new_user)
    token_value = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    new_invite = InviteToken(token=token_value, email=invite_data.email, organization_id=org_id, expires_at=expires_at)
    db.add(new_invite); db.commit(); db.refresh(new_user)
    return {"access_token": token_value, "token_type": "invite"}

# --- Routes: User Management (omitted for brevity) ---
@app.get("/users/me", response_model=UserOut)
def get_current_user_details(current_user: User = Depends(get_current_user)): return current_user
@app.get("/users/{user_id}", response_model=UserSimple)
def get_user_details(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(role_required(["admin", "manager", "trainer"]))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found.")
    if current_user.role != "admin" and current_user.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized.")
    return user

# THIS IS THE ENDPOINT THAT CAUSED THE ERROR
@app.patch("/users/{user_id}/role", response_model=UserSimple)
def update_user_role(user_id: int, role_update: UserRoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(role_required(["admin", "manager"]))):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user: raise HTTPException(status_code=404, detail="Target user not found.")
    if current_user.organization_id != target_user.organization_id: raise HTTPException(status_code=403, detail="Not authorized.")
    if role_update.role not in ROLES: raise HTTPException(status_code=400, detail="Invalid role.")
    current_role, target_role, new_role = current_user.role, target_user.role, role_update.role
    if current_role == "manager":
        if target_role not in ROLE_HIERARCHY["manager"]: raise HTTPException(status_code=403, detail="Manager cannot modify this user.")
        if new_role == "admin": raise HTTPException(status_code=403, detail="Manager cannot assign 'admin' role.")
    if target_role == "admin" and current_role != "admin": raise HTTPException(status_code=403, detail="Only an admin can modify another admin.")
    target_user.role = new_role
    db.commit(); db.refresh(target_user)
    return target_user

# --- Routes: Training Content (Module 2) ---
@app.post("/orgs/{org_id}/content/upload", summary="Upload and ingest training content", status_code=202)
async def upload_and_ingest_content(org_id: int, product_name: str = Form(..., max_length=100), version: str = Form("1.0", max_length=50), file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(role_required(["admin", "manager"]))):
    if current_user.organization_id != org_id: raise HTTPException(status_code=403, detail="Not authorized.")
    content_id = secrets.token_urlsafe(16); temp_dir = "temp_uploads"; temp_file_path = os.path.join(temp_dir, f"{content_id}_{file.filename}")
    os.makedirs(temp_dir, exist_ok=True)
    if file.content_type != "application/pdf": raise HTTPException(status_code=400, detail="Only PDF files are currently supported.")
    try:
        contents = await file.read();
        with open(temp_file_path, "wb") as buffer: buffer.write(contents)
    except Exception as e: raise HTTPException(status_code=500, detail=f"File storage failed: {e}")
    try:
        num_chunks, page_count = ingest_document_pipeline(temp_file_path, org_id, content_id)
    except HTTPException as e: raise e
    except Exception as e: raise HTTPException(status_code=500, detail=f"Ingestion pipeline failed: {str(e)}")
    content_meta = TrainingContent(content_id=content_id, file_name=file.filename, version=version, page_count=page_count, chunk_count=num_chunks, uploader_id=current_user.id, organization_id=org_id)
    db.add(content_meta); db.commit()
    return {"content_id": content_id, "message": "File successfully uploaded and indexed.", "chunks_indexed": num_chunks}

@app.get("/orgs/{org_id}/retriever", response_model=List[RetrievalResult], summary="Retrieve relevant chunks for a query (Test Embeddings)")
def retrieve_content(org_id: int, q: str, k: int = 4, current_user: User = Depends(role_required(ROLES))):
    if current_user.organization_id != org_id: raise HTTPException(status_code=403, detail="Not authorized.")
    try:
        emb = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
        collection_name = f"org_{org_id}_collection"
        vstore = Chroma(persist_directory=CHROMA_PERSIST_DIR, embedding_function=emb, collection_name=collection_name)
        results = vstore.similarity_search_with_score(q, k=k)
        retrieved_data = []
        for doc, score in results:
            retrieved_data.append(RetrievalResult(chunk=doc.page_content, source=doc.metadata.get("source_file", "Unknown"), page=doc.metadata.get("page", 0), score=score))
        return retrieved_data
    except Exception as e:
        print(f"Retrieval Error: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed. Index may not exist: {e}")

# --- NEW: Admin UI Endpoints ---
@app.get("/orgs/{org_id}/content", response_model=List[TrainingContentOut], summary="List all uploaded training documents (Admin UI)")
def list_uploaded_content(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager"]))
):
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized for this organization.")
    
    content_list = db.query(TrainingContent).filter(TrainingContent.organization_id == org_id).order_by(TrainingContent.upload_date.desc()).all()
    return content_list

@app.delete("/orgs/{org_id}/content/{content_id}", status_code=204, summary="Delete a training document (Admin UI)")
def delete_training_content(
    org_id: int,
    content_id: int, # This is the SQL Primary Key (id)
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin", "manager"]))
):
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized for this organization.")

    # 1. Find the content metadata in SQL
    content_to_delete = db.query(TrainingContent).filter(
        TrainingContent.id == content_id,
        TrainingContent.organization_id == org_id
    ).first()

    if not content_to_delete:
        raise HTTPException(status_code=404, detail="Content not found.")

    # 2. Delete vectors from ChromaDB
    try:
        collection_name = f"org_{org_id}_collection"
        emb = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
        vstore = Chroma(
            persist_directory=CHROMA_PERSIST_DIR, 
            embedding_function=emb, 
            collection_name=collection_name
        )
        
        # Delete using the unique 'content_id' string we stored in metadata
        vstore.delete(where={"content_id": content_to_delete.content_id})
        print(f"Deleted vectors for content_id: {content_to_delete.content_id}")
    except Exception as e:
        # Log the error but don't stop. We still want to delete the SQL entry.
        print(f"Warning: Failed to delete vectors from Chroma. Manual cleanup may be needed. Error: {e}")

    # 3. Delete the metadata from SQL DB
    db.delete(content_to_delete)
    db.commit()
    
    return # Returns 204 No Content

# --- Startup Event & Root Endpoint ---
@app.on_event("startup")
def on_startup():
    print("Creating database tables...")
    create_db_tables()
    print("Database ready.")
@app.get("/", summary="API Health Check")
def read_root():
    return {"status": "ok", "service": "SalesForge API"}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

