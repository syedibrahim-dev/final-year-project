"""
Database migration to update RoleplayEvaluation model
Adds summary and nlp_metrics fields, renames metrics to category_scores
"""
from sqlalchemy import text
from utils.database import engine

def migrate():
    """Run migration to update roleplay_evaluations table"""
    
    with engine.connect() as conn:
        # Add new columns
        try:
            # Add summary column (TEXT)
            conn.execute(text("""
                ALTER TABLE roleplay_evaluations 
                ADD COLUMN summary TEXT NULL
            """))
            print("✅ Added 'summary' column")
        except Exception as e:
            print(f"⚠️ summary column may already exist: {e}")
        
        try:
            # Add nlp_metrics column (JSON)
            conn.execute(text("""
                ALTER TABLE roleplay_evaluations 
                ADD COLUMN nlp_metrics JSON NOT NULL DEFAULT ('{}')
            """))
            print("✅ Added 'nlp_metrics' column")
        except Exception as e:
            print(f"⚠️ nlp_metrics column may already exist: {e}")
        
        try:
            # Add category_scores column (JSON)
            conn.execute(text("""
                ALTER TABLE roleplay_evaluations 
                ADD COLUMN category_scores JSON NOT NULL DEFAULT ('{}')
            """))
            print("✅ Added 'category_scores' column")
        except Exception as e:
            print(f"⚠️ category_scores column may already exist: {e}")
        
        try:
            # Drop old metrics column if it exists
            conn.execute(text("""
                ALTER TABLE roleplay_evaluations 
                DROP COLUMN IF EXISTS metrics
            """))
            print("✅ Dropped old 'metrics' column")
        except Exception as e:
            print(f"⚠️ Error dropping metrics column: {e}")
        
        conn.commit()
        print("✅ Migration completed successfully!")

if __name__ == "__main__":
    print("Running roleplay evaluation migration...")
    migrate()
