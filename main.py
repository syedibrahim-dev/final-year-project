# Python 3.14+ compatibility patch - MUST be first import
# Fixes pydantic.v1 PEP 649 deferred annotations issue (affects chromadb)
import compat_patch  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from datetime import datetime, timedelta
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
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
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
try:
    from routes import chatbot
    routes_to_import.append(("chatbot", chatbot))
    print("✅ Chatbot routes imported")
except ImportError as e:
    print(f"❌ Failed to import chatbot routes: {e}")
    traceback.print_exc()

# Roleplay routes
try:
    from routes import roleplay
    routes_to_import.append(("roleplay", roleplay))
    print("✅ Roleplay routes imported")
except ImportError as e:
    print(f"❌ Failed to import roleplay routes: {e}")
    traceback.print_exc()

# Marketing routes (Module 5b)
try:
    from routes import marketing
    routes_to_import.append(("marketing", marketing))
    print("✅ Marketing routes imported")
except ImportError as e:
    print(f"❌ Failed to import marketing routes: {e}")
    traceback.print_exc()

# Inventory routes (Module 5e)
try:
    from routes import inventory
    routes_to_import.append(("inventory", inventory))
    print("✅ Inventory routes imported")
except ImportError as e:
    print(f"❌ Failed to import inventory routes: {e}")
    traceback.print_exc()

# Analytics routes (Module 5f)
try:
    from routes import analytics
    routes_to_import.append(("analytics", analytics))
    print("✅ Analytics routes imported")
except ImportError as e:
    print(f"❌ Failed to import analytics routes: {e}")
    traceback.print_exc()

# Lead scoring routes (Module 5a)
try:
    from routes import leads
    routes_to_import.append(("leads", leads))
    print("✅ Lead scoring routes imported")
    # Pre-load the ML pipeline
    from services.lead_scoring_service import load_pipeline
    load_pipeline()
except ImportError as e:
    print(f"❌ Failed to import lead scoring routes: {e}")
    traceback.print_exc()

# Check if we have at least auth routes
if not any(name == "auth" for name, _ in routes_to_import):
    print("\n❌ CRITICAL: Auth routes failed to import!")
    print("❌ Cannot start server without authentication")
    sys.exit(1)

print(f"\n✅ Successfully imported {len(routes_to_import)} route modules")

# ── APScheduler: background jobs ────────────────────────────────────────────
#   1. publish_due_posts          — every 60 s, fires scheduled marketing posts
#   2. refresh_all_forecasts      — every 6 h, regenerates inventory forecasts
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from services.marketing_service import publish_due_posts
    from services.inventory_service import refresh_all_forecasts
    from utils.database import SessionLocal as _SessionLocal

    def _run_publish_job():
        db = _SessionLocal()
        try:
            publish_due_posts(db)
        except Exception as _e:
            print(f"⚠️  Scheduler publish job error: {_e}")
        finally:
            db.close()

    def _run_forecast_refresh_job():
        db = _SessionLocal()
        try:
            summary = refresh_all_forecasts(db)
            print(f"📊 Scheduled forecast refresh: {summary['products_succeeded']}/{summary['products_total']} succeeded")
        except Exception as _e:
            print(f"⚠️  Scheduler forecast refresh error: {_e}")
        finally:
            db.close()

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_publish_job,
        trigger="interval", seconds=60,
        id="publish_scheduled_posts",
    )
    _scheduler.add_job(
        _run_forecast_refresh_job,
        trigger="interval", hours=6,
        id="refresh_inventory_forecasts",
        next_run_time=datetime.now() + timedelta(minutes=5),  # delay first run by 5 min after startup
    )
    _scheduler.start()
    print("✅ APScheduler started")
    print("   • publish_due_posts        — every 60 s")
    print("   • refresh_all_forecasts    — every 6 h (first run in 5 min)")
except ImportError:
    print("⚠️  apscheduler not installed — scheduled jobs won't run.")
    print("   Run:  pip install apscheduler")
except Exception as _sched_err:
    print(f"⚠️  Could not start scheduler: {_sched_err}")
    import traceback
    traceback.print_exc()


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
        print("="*70)
        
        # Print all registered routes
        print("\n🔌 REGISTERED API ENDPOINTS:")
        print("="*70)
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                methods = ', '.join(route.methods)
                print(f"   {methods:10} {route.path}")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ STARTUP FAILED: {e}")
        traceback.print_exc()
        print("="*70 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shut down background services."""
    try:
        from services.conversion_service import get_conversion_service
        get_conversion_service().shutdown()
        print("✅ SalesRLAgent subprocess stopped")
    except Exception:
        pass


# Include routers that successfully imported
print("\n" + "="*70)
print("🔌 REGISTERING API ROUTES")
print("="*70)

# ✅ NO /api PREFIX - Keep existing behavior
for route_name, route_module in routes_to_import:
    try:
        app.include_router(route_module.router)  # ✅ NO PREFIX
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
            "auth": "/auth/*",
            "users": "/users/*",
            "organizations": "/orgs/*",
            "content": "/content/*",
            "mcq": "/mcq/*"
        }
    }

print("🎉 Application initialized successfully!")
print("🚀 Ready to accept requests\n")