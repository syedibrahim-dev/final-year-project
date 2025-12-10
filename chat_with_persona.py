"""
Interactive roleplay conversation - chat with AI customer personas
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.database import SessionLocal
from models.roleplay import RoleplayPersona
from services.roleplay_service import create_session, generate_ai_response, end_session, get_conversation_history


def interactive_chat():
    """Start an interactive chat session with a persona"""
    
    print("\n" + "="*60)
    print("INTERACTIVE ROLEPLAY CHAT")
    print("="*60 + "\n")
    
    db = SessionLocal()
    
    try:
        # List available personas
        personas = db.query(RoleplayPersona).filter_by(is_predefined=True).all()
        
        if not personas:
            print("Error: No personas found. Please run seed_personas.py first")
            return
        
        print("Available customer personas:\n")
        for i, persona in enumerate(personas, 1):
            print(f"{i}. {persona.name}")
            print(f"   {persona.description[:80]}...")
            print(f"   Difficulty: {persona.difficulty} | Tone: {persona.tone}\n")
        
        # Select persona
        while True:
            try:
                choice = input("Select persona (1-{}): ".format(len(personas)))
                choice_num = int(choice)
                if 1 <= choice_num <= len(personas):
                    selected_persona = personas[choice_num - 1]
                    break
                else:
                    print("Invalid choice. Try again.")
            except ValueError:
                print("Please enter a number.")
        
        print(f"\n{'='*60}")
        print(f"Starting conversation with: {selected_persona.name}")
        print(f"{'='*60}\n")
        
        # Create session
        session = create_session(
            db=db,
            trainee_id=1,  # Dummy ID
            org_id=1,      # Dummy ID
            persona_id=selected_persona.id
        )
        
        print("Conversation started! Type your messages below.")
        print("Commands: 'quit' to end, 'history' to see full transcript\n")
        
        # Chat loop
        message_count = 0
        while True:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Check for commands
            if user_input.lower() == 'quit':
                print("\nEnding session...")
                end_session(db, session.id)
                break
            
            if user_input.lower() == 'history':
                print("\n" + "="*60)
                print("CONVERSATION HISTORY")
                print("="*60 + "\n")
                history = get_conversation_history(db, session.id)
                for msg in history:
                    sender = "You" if msg.sender == "trainee" else f"{selected_persona.name}"
                    print(f"{sender}: {msg.message_text}\n")
                print("="*60 + "\n")
                continue
            
            # Generate AI response
            try:
                print(f"{selected_persona.name}: ", end="", flush=True)
                response = generate_ai_response(db, session.id, user_input)
                print(response["response"] + "\n")
                message_count += 2
                
                # Show progress
                if message_count % 10 == 0:
                    print(f"[{message_count} messages exchanged so far]\n")
                
            except Exception as e:
                print(f"\nError: {e}")
                print("Continuing conversation...\n")
        
        # Show final summary
        print("\n" + "="*60)
        print("SESSION SUMMARY")
        print("="*60)
        print(f"Total messages: {message_count}")
        print(f"Session ID: {session.id}")
        print(f"Status: {session.status}")
        print("="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Ending session...")
        if 'session' in locals():
            end_session(db, session.id)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    print("\nIMPORTANT: Make sure Ollama is running!")
    print("If not, run: ollama run llama3.1:8b-instruct-q4_K_M\n")
    
    input("Press Enter to start...")
    interactive_chat()
