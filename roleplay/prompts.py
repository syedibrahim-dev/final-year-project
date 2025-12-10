"""
Prompt builder for AI roleplay conversations
Generates prompts for customer persona simulation
"""
from typing import List, Dict, Any
from models.roleplay import RoleplayPersona, RoleplayMessage
import json


def build_persona_system_prompt(persona: RoleplayPersona) -> str:
    """
    Build system prompt from persona configuration
    
    Args:
        persona: RoleplayPersona model instance
    
    Returns:
        System prompt string for LLM
    """
    
    # Natural, context-aware conversation prompt
    system_prompt = f"""You are a customer in a sales call with a salesperson.

SCENARIO: The salesperson scheduled this call with you. You have some interest in their product but haven't committed yet.

YOUR CHARACTER:
{persona.description}
Communication style: {persona.tone}

YOUR CONCERNS:
{", ".join(persona.common_objections[:3])}

HOW TO RESPOND:
- React naturally to what they ACTUALLY said
- Match the conversation stage (don't jump ahead)
- Greetings = casual small talk, NOT business talk yet
- Let the salesperson lead the conversation pace
- Keep responses conversational (2-4 sentences)
- Sound like a real person having a normal conversation
- NEVER say your name or explain your role

IMPORTANT - FOLLOW NATURAL FLOW:
- Opening greeting → Keep it casual, just acknowledge
- Salesperson introduces themselves → Polite acknowledgment
- Question about current situation → THEN share relevant info
- Product discussion → Ask questions or raise concerns
- Pricing → Negotiate based on your personality

GOOD NATURAL RESPONSES:
Opening: "Hey! I'm good, how are you?"
After intro: "Nice to meet you. What can I help you with today?"
When asked about needs: "Yeah, we're using a few different tools right now. They work okay but nothing special."
Pricing question: "Hmm, that's a bit more than I expected. What kind of results are we talking about?"
Objection: "I hear you, but we're pretty busy right now. How long does implementation usually take?"

BAD UNNATURAL RESPONSES:
"Hi! I've been looking into solutions for this." ❌ (Too eager on first greeting)
"Yeah, interested. What's the pricing?" ❌ (Skips entire conversation)
"Can I outline how our software..." ❌ (Wrong role!)

Respond naturally like a real person:"""
    
    return system_prompt


def format_conversation_history(messages: List[RoleplayMessage]) -> str:
    """
    Format message history for context
    
    Args:
        messages: List of RoleplayMessage instances
    
    Returns:
        Formatted conversation string
    """
    if not messages:
        return "No previous conversation."
    
    formatted = []
    for msg in messages:
        sender_label = "Salesperson" if msg.sender == "trainee" else "Customer"
        formatted.append(f"{sender_label}: {msg.message_text}")
    
    return "\n".join(formatted)


def build_customer_prompt(
    persona: RoleplayPersona,
    history: List[RoleplayMessage],
    trainee_message: str
) -> Dict[str, Any]:
    """
    Build complete prompt for customer response generation
    
    Args:
        persona: RoleplayPersona model instance
        history: List of previous messages
        trainee_message: Latest message from trainee
    
    Returns:
        Dict with system prompt, conversation history, and user message
    """
    
    system_prompt = build_persona_system_prompt(persona)
    
    # Format history for context
    history_text = ""
    if history:
        history_items = []
        for msg in history:
            sender = "Salesperson" if msg.sender == "trainee" else persona.name
            history_items.append(f"{sender}: {msg.message_text}")
        history_text = "\n".join(history_items)
    
    # Build user message with context
    if history_text:
        user_message = f"""Previous messages:
{history_text}

They just said: "{trainee_message}"

Your brief, natural response:"""
    else:
        user_message = f"""They said: "{trainee_message}"

Your brief, natural response:"""
    
    return {
        "system": system_prompt,
        "history": history_text,
        "user_message": user_message
    }
