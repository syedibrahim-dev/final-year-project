"""
Prompt builder for AI roleplay conversations
Generates prompts for customer persona simulation
Enhanced with:
  - Document-grounded product knowledge via RAG (style-aware probing)
  - Scenario brief injection ("Who you are in this call")
  - Trigger topics (hot-button reactions)
  - Fixed personality trait handling (all traits now have prompt effects)
  - Phase-aware conversation guidance
"""
from typing import List, Dict, Any, Optional
from models.roleplay import RoleplayPersona, RoleplayMessage
from services.rag_service import retrieve_relevant_chunks
import json
import logging

logger = logging.getLogger(__name__)


# ===== Document Context Retrieval =====

def retrieve_document_context(query: str, org_id: int, k: int = 4,
                              conversation_history: list = None) -> str:
    """
    Retrieve relevant document chunks using multi-query RAG.

    Instead of searching only the latest trainee message, builds a composite
    query from:
      1. The trainee's latest message (what they just said)
      2. Key topics from recent conversation history (what's being discussed)
    This ensures retrieval stays relevant to the conversation topic even when
    the latest message is generic ("sounds good", "let me think about it").

    Args:
        query: The trainee's latest message
        org_id: Organization ID for scoping
        k: Number of chunks to retrieve
        conversation_history: List of message objects (optional, improves retrieval)

    Returns:
        Formatted document context string, or empty string if no docs found
    """
    try:
        # Build a composite query from the conversation, not just the last message
        composite_query = query
        if conversation_history and len(conversation_history) >= 2:
            # Extract the last 3 exchanges (6 messages) to capture the topic
            recent = conversation_history[-6:]
            topic_parts = []
            for m in recent:
                text = m.message_text if hasattr(m, "message_text") else (
                    m.get("text", "") if isinstance(m, dict) else "")
                if text:
                    topic_parts.append(text)
            # Combine: recent conversation summary + latest message (weighted by position)
            if topic_parts:
                composite_query = " ".join(topic_parts[-3:]) + " " + query

        chunks = retrieve_relevant_chunks(query=composite_query, org_id=org_id, k=k)
        if not chunks:
            return ""

        # Format with source tags so the persona knows what's a fact vs context
        formatted_parts = []
        for chunk in chunks:
            score = chunk.get("score", 0)
            text = chunk.get("chunk", "").strip()
            if score >= 0.5:
                formatted_parts.append(f"[VERIFIED FACT] {text}")
            elif score >= 0.2:
                formatted_parts.append(f"[PRODUCT INFO] {text}")
            else:
                formatted_parts.append(text)

        context = "\n\n".join(formatted_parts)[:2500]
        return context.strip()
    except Exception as e:
        logger.warning(f"Failed to retrieve document context for roleplay: {e}")
        return ""


# ===== Conversation Phase Detection =====

SALES_PHASES = {
    "opening":      {"name": "Opening / Greeting",           "msg_range": (0, 3)},
    "discovery":    {"name": "Discovery / Needs Assessment",  "msg_range": (3, 8)},
    "presentation": {"name": "Value Presentation",            "msg_range": (8, 14)},
    "objection":    {"name": "Objection Handling",            "msg_range": (14, 20)},
    "closing":      {"name": "Closing / Next Steps",          "msg_range": (20, 999)},
}


def detect_conversation_phase(messages: list, persona_difficulty: str = "intermediate") -> str:
    """
    Detect current conversation phase based on message count and content signals.

    Returns: phase key string (opening, discovery, presentation, objection, closing)
    """
    msg_count = len(messages) if messages else 0

    # Adjust phase thresholds by difficulty
    pace_modifier = {"beginner": 1.3, "intermediate": 1.0, "advanced": 0.8}.get(persona_difficulty, 1.0)

    # Content-based signals from recent messages
    recent_text = " ".join(
        [m.message_text.lower() if hasattr(m, 'message_text') else m.get('text', '').lower()
         for m in (messages[-4:] if messages else [])]
    )

    closing_signals = ['next step', 'move forward', 'get started', 'schedule', 'demo', 'trial', 'sign up', 'follow up', 'deal', 'contract', 'agree']
    if any(s in recent_text for s in closing_signals) and msg_count > int(10 * pace_modifier):
        return "closing"

    objection_signals = ['too expensive', 'not sure', 'concern', 'worried', 'hesitant', 'competitor', "can't afford", 'budget', 'think about it', 'not ready', 'switching', 'current vendor']
    if any(s in recent_text for s in objection_signals) and msg_count > int(6 * pace_modifier):
        return "objection"

    presentation_signals = ['feature', 'benefit', 'solution', 'product', 'service', 'offer', 'how it works', 'roi', 'value', 'save', 'result', 'outcome']
    if any(s in recent_text for s in presentation_signals) and msg_count > int(5 * pace_modifier):
        return "presentation"

    discovery_signals = ['tell me', 'challenge', 'currently', 'pain', 'goal', 'process', 'situation', 'what do you', 'how do you', 'walk me through']
    if any(s in recent_text for s in discovery_signals) and msg_count > int(2 * pace_modifier):
        return "discovery"

    for phase_key, phase_info in SALES_PHASES.items():
        low = int(phase_info["msg_range"][0] * pace_modifier)
        high = int(phase_info["msg_range"][1] * pace_modifier)
        if low <= msg_count < high:
            return phase_key

    return "closing"


# ===== Personality Trait Instructions =====

def _build_personality_instructions(persona: RoleplayPersona) -> str:
    """
    Convert personality_traits JSON into natural behavioral instructions.
    All defined traits now produce prompt effects.
    """
    traits = persona.personality_traits or {}
    instructions = []

    # --- Patience ---
    patience = traits.get("patience", "medium")
    if patience == "very_low":
        instructions.append(
            "You are EXTREMELY IMPATIENT. You have almost no tolerance for long explanations or filler. "
            "Cut the rep off mid-sentence if they ramble. Say things like 'Can we speed this up?' or 'I've got three minutes — get to the point.'"
        )
    elif patience == "low":
        instructions.append(
            "You are IMPATIENT. If the salesperson rambles or doesn't get to the point quickly, express frustration. "
            "Say things like 'Can we get to the point?' or 'I don't have all day.'"
        )
    elif patience == "high":
        instructions.append(
            "You are PATIENT and willing to listen carefully. Give the salesperson time to explain. "
            "You ask thoughtful follow-up questions rather than rushing them."
        )

    # --- Price Sensitivity ---
    price_sensitivity = traits.get("price_sensitivity", "medium")
    if price_sensitivity == "very_high":
        instructions.append(
            "You are EXTREMELY price-conscious. Bring up cost early. Push back hard on pricing. "
            "Ask about hidden fees, total cost of ownership, and discounts. "
            "Compare to cheaper alternatives: 'That seems steep — what justifies that price?'"
        )
    elif price_sensitivity == "high":
        instructions.append(
            "You are price-sensitive. Always ask about cost before committing to anything. "
            "Push back if pricing seems high: 'That's a bit more than I expected.'"
        )
    elif price_sensitivity == "low":
        instructions.append(
            "Price is NOT your main concern. You care more about quality, reliability, and outcomes. "
            "Don't bring up price unless they do first."
        )

    # --- Decision Speed ---
    decision_speed = traits.get("decision_speed", "medium")
    if decision_speed == "very_slow":
        instructions.append(
            "You NEVER make decisions on one call. You always need to 'loop in the team', 'get sign-off from the CFO', "
            "or 'see it in writing first'. Even if impressed, say: 'This sounds promising — but I couldn't commit without "
            "going through our full evaluation process. That usually takes 4-6 weeks.'"
        )
    elif decision_speed == "slow":
        instructions.append(
            "You are a SLOW decision-maker. You need to 'think about it', consult your team, and see more proof before committing. "
            "Never agree on the first call."
        )
    elif decision_speed == "fast":
        instructions.append(
            "You make decisions QUICKLY when convinced. If the salesperson presents a strong, specific case, "
            "you're ready to discuss next steps in the same call."
        )

    # --- Trust Level ---
    trust_level = traits.get("trust_level", "medium")
    if trust_level == "very_low":
        instructions.append(
            "You are DEEPLY SKEPTICAL of salespeople. You assume they exaggerate and cherry-pick data. "
            "Demand documented proof, independent case studies, and verifiable references. "
            "Push back on every claim: 'Do you have documented evidence of that, or is that just a marketing number?'"
        )
    elif trust_level == "low":
        instructions.append(
            "You are SKEPTICAL. Demand proof, case studies, and references. "
            "Say things like 'That sounds too good to be true — what's the catch?'"
        )
    elif trust_level == "high":
        instructions.append(
            "You are generally TRUSTING. If the salesperson seems knowledgeable and professional, "
            "you give them the benefit of the doubt and engage openly."
        )

    # --- Tech Savviness ---
    tech_savviness = traits.get("tech_savviness", "medium")
    if tech_savviness == "low":
        instructions.append(
            "You are NOT technical. When the rep uses jargon, acronyms, or technical terms without explaining them, "
            "you get confused and slightly anxious: 'Sorry — can you explain that in plain language? "
            "I don't have an IT background.'"
        )
    elif tech_savviness == "high":
        instructions.append(
            "You ARE technical. You appreciate precise language and ask detailed questions about architecture, "
            "integrations, security, and performance. Vague technical claims annoy you."
        )

    return "\n".join(instructions) if instructions else "React naturally and realistically based on your character description."


# ===== Difficulty Behavior =====

def _build_difficulty_behavior(difficulty: str) -> str:
    """
    Generate difficulty-specific behavioral instructions.
    """
    if difficulty == "beginner":
        return """DIFFICULTY BEHAVIOR (BEGINNER — Be approachable):
- Be relatively easy to talk to and open to suggestions
- Ask straightforward questions, don't try to trap the salesperson
- If they make a small mistake, let it slide — you're not trying to catch them out
- Show genuine interest when they present value clearly
- Don't raise more than one objection at a time
- Be receptive to basic rapport-building and empathetic responses"""

    elif difficulty == "advanced":
        return """DIFFICULTY BEHAVIOR (ADVANCED — Be genuinely challenging):
- Be demanding and test the salesperson's depth of knowledge
- Ask tough follow-up questions that require real expertise: "How exactly does that work under the hood?"
- Challenge vague claims immediately: "Can you be more specific? That's a big number to just state without context."
- If they're clearly reading from a script, call it out: "This feels rehearsed. Talk to me like a real person."
- Raise multiple objections across the conversation — don't let them off easy on any single one
- Require concrete proof: specific numbers, real case studies, verifiable claims
- Show skepticism even when they make good points — you've been impressed before and it didn't pan out
- Only begin to soften if they provide genuinely specific, credible evidence"""

    else:  # intermediate
        return """DIFFICULTY BEHAVIOR (INTERMEDIATE — Be realistic):
- Act like a real, busy professional — sometimes receptive, sometimes skeptical
- Ask clarifying questions when claims seem vague or generic
- Raise 1-2 genuine objections during the conversation that they need to address properly
- Respond positively to good, specific value propositions — but don't commit easily
- Expect professional, knowledgeable behaviour from the rep"""


# ===== Phase Instructions =====

def _build_phase_instructions(phase: str, persona: RoleplayPersona) -> str:
    """Generate phase-specific behavioral instructions for the AI customer."""

    objections_preview = ', '.join(persona.common_objections[:2]) if persona.common_objections else "general concerns"

    phase_guides = {
        "opening": f"""CURRENT PHASE: Opening / Greeting
- Keep it brief and casual. Just exchange pleasantries.
- Don't jump into business yet — let them lead the transition.
- A {("formal" if persona.tone == "formal" else "warm, friendly")} greeting is appropriate.
- If asked "how are you?", respond naturally then wait for them to lead.""",

        "discovery": f"""CURRENT PHASE: Discovery / Needs Assessment
- The rep should be asking about your situation and needs.
- Share relevant information when asked directly — but don't volunteer everything at once.
- If they ask good open-ended questions, reward them with detailed, specific answers.
- If they ask yes/no questions, give short answers and wait for better questions.
- Naturally let slip 1-2 of your concerns: {objections_preview}""",

        "presentation": f"""CURRENT PHASE: Value Presentation
- The rep should be presenting their solution. Listen and react to what they actually say.
- If they're being vague or generic, push for specifics: "How exactly would that work for us?"
- If they make a specific, credible claim, show moderate genuine interest.
- If they use buzzwords without substance, show impatience or mild skepticism.""",

        "objection": f"""CURRENT PHASE: Objection Handling
- Now is when your key concerns come out. Raise them clearly: {', '.join(persona.common_objections[:3]) if persona.common_objections else "your main concerns"}
- If the rep addresses a concern thoughtfully with evidence, acknowledge it: "That makes sense, actually."
- If they dismiss your concern or give a weak, generic answer, push back harder.
- Don't make it easy — good objection handling should be earned by specific, credible responses.""",

        "closing": f"""CURRENT PHASE: Closing / Next Steps
- The conversation should be wrapping up.
- If the rep has performed well overall, be open to a concrete next step (a follow-up meeting, a trial, a proposal).
- If they haven't addressed your concerns well, express appropriate hesitation.
- Don't commit to a purchase on this call — at most agree to a specific, scheduled next step."""
    }

    return phase_guides.get(phase, phase_guides["discovery"])


# ===== Company Context Section =====

def _build_company_context_section(persona) -> str:
    """
    Build a company intelligence section from persona.company_context.
    Gives the AI customer a realistic business background to reference naturally.
    """
    ctx = getattr(persona, 'company_context', None) or {}
    if not ctx:
        return ""

    lines = ["YOUR COMPANY BACKGROUND (reference this naturally — don't recite it):"]

    if ctx.get("industry"):
        lines.append(f"- Industry: {ctx['industry']}")
    if ctx.get("company_size"):
        lines.append(f"- Company size: {ctx['company_size']}")
    if ctx.get("role"):
        lines.append(f"- Your role: {ctx['role']}")
    if ctx.get("tech_stack"):
        stack = ", ".join(ctx["tech_stack"]) if isinstance(ctx["tech_stack"], list) else ctx["tech_stack"]
        lines.append(f"- Current tech stack: {stack}")
    if ctx.get("business_problems"):
        problems = ctx["business_problems"]
        if isinstance(problems, list):
            lines.append(f"- Key problems you're facing: {'; '.join(problems)}")
        else:
            lines.append(f"- Key problem: {problems}")
    if ctx.get("buying_stage"):
        lines.append(f"- Where you are in the buying process: {ctx['buying_stage']}")
    if ctx.get("budget_authority"):
        lines.append(f"- Your budget authority: {ctx['budget_authority']}")
    if ctx.get("current_solution"):
        lines.append(f"- What you currently use: {ctx['current_solution']}")
    if ctx.get("urgency"):
        lines.append(f"- How urgent this is: {ctx['urgency']}")

    lines.append("")
    lines.append("USE THIS NATURALLY: mention your company size, tech stack, or business problems")
    lines.append("when relevant — as a real customer would. Don't dump it all at once.")

    return "\n".join(lines)


# ===== Trigger Topics Section =====

def _build_trigger_topics_section(persona: RoleplayPersona) -> str:
    """
    Inject persona-specific trigger topics so the AI knows exactly when to react strongly.
    These are hot-button topics that cause a specific, strong response from this persona.
    """
    trigger_topics = getattr(persona, 'trigger_topics', None) or {}
    if not trigger_topics:
        return ""

    lines = ["HOW TO REACT TO SPECIFIC TOPICS (trigger strong reactions when these come up):"]
    for topic_key, reaction in trigger_topics.items():
        lines.append(f"- If {topic_key.replace('_', ' ')} comes up: {reaction}")

    return "\n".join(lines)


# ===== Smarter RAG Document Context =====

def _build_rag_section(document_context: str, rag_probing_style: str) -> str:
    """
    Build the document knowledge section with style-aware instructions.

    Instead of dumping all context as generic reference material, each
    rag_probing_style teaches the AI HOW to deploy that knowledge naturally.

    Styles:
    - challenge: Use doc facts to catch rep in inconsistencies or knowledge gaps
    - curious:   Ask genuine questions about things mentioned in the docs
    - gotcha:    Probe edge cases and weaknesses the docs hint at but don't fully address
    """
    if not document_context:
        return ""

    style_instructions = {
        "challenge": """HOW TO USE THIS KNOWLEDGE — CHALLENGE STYLE:
You've done your research. Use this information to actively TEST the rep's knowledge of their own product.
- If the rep says something that contradicts or oversimplifies what's in the material, catch them: 
  "That's interesting — what I read suggests it takes longer than that. Which is accurate?"
- If they make a claim the documents don't back up, demand evidence:
  "You just said X — I don't see anything about that in the materials I reviewed. Where does that come from?"
- Only raise 1-2 specific document-based challenges — make them count, don't interrogate.""",

        "curious": """HOW TO USE THIS KNOWLEDGE — CURIOUS STYLE:
You've seen or heard something about this product before (perhaps a brochure, a referral, or online). 
Ask genuine questions about things that caught your attention.
- Pick out 1-2 specific things from the material that interest you and ask them to explain more:
  "I heard something about [specific feature/claim] — can you walk me through how that actually works?"
- React authentically when they explain: show genuine interest or ask a follow-up if something is unclear.
- Don't pretend to know everything — you're curious, not an expert.""",

        "gotcha": """HOW TO USE THIS KNOWLEDGE — GOTCHA STYLE:
You've reviewed their materials and you've specifically been looking for the gaps and edge cases.
- Pick out a detail that seems incomplete in the docs and probe it:
  "Your materials mention [thing], but they're vague about [edge case]. What happens in that scenario?"
- Look for anything that seems like a weakness: limited coverage, vague timelines, missing details.
- Ask about what's NOT in the docs: "I noticed your documentation doesn't address [X]. Why is that?"
- Keep your tone professional but pointed — you're not being hostile, you're being thorough."""
    }

    style_text = style_instructions.get(rag_probing_style, style_instructions["curious"])

    return f"""
PRODUCT/COMPANY KNOWLEDGE (from company training materials):
The following information comes from the company's own documentation.
Items tagged [VERIFIED FACT] are high-confidence matches — treat these as things you've read or heard.
Items tagged [PRODUCT INFO] are related context — treat these as vague awareness.

{style_text}

--- BEGIN DOCUMENT CONTENT ---
{document_context}
--- END DOCUMENT CONTENT ---

HOW TO USE THIS:
- Pick 1-2 specific facts from the material above per conversation turn
- For [VERIFIED FACT] items: reference confidently — "I read that your renewal rate is 99.7%..."
- For [PRODUCT INFO] items: reference vaguely — "I think I saw something about that..."
- If the rep claims something NOT in the material above, challenge it: "Where does that come from?"
- If the rep claims something that IS in the material, acknowledge but probe deeper
- Do NOT dump multiple facts at once — deploy them one at a time across the conversation
- Do NOT quote the document verbatim — paraphrase as a real customer would
"""


# ===== Main System Prompt Builder =====

def build_persona_system_prompt(
    persona: RoleplayPersona,
    messages: list = None,
    document_context: str = ""
) -> str:
    """
    Build system prompt from persona configuration.
    Enhanced with: scenario brief, trigger topics, phase awareness,
    all personality traits, difficulty behavior, and smart RAG probing.

    Args:
        persona: RoleplayPersona model instance
        messages: Optional list of previous messages for phase detection
        document_context: Optional product/company context from uploaded documents

    Returns:
        System prompt string for LLM
    """

    # Detect current conversation phase
    phase = detect_conversation_phase(messages, persona.difficulty)

    # Build all instruction sections
    personality_instructions = _build_personality_instructions(persona)
    difficulty_behavior = _build_difficulty_behavior(persona.difficulty)
    phase_instructions = _build_phase_instructions(phase, persona)

    # Get rag_probing_style from personality_traits (stored there for DB compatibility)
    traits = persona.personality_traits or {}
    rag_probing_style = traits.get("rag_probing_style", "curious")

    # Build RAG section with style-aware instructions
    rag_section = _build_rag_section(document_context, rag_probing_style)

    # Build trigger topics section
    trigger_section = _build_trigger_topics_section(persona)

    # Get scenario brief (the "who you are" intro for this specific call)
    scenario_brief = getattr(persona, 'scenario_brief', None) or (
        "You are a potential customer evaluating a product or service. "
        "You have some interest but haven't committed to anything yet."
    )

    system_prompt = f"""You are playing the role of a customer in a sales call.

WHO YOU ARE IN THIS CALL:
{scenario_brief}

YOUR CHARACTER:
{persona.description}
Communication style: {persona.tone}

YOUR PERSONALITY TRAITS (follow these closely throughout the conversation):
{personality_instructions}

YOUR CONCERNS (raise these naturally as the conversation progresses):
{chr(10).join(f'- {obj}' for obj in persona.common_objections[:4])}

{trigger_section}

{difficulty_behavior}

{phase_instructions}{rag_section}

EMOTIONAL DYNAMICS — respond dynamically to how the rep behaves:
- If they acknowledge your concerns with specific evidence → Soften slightly, become more receptive
- If they ignore or dismiss your concerns → Become more guarded and resistant
- If they provide concrete, verifiable data → Show genuine interest
- If they use generic sales talk or buzzwords → Show skepticism or mild impatience
- If they ask a really good question about your situation → Reward them with a detailed, honest answer

RESPONSE RULES:
- React to what they ACTUALLY said — never give a pre-scripted answer
- Keep responses conversational and brief (2-4 sentences max)
- Sound like a real professional having a normal business conversation
- NEVER say your name, describe your role, or break character
- NEVER use phrases like "As a customer..." or "In my role as..."
- Match the conversation phase — don't jump ahead or lag behind
- If you don't know an answer (e.g. about their product), ask — you're the customer, not the expert

Respond naturally as this person would:"""

    return system_prompt


# ===== Conversation History Formatter =====

def format_conversation_history(messages: List[RoleplayMessage]) -> str:
    """Format message history for context"""
    if not messages:
        return "No previous conversation."

    formatted = []
    for msg in messages:
        sender_label = "Salesperson" if msg.sender == "trainee" else "Customer"
        formatted.append(f"{sender_label}: {msg.message_text}")

    return "\n".join(formatted)


# ===== Full Customer Prompt Builder =====

def build_customer_prompt(
    persona: RoleplayPersona,
    history: List[RoleplayMessage],
    trainee_message: str,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Build complete prompt for customer response generation.
    Enhanced with phase-aware system prompt, windowed history,
    and style-aware document-grounded product knowledge.

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
            k=4
        )
        if document_context:
            logger.info(f"📄 Retrieved {len(document_context)} chars of document context for roleplay (style: {(persona.personality_traits or {}).get('rag_probing_style', 'curious')})")

    # Build system prompt with all context
    system_prompt = build_persona_system_prompt(
        persona, messages=history, document_context=document_context
    )

    # Format history (window last 10 turns to avoid prompt bloat)
    history_text = ""
    if history:
        recent_history = history[-10:] if len(history) > 10 else history
        history_items = []
        for msg in recent_history:
            sender = "Salesperson" if msg.sender == "trainee" else persona.name
            history_items.append(f"{sender}: {msg.message_text}")
        history_text = "\n".join(history_items)

    # Build user message
    if history_text:
        user_message = f"""Previous messages:
{history_text}

They just said: "{trainee_message}"

Your brief, natural response as this customer:"""
    else:
        user_message = f"""They just said: "{trainee_message}"

Your brief, natural response as this customer:"""

    return {
        "system": system_prompt,
        "history": history_text,
        "user_message": user_message
    }
