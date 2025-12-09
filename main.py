from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import sys
import traceback

# Initialize FastAPI app first
app = FastAPI(
    title="Sales Training AI Platform",
    description="AI-powered training content and assessment platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000", 
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("\n" + "="*70)
print("🚀 INITIALIZING SALES TRAINING AI PLATFORM")
print("="*70)

# Import database utilities
try:
    from utils.database import init_db
    print("✅ Database utilities imported")
except ImportError as e:
    print(f"❌ Failed to import database utilities: {e}")
    traceback.print_exc()
    sys.exit(1)

# Import routes one by one with error handling
routes_to_import = []

# Auth routes
try:
    from routes import auth
    routes_to_import.append(("auth", auth))
    print("✅ Auth routes imported")
except ImportError as e:
    print(f"❌ Failed to import auth routes: {e}")
    traceback.print_exc()

# User routes
try:
    from routes import user
    routes_to_import.append(("user", user))
    print("✅ User routes imported")
except ImportError as e:
    print(f"❌ Failed to import user routes: {e}")
    traceback.print_exc()

# Organization routes
try:
    from routes import organization
    routes_to_import.append(("organization", organization))
    print("✅ Organization routes imported")
except ImportError as e:
    print(f"❌ Failed to import organization routes: {e}")
    traceback.print_exc()

# Content routes
try:
    from routes import content
    routes_to_import.append(("content", content))
    print("✅ Content routes imported")
except ImportError as e:
    print(f"❌ Failed to import content routes: {e}")
    traceback.print_exc()

# MCQ routes
try:
    from routes import mcq
    routes_to_import.append(("mcq", mcq))
    print("✅ MCQ routes imported")
except ImportError as e:
    print(f"❌ Failed to import mcq routes: {e}")
    traceback.print_exc()

# Check if we have at least auth routes
if not any(name == "auth" for name, _ in routes_to_import):
    print("\n❌ CRITICAL: Auth routes failed to import!")
    print("❌ Cannot start server without authentication")
    sys.exit(1)

print(f"\n✅ Successfully imported {len(routes_to_import)} route modules")

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    print("\n" + "="*70)
    print("🔧 STARTUP SEQUENCE")
    print("="*70)
    
    try:
        # Initialize database
        print("📦 Initializing database...")
        init_db()
        print("✅ Database initialized successfully")
        
        # Check if temp directories exist
        from pathlib import Path
        
        base_dir = Path(__file__).parent
        temp_dir = base_dir / "temp"
        chroma_dir = base_dir / "chroma_db"
        logs_dir = base_dir / "logs"
        
        # Create directories
        for directory in [temp_dir, chroma_dir, logs_dir]:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                print(f"✅ Directory ready: {directory.name}/")
            except Exception as dir_error:
                print(f"⚠️  Could not create {directory.name}/: {dir_error}")
        
        # Check LLM availability (optional - won't fail startup)
        try:
            import requests
            llm_url = "http://localhost:11434/api/tags"
            response = requests.get(llm_url, timeout=3)
            if response.status_code == 200:
                print("✅ Ollama LLM service is available")
            else:
                print("⚠️  Ollama LLM service responded with error")
        except Exception as e:
            print("⚠️  Ollama LLM service not available (MCQ generation will fail)")
        
        print("\n✅ All systems ready")
        print("="*70)
        print("📡 API Documentation: http://localhost:8000/docs")
        print("📡 Alternative Docs: http://localhost:8000/redoc")
        print("💚 Health Check: http://localhost:8000/health")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ STARTUP FAILED: {e}")
        traceback.print_exc()
        print("="*70 + "\n")
        # Don't exit - let FastAPI handle it

# Include routers that successfully imported
print("\n" + "="*70)
print("🔌 REGISTERING API ROUTES")
print("="*70)

for route_name, route_module in routes_to_import:
    try:
        app.include_router(route_module.router)
        print(f"✅ Registered: {route_name} routes")
    except Exception as e:
        print(f"❌ Failed to register {route_name} routes: {e}")
        traceback.print_exc()

print("="*70 + "\n")

# Root endpoint
@app.get("/", tags=["Root"])
def read_root():
    """API root endpoint"""
    return {
        "message": "Sales Training AI Platform API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }

# Health check endpoint
@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint"""
    
    health_status = {
        "status": "healthy",
        "message": "Server is running",
        "version": "1.0.0"
    }
    
    # Check database connection
    try:
        from utils.database import get_db
        db = next(get_db())
        # ✅ FIXED: Use text() for raw SQL in SQLAlchemy 2.0+
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        health_status["database"] = "connected"
        db.close()
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check LLM availability
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        health_status["llm"] = "available" if response.ok else "unavailable"
    except:
        health_status["llm"] = "unavailable"
    
    # Check directories
    from pathlib import Path
    base_dir = Path(__file__).parent
    health_status["temp_dir"] = (base_dir / "temp").exists()
    health_status["chroma_dir"] = (base_dir / "chroma_db").exists()
    
    return health_status

# API info endpoint
@app.get("/info", tags=["Root"])
def api_info():
    """Get API information"""
    return {
        "title": "Sales Training AI Platform",
        "version": "1.0.0",
        "description": "AI-powered training content and assessment platform",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "auth": "/auth",
            "users": "/users",
            "organizations": "/orgs",
            "content": "/orgs/{org_id}/content",
            "mcq": "/orgs/{org_id}/mcq"
        }
    }

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    print(f"\n❌ UNHANDLED EXCEPTION:")
    print(f"   Path: {request.url.path}")
    print(f"   Method: {request.method}")
    print(f"   Error: {str(exc)}")
    traceback.print_exc()
    
    return {
        "error": "Internal server error",
        "message": str(exc),
        "path": str(request.url.path)
    }

print("🎉 Application initialized successfully!")
print("🚀 Ready to accept requests\n")