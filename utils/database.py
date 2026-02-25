from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Generator
from config.settings import settings

# Create database engine with MySQL-specific settings
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # Test connections before using them
    pool_recycle=3600,       # Recycle connections after 1 hour
    pool_size=10,            # Base pool size (default was 5)
    max_overflow=20,         # Extra connections allowed (default was 10)
    pool_timeout=30,         # Timeout waiting for connection
    echo=False               # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()


def get_db() -> Generator:
    """
    Database session dependency for FastAPI
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db_tables():
    """
    Create all database tables defined in models
    This uses SQLAlchemy's metadata to create tables
    """
    print("📦 Creating database tables...")
    
    # Import all models so they are registered with Base.metadata
    try:
        from models.user import User
        from models.organization import Organization
        from models.training_content import TrainingContent
        from models.mcq import MCQTest, MCQAttempt
        from models.roleplay import RoleplayPersona, RoleplaySession, RoleplayMessage, RoleplayEvaluation
        
        print("✅ Models imported successfully")
    except ImportError as e:
        print(f"⚠️  Warning: Some models failed to import: {e}")
        import traceback
        traceback.print_exc()
    
    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        raise


def init_db():
    """
    Initialize database - create tables and optionally seed data
    This is the main function called on app startup
    """
    print("\n" + "="*60)
    print("🗄️  DATABASE INITIALIZATION")
    print("="*60)
    
    # Hide password in URL for logging
    display_url = settings.DATABASE_URL
    if "@" in display_url:
        parts = display_url.split("@")
        before_at = parts[0].split("://")
        if len(before_at) > 1 and ":" in before_at[1]:
            username = before_at[1].split(":")[0]
            display_url = f"{before_at[0]}://{username}:****@{parts[1]}"
    
    print(f"📍 Database: {display_url}")
    
    try:
        # Test database connection using text()
        print("🔌 Testing database connection...")
        db = SessionLocal()
        try:
            # Use text() for raw SQL - required in SQLAlchemy 2.0+
            result = db.execute(text("SELECT 1"))
            result.fetchone()
            print("✅ Database connection successful")
        except Exception as conn_error:
            print(f"❌ Database connection failed: {conn_error}")
            raise
        finally:
            db.close()
        
        # Create tables
        create_db_tables()
        
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        print("="*60 + "\n")
        raise


def drop_all_tables():
    """
    Drop all database tables
    WARNING: This will delete all data!
    Use only for development/testing
    """
    print("⚠️  WARNING: Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    print("✅ All tables dropped")


def reset_database():
    """
    Reset database - drop and recreate all tables
    WARNING: This will delete all data!
    Use only for development/testing
    """
    print("\n" + "="*60)
    print("🔄 DATABASE RESET")
    print("="*60)
    print("⚠️  WARNING: This will delete all data!")
    
    try:
        # Drop all tables
        drop_all_tables()
        
        # Recreate tables
        create_db_tables()
        
        print("✅ Database reset complete")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        import traceback
        traceback.print_exc()
        print("="*60 + "\n")
        raise


def test_connection():
    """Test database connection and print info"""
    print("\n" + "="*60)
    print("🔍 DATABASE CONNECTION TEST")
    print("="*60)
    
    try:
        db = SessionLocal()
        
        # Test connection
        result = db.execute(text("SELECT 1 as test"))
        print("✅ Connection: OK")
        
        # Get MySQL version
        try:
            version = db.execute(text("SELECT VERSION() as version"))
            version_str = version.fetchone()[0]
            print(f"📦 MySQL Version: {version_str}")
        except:
            print("📦 Database: Connected")
        
        # Get current database
        try:
            dbname = db.execute(text("SELECT DATABASE() as dbname"))
            db_str = dbname.fetchone()[0]
            print(f"📁 Database Name: {db_str}")
        except:
            pass
        
        # List tables
        try:
            tables = db.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                ORDER BY table_name
            """))
            table_list = [row[0] for row in tables.fetchall()]
            
            if table_list:
                print(f"📋 Tables ({len(table_list)}):")
                for table in table_list:
                    print(f"   - {table}")
            else:
                print("📋 Tables: None (database is empty)")
        except Exception as e:
            print(f"⚠️  Could not list tables: {e}")
        
        db.close()
        print("="*60 + "\n")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        print("="*60 + "\n")
        return False


# For backwards compatibility
create_tables = create_db_tables