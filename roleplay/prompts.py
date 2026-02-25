"""
Prompt builder for AI roleplay conversations
Generates prompts for customer persona simulation
Enhanced with document-grounded product knowledge via RAG
"""
from typing import List, Dict, Any, Optional
from models.roleplay import RoleplayPersona, RoleplayMessage
from services.rag_service import retrieve_relevant_chunks
import json
import logging

logger = logging.getLogger(__name__)


def retrieve_document_context(query: str, org_id: int, k: int = 3) -> str:
    """
    Retrieve relevant document chunks from ChromaDB for the given query.
    Used to ground AI customer conversations in real product knowledge.
    
    Args:
        query: The trainee's message or topic to search for
        org_id: Organization ID to scope document retrieval
        k: Number of chunks to retrieve
    
    Returns:
        Formatted document context string, or empty string if no docs found
    """
    try:
        chunks = retrieve_relevant_chunks(query=query, org_id=org_id, k=k)
        if not chunks:
            return ""
        
        # Combine chunk text, cap at 2000 chars to avoid prompt bloat
        context = "\n\n".join([chunk["chunk"] for chunk in chunks])[:2000]
        return context.strip()
    except Exception as e:
        logger.warning(f"Failed to retrieve document context for roleplay: {e}")
        return ""


# ===== Conversation Phase Detection =====

SALES_PHASES = {
    "opening": {"name": "Opening / Greeting", "msg_range": (0, 3)},
    "discovery": {"name": "Discovery / Needs Assessment", "msg_range": (3, 8)},
    "presentation": {"name": "Value Presentation", "msg_range": (8, 14)},
    "objection": {"name": "Objection Handling", "msg_range": (14, 20)},
    "closing": {"name": "Closing / Next Steps", "msg_range": (20, 999)},
}


def detect_conversation_phase(messages: list, persona_difficulty: str = "intermediate") -> str:
    """
    Detect current conversation phase based on message count and content signals.
    
    Returns: phase key string (opening, discovery, presentation, objection, closing)
    """
    msg_count = len(messages) if messages else 0
    
    # Adjust phase thresholds by difficulty (advanced = faster pace expected)
    pace_modifier = {"beginner": 1.3, "intermediate": 1.0, "advanced": 0.8}.get(persona_difficulty, 1.0)
    
    # Content-based signals from recent messages
    recent_text = " ".join(
        [m.message_text.lower() if hasattr(m, 'message_text') else m.get('text', '').lower()
         for m in (messages[-4:] if messages else [])]
    )
    
    # Check for closing signals
    closing_signals = ['next step', 'move forward', 'get started', 'schedule', 'demo', 'trial', 'sign up', 'follow up', 'deal', 'contract', 'agree']
    if any(s in recent_text for s in closing_signals) and msg_count > int(10 * pace_modifier):
        return "closing"
    
    # Check for objection signals
    objection_signals = ['too expensive', 'not sure', 'concern', 'worried', 'hesitant', 'competitor', "can't afford", 'budget', 'think about it', 'not ready']
    if any(s in recent_text for s in objection_signals) and msg_count > int(6 * pace_modifier):
        return "objection"
    
    # Check for presentation signals
    presentation_signals = ['feature', 'benefit', 'solution', 'product', 'service', 'offer', 'how it works', 'roi', 'value', 'save']
    if any(s in recent_text for s in presentation_signals) and msg_count > int(5 * pace_modifier):
        return "presentation"
    
    # Check for discovery signals
    discovery_signals = ['tell me', 'challenge', 'currently', 'pain', 'goal', 'process', 'situation', 'what do you', 'how do you']
    if any(s in recent_text for s in discovery_signals) and msg_count > int(2 * pace_modifier):
        return "discovery"
    
    # Default: message count based
    for phase_key, phase_info in SALES_PHASES.items():
        low = int(phase_info["msg_range"][0] * pace_modifier)
        high = int(phase_info["msg_range"][1] * pace_modifier)
        if low <= msg_count < high:
            return phase_key
    
    return "closing"


def _build_personality_instructions(persona: RoleplayPersona) -> str:
    """
    Convert personality_traits JSON into natural behavioral instructions.
    Maps traits like patience, price_sensitivity etc. to actual prompt behavior.
    """
    traits = persona.personality_traits or {}
    instructions = []
    
    # Patience
    patience = traits.get("patience", "medium")
    if patience == "low":
        instructions.append("You are IMPATIENT. If the salesperson rambles or doesn't get to the point quickly, express frustration. Say things like 'Can we get to the point?' or 'I don't have all day.'")
    elif patience == "high":
        instructions.append("You are PATIENT and willing to listen. Give the salesperson time to explain. Don't rush them.")
    
    # Price sensitivity
    price_sensitivity = traits.get("price_sensitivity", "medium")
    if price_sensitivity in ("high", "very_high"):
        instructions.append("You are VERY price-conscious. Always ask about cost early. Push back hard on pricing. Compare to cheaper alternatives. Say things like 'That's quite steep' or 'We've seen cheaper options.'")
    elif price_sensitivity == "low":
        instructions.append("Price is NOT your main concern. You care more about quality, reliability, and support. Don't bring up price unless they do first.")
    
    # Decision speed
    decision_speed = traits.get("decision_speed", "medium")
    if decision_speed == "slow":
        instructions.append("You are a SLOW decision-maker. You need to 'think about it', consult with your team, and see more proof before committing. Never agree on the first call.")
    elif decision_speed == "fast":
        instructions.append("You make decisions QUICKLY when convinced. If the salesperson presents a strong case, you're ready to move forward.")
    
    # Trust level
    trust_level = traits.get("trust_level", "medium")
    if trust_level == "low":
        instructions.append("You are SKEPTICAL of salespeople. Demand proof, case studies, references. Say things like 'That sounds too good to be true' or 'Do you have data to back that up?'")
    elif trust_level == "high":
        instructions.append("You are generally TRUSTING. If the salesperson seems knowledgeable and professional, you give them the benefit of the doubt.")
    
    return "\n".join(instructions) if instructions else "React naturally based on your character description."


def _build_difficulty_behavior(difficulty: str) -> str:
    """
    Generate difficulty-specific behavioral instructions.
    Beginner = forgiving, Advanced = challenging and resistant.
    """
    if difficulty == "beginner":
        return """DIFFICULTY BEHAVIOR (BEGINNER - Be forgiving):
- Be relatively easy to talk to and open to suggestions
- Ask straightforward questions, don't try to trap the salesperson
- If they make a small mistake, let it slide
- Show buying signals when they present value reasonably well
- Don't raise too many objections at once
- Be receptive to basic rapport-building efforts"""
    
    elif difficulty == "advanced":
        return """DIFFICULTY BEHAVIOR (ADVANCED - Be challenging):
- Be demanding and test the salesperson's expertise
- Ask tough follow-up questions that require deep knowledge
- Challenge vague claims: "Can you be more specific about those results?"
- Interrupt if they're reading from a script or being too generic
- Raise multiple objections and don't let them off easy
- Require concrete proof: numbers, case studies, references
- Compare them unfavorably to competitors
- Show skepticism even when they make good points
- Only show buying interest if they truly earn it"""
    
    else:  # intermediate
        return """DIFFICULTY BEHAVIOR (INTERMEDIATE):
- Be a realistic customer - sometimes receptive, sometimes skeptical
- Ask clarifying questions when claims seem vague
- Raise 1-2 genuine objections during the conversation
- Respond positively to good value propositions but don't commit easily
- Expect professional behavior and product knowledge"""


def _build_phase_instructions(phase: str, persona: RoleplayPersona) -> str:
    """Generate phase-specific behavioral instructions for the AI customer."""
    
    phase_guides = {
        "opening": f"""CURRENT PHASE: Opening / Greeting
- Keep it casual and brief. Just exchange pleasantries.
- Don't jump into business immediately.
- If asked "how are you?", respond naturally then wait for them to transition.
- A {"brief" if persona.tone == "formal" else "warm, friendly"} greeting is appropriate.""",
        
        "discovery": f"""CURRENT PHASE: Discovery / Needs Assessment
- The salesperson should be asking about your situation and needs.
- Share relevant information about your challenges when asked directly.
- Don't volunteer everything at once - make them earn the information with good questions.
- If they ask good open-ended questions, reward them with detailed answers.
- If they ask yes/no questions, give short answers and wait for better questions.
- Mention 1-2 of your concerns naturally: {', '.join(persona.common_objections[:2])}""",
        
        "presentation": f"""CURRENT PHASE: Value Presentation
- The salesperson should be presenting their solution now.
- Listen to their pitch and react to specific claims.
- Ask clarifying questions about features that matter to you.
- If they're being too generic, push for specifics: "How exactly would that help us?"
- Show moderate interest in strong points but don't be overly enthusiastic.""",
        
        "objection": f"""CURRENT PHASE: Objection Handling
- Raise your key concerns now: {', '.join(persona.common_objections[:3])}
- If the salesperson addresses a concern well, acknowledge it: "That makes sense" or "I hadn't thought of it that way."
- If they dismiss your concern or give a weak answer, push back harder.
- Don't make it easy - good objection handling should be earned.
- You can soften slightly if they show genuine empathy and provide evidence.""",
        
        "closing": f"""CURRENT PHASE: Closing / Next Steps
- The conversation should be wrapping up.
- If the salesperson has done well overall, be open to a next step (demo, trial, follow-up meeting).
- If they haven't addressed your concerns, express hesitation: "I need to think about it."
- Don't commit to a purchase on this call - at most agree to a next meeting or trial.
- A good close from them: suggesting a specific next step with a timeline."""
    }
    
    return phase_guides.get(phase, phase_guides["discovery"])


def build_persona_system_prompt(
    persona: RoleplayPersona,
    messages: list = None,
    document_context: str = ""
) -> str:
    """
    Build system prompt from persona configuration.
    Enhanced with: phase awareness, personality traits, difficulty behavior,
    and document-grounded product knowledge.
    
    Args:
        persona: RoleplayPersona model instance
        messages: Optional list of previous messages for phase detection
        document_context: Optional product/company context from uploaded documents
    
    Returns:
        System prompt string for LLM
    """
    
    # Detect current conversation phase
    phase = detect_conversation_phase(messages, persona.difficulty)
    
    # Build personality instructions from traits
    personality_instructions = _build_personality_instructions(persona)
    
    # Build difficulty behavior
    difficulty_behavior = _build_difficulty_behavior(persona.difficulty)
    
    # Build phase-specific instructions
    phase_instructions = _build_phase_instructions(phase, persona)
    
    # Build product knowledge section from documents (if available)
    product_knowledge_section = ""
    if document_context:
        product_knowledge_section = f"""\n\nPRODUCT KNOWLEDGE (from company training materials):
You are aware of the following product/service details. Use this knowledge to:
- Ask informed questions about specific features the salesperson mentions
- Challenge claims that contradict or misrepresent this information
- Bring up specific concerns related to pricing, implementation, or competitors mentioned below
- Test whether the salesperson truly knows their product

Reference Material:
{document_context}

IMPORTANT: Use this knowledge NATURALLY. Don't quote it directly. Instead, paraphrase as a real customer would:
- "I heard your competitor offers something similar for less..." 
- "Someone mentioned your implementation takes weeks — is that true?"
- "What exactly does the enterprise tier include that the basic one doesn't?"
"""
    
    system_prompt = f"""You are a customer in a sales call with a salesperson.

SCENARIO: The salesperson scheduled this call with you. You have some interest in their product but haven't committed yet.

YOUR CHARACTER:
{persona.description}
Communication style: {persona.tone}

YOUR PERSONALITY:
{personality_instructions}

YOUR CONCERNS (raise these naturally when appropriate):
{', '.join(persona.common_objections[:4])}

{difficulty_behavior}

{phase_instructions}{product_knowledge_section}

EMOTIONAL DYNAMICS:
- If the salesperson acknowledges your concerns thoughtfully → Soften slightly, become more receptive
- If they ignore or dismiss your concerns → Become more resistant and guarded
- If they provide specific evidence or data → Show genuine interest
- If they use generic sales talk → Show impatience or skepticism

HOW TO RESPOND:
- React naturally to what they ACTUALLY said
- Keep responses conversational (2-4 sentences)
- Sound like a real person having a normal conversation
- NEVER say your name, explain your role, or break character
- NEVER use phrases like "As a customer..." or "In my role..."
- Match the conversation stage - don't jump ahead or behind

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
    trainee_message: str,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Build complete prompt for customer response generation.
    Enhanced with phase-aware system prompt, windowed history,
    and document-grounded product knowledge.
    
    Args:
        persona: RoleplayPersona model instance
        history: List of previous messages
        trainee_message: Latest message from trainee
        org_id: Optional organization ID for document context retrieval
    
    Returns:
        Dict with system prompt, conversation history, and user message
    """
    
    # Retrieve document context using trainee's message as the query
    document_context = ""
    if org_id:
        document_context = retrieve_document_context(
            query=trainee_message,
            org_id=org_id,
            k=3
        )
        if document_context:
            logger.info(f"📄 Retrieved {len(document_context)} chars of document context for roleplay")
    
    # Pass history + document context to system prompt for phase detection
    system_prompt = build_persona_system_prompt(
        persona, messages=history, document_context=document_context
    )
    
    # Format history for context (window last 10 turns to avoid prompt bloat)
    history_text = ""
    if history:
        # Use last 10 messages for context window
        recent_history = history[-10:] if len(history) > 10 else history
        history_items = []
        for msg in recent_history:
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
