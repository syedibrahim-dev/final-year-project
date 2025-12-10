"""
Simple test script for Phase 2: Conversation Engine
Tests prompt building and LLM response generation
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.database import SessionLocal
from models.roleplay import RoleplayPersona
from services.roleplay_service import create_session, generate_ai_response, get_conversation_history


def test_conversation():
    """Test creating a session and generating responses"""
    
    print("\n" + "="*60)
    print("TESTING ROLEPLAY CONVERSATION ENGINE")
    print("="*60 + "\n")
    
    db = SessionLocal()
    
    try:
        # Get a persona (The Friendly Prospect - easiest to test with)
        persona = db.query(RoleplayPersona).filter_by(name="The Friendly Prospect").first()
        
        if not persona:
            print("Error: 'The Friendly Prospect' persona not found")
            print("Please run seed_personas.py first")
            return
        
        print(f"+ Using persona: {persona.name}")
        print(f"  Difficulty: {persona.difficulty}")
        print(f"  Tone: {persona.tone}\n")
        
        # Create a test session (using dummy user ID and org ID)
        print("+ Creating session...")
        session = create_session(
            db=db,
            trainee_id=1,  # Assuming user ID 1 exists
            org_id=1,      # Assuming org ID 1 exists
            persona_id=persona.id
        )
        print(f"  Session ID: {session.id}")
        print(f"  Status: {session.status}\n")
        
        # Test conversation flow
        print("+ Starting conversation...\n")
        
        # Trainee's opening
        trainee_msg_1 = "Hi! My name is John and I'm calling from TechCorp. How are you doing today?"
        print(f"Trainee: {trainee_msg_1}")
        
        # Generate AI response
        print("Customer (AI): ", end="", flush=True)
        response_1 = generate_ai_response(db, session.id, trainee_msg_1)
        print(response_1["response"] + "\n")
        
        # Trainee's follow-up
        trainee_msg_2 = "I wanted to talk to you about our new project management software. Are you currently using any tools to manage your team's projects?"
        print(f"Trainee: {trainee_msg_2}")
        
        # Generate AI response
        print("Customer (AI): ", end="", flush=True)
        response_2 = generate_ai_response(db, session.id, trainee_msg_2)
        print(response_2["response"] + "\n")
        
        # Show conversation history
        print("="*60)
        print("CONVERSATION HISTORY")
        print("="*60 + "\n")
        
        history = get_conversation_history(db, session.id)
        for msg in history:
            sender = "Trainee" if msg.sender == "trainee" else f"Customer ({persona.name})"
            print(f"{sender}: {msg.message_text}\n")
        
        print(f"Total messages: {len(history)}")
        print("\n" + "="*60)
        print("TEST COMPLETED SUCCESSFULLY!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\nError during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    print("\nIMPORTANT: Make sure Ollama is running with llama3.1:8b!")
    print("If not, run: ollama run llama3.1:8b-instruct-q4_K_M\n")
    
    input("Press Enter to start the test...")
    test_conversation()
