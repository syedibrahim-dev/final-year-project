"""
Persona Agent — responsible for generating AI customer responses.

Wraps the existing prompt-building helpers from roleplay.prompts but strips
out phase detection (handled by the Analyst Agent) so the Persona Agent
focuses purely on character simulation.
"""
from __future__ import annotations

import logging
from typing import Dict

from roleplay.agents.base import BaseAgent, AgentContext, AgentResult
from roleplay.llm_client import OllamaClient
from config.settings import settings

logger = logging.getLogger(__name__)


class PersonaAgent(BaseAgent):
    """Generates natural AI customer replies in character."""

    @property
    def name(self) -> str:
        return "persona"

    def __init__(self):
        self._client = OllamaClient(
            model=settings.ROLEPLAY_LLM_MODEL,
        )

    # ── Prompt construction ──────────────────────────────────────────

    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        """
        Build system + user prompt for the Persona Agent.
        Re‑uses helpers from roleplay.prompts (personality, difficulty,
        trigger topics, RAG) but *omits* phase instructions — the Analyst
        Agent owns phase tracking now.
        """
        from roleplay.prompts import (
            _build_personality_instructions,
            _build_difficulty_behavior,
            _build_trigger_topics_section,
            _build_company_context_section,
            _build_rag_section,
        )

        persona = ctx.persona

        # ── Personality & difficulty ──
        personality_instructions = _build_personality_instructions(persona)
        difficulty_behavior = _build_difficulty_behavior(persona.difficulty)

        # ── Company context ──
        company_section = _build_company_context_section(persona)

        # ── Trigger topics ──
        trigger_section = _build_trigger_topics_section(persona)

        # ── RAG document knowledge ──
        traits = persona.personality_traits or {}
        rag_probing_style = traits.get("rag_probing_style", "curious")
        rag_section = _build_rag_section(ctx.document_context, rag_probing_style)

        # ── Scenario brief ──
        scenario_brief = getattr(persona, "scenario_brief", None) or (
            "You are a potential customer evaluating a product or service. "
            "You have some interest but haven't committed to anything yet."
        )

        # ── Scenario type context (acquisition vs displacement) ──
        scenario_type = getattr(persona, "scenario_type", "acquisition") or "acquisition"
        scenario_type_instruction = ""
        if scenario_type == "displacement":
            scenario_type_instruction = (
                "\nSCENARIO CONTEXT — DISPLACEMENT SALE:\n"
                "You already have a working solution from another vendor. You are NOT actively looking to switch.\n"
                "The rep must give you a genuinely compelling reason to even consider disrupting your current setup.\n"
                "Default to status quo bias — switching costs are real and you know it.\n"
                "Only show interest if they identify a specific pain your current vendor doesn't address.\n"
            )
        elif scenario_type == "expansion":
            scenario_type_instruction = (
                "\nSCENARIO CONTEXT — EXPANSION / RENEWAL:\n"
                "You are already a customer. This is about expanding usage or renewing your contract.\n"
                "You are generally satisfied but want to make sure you're still getting value.\n"
                "Reward the rep for reinforcing the value you're already getting. Be skeptical of upsell pressure.\n"
            )

        # ── Assemble system prompt (no phase injection) ──
        system_prompt = f"""You are playing the role of a customer in a sales call.

WHO YOU ARE IN THIS CALL:
{scenario_brief}
{scenario_type_instruction}
YOUR CHARACTER:
{persona.description}
Communication style: {persona.tone}

YOUR PERSONALITY TRAITS (follow these closely throughout the conversation):
{personality_instructions}

YOUR CONCERNS (raise these naturally as the conversation progresses):
{chr(10).join(f'- {obj}' for obj in (persona.common_objections or [])[:4])}

{company_section}

{trigger_section}

{difficulty_behavior}
{rag_section}

EMOTIONAL DYNAMICS — respond dynamically to how the rep behaves:
- If they acknowledge your concerns with specific evidence → Soften slightly, become more receptive
- If they ignore or dismiss your concerns → Become more guarded and resistant
- If they provide concrete, verifiable data → Show genuine interest
- If they use generic sales talk or buzzwords → Show skepticism or mild impatience
- If they ask a really good question about your situation → Reward them with a detailed, honest answer

CRITICAL — DO NOT BE A PUSHOVER:
- You are a REAL customer, not a helpful assistant. You do NOT want to make the salesperson's job easy.
- NEVER say "That's a great point!" or "You've convinced me!" just because they said something reasonable.
- If they give a generic pitch, respond with skepticism or redirect to YOUR concerns — don't validate their pitch.
- Only soften your stance when they provide genuinely specific, relevant evidence that addresses YOUR stated concern.
- If they haven't earned your trust yet, default to mild resistance, not agreement.
- Real customers don't praise salespeople mid-call. They challenge, redirect, and protect their own interests.
- If they dump a wall of text or information overload you, react like a real person: "Okay, slow down — that's a lot. What's the one thing I should care about?"

ANTI-HALLUCINATION RULES:
- Do NOT invent product features, pricing, company history, or statistics
- Do NOT mention specific competitor products by name unless they are in your persona's trigger_topics
- If the rep asks about something you don't have information about, say "I don't know much about that"
- You are a CUSTOMER — you're not supposed to know their product inside out. It's okay to not know things.
- If you reference something from the document content, keep it vague: "I think I read..." not "According to your documentation..."

RESPONSE RULES:
- React to what they ACTUALLY said — never give a pre-scripted answer
- Keep responses conversational and brief (1-3 sentences typical, 4 sentences absolute max)
- Sound like a REAL person, not an AI. Use natural speech patterns:
  * Occasionally start with fillers: "Hmm...", "Look,", "Yeah, but...", "I mean,", "Right, so..."
  * Sometimes trail off or self-correct: "We tried that — well, something similar anyway."
  * Use contractions naturally: "I'd", "we've", "that's", "don't", "won't"
- NEVER say your name, describe your role, or break character
- NEVER use phrases like "As a customer...", "In my role as...", "That's a great question!"
- NEVER use bullet points, numbered lists, or structured formatting
- If you don't know an answer (e.g. about their product), ask — you're the customer, not the expert

Respond naturally as this person would:"""

        # ── Inject directives from other agents ──
        if ctx.objection_directive:
            system_prompt += f"\n\n{ctx.objection_directive}"
        if ctx.difficulty_modifier:
            system_prompt += f"\n\n{ctx.difficulty_modifier}"
        if ctx.guardrail_redirect:
            system_prompt += f"\n\n{ctx.guardrail_redirect}"

        # ── Overflow check — truncate RAG if system prompt is too long ──
        # Rough estimate: 1 token ~ 4 chars. Leave room for conversation history.
        MAX_SYSTEM_CHARS = 14000  # ~3500 tokens
        if len(system_prompt) > MAX_SYSTEM_CHARS and ctx.document_context:
            # Rebuild with truncated RAG context
            rag_section = _build_rag_section(ctx.document_context[:800], rag_probing_style)
            # Reconstruct just the rag portion (it's already in the prompt)
            system_prompt = system_prompt[:system_prompt.rfind("EMOTIONAL DYNAMICS")]
            system_prompt += f"""{rag_section}

EMOTIONAL DYNAMICS — respond dynamically to how the rep behaves:
- If they acknowledge your concerns with specific evidence → Soften slightly, become more receptive
- If they ignore or dismiss your concerns → Become more guarded and resistant
- If they provide concrete, verifiable data → Show genuine interest
- If they use generic sales talk or buzzwords → Show skepticism or mild impatience
- If they ask a really good question about your situation → Reward them with a detailed, honest answer

CRITICAL — DO NOT BE A PUSHOVER:
- You are a REAL customer, not a helpful assistant. You do NOT want to make the salesperson's job easy.
- NEVER say "That's a great point!" or "You've convinced me!" just because they said something reasonable.
- If they give a generic pitch, respond with skepticism or redirect to YOUR concerns — don't validate their pitch.
- Only soften your stance when they provide genuinely specific, relevant evidence that addresses YOUR stated concern.
- If they haven't earned your trust yet, default to mild resistance, not agreement.
- Real customers don't praise salespeople mid-call. They challenge, redirect, and protect their own interests.
- If they dump a wall of text or information overload you, react like a real person: "Okay, slow down — that's a lot. What's the one thing I should care about?"

RESPONSE RULES:
- React to what they ACTUALLY said — never give a pre-scripted answer
- Keep responses conversational and brief (1-3 sentences typical, 4 sentences absolute max)
- Sound like a REAL person, not an AI. Use natural speech patterns:
  * Occasionally start with fillers: "Hmm...", "Look,", "Yeah, but...", "I mean,", "Right, so..."
  * Sometimes trail off or self-correct: "We tried that — well, something similar anyway."
  * Use contractions naturally: "I'd", "we've", "that's", "don't", "won't"
- NEVER say your name, describe your role, or break character
- NEVER use phrases like "As a customer...", "In my role as...", "That's a great question!"
- NEVER use bullet points, numbered lists, or structured formatting
- If you don't know an answer (e.g. about their product), ask — you're the customer, not the expert

Respond naturally as this person would:"""

            # Re-inject directives
            if ctx.objection_directive:
                system_prompt += f"\n\n{ctx.objection_directive}"
            if ctx.difficulty_modifier:
                system_prompt += f"\n\n{ctx.difficulty_modifier}"
            if ctx.guardrail_redirect:
                system_prompt += f"\n\n{ctx.guardrail_redirect}"

        # ── User message (with dynamic windowed history) ──
        max_turns = {"beginner": 8, "intermediate": 12, "advanced": 20}.get(
            ctx.difficulty, 10
        )
        history_text = self._format_transcript(ctx.messages, max_turns=max_turns)

        if history_text:
            user_message = (
                f"Previous messages:\n{history_text}\n\n"
                f'They just said: "{ctx.trainee_message}"\n\n'
                f"Your brief, natural response as this customer:"
            )
        else:
            user_message = (
                f'They just said: "{ctx.trainee_message}"\n\n'
                f"Your brief, natural response as this customer:"
            )

        return {"system": system_prompt, "user": user_message}

    # ── Execution ────────────────────────────────────────────────────

    # ── Output guardrails ───────────────────────────────────────────

    # Phrases that indicate the LLM broke character
    _CHARACTER_BREAK_SIGNALS = [
        "as an ai", "as a language model", "i'm an ai", "i am an ai",
        "i cannot", "i can't help with", "i don't have personal",
        "as an artificial", "i'm not a real person", "i'm just a",
        "that's a great question!", "great question!", "excellent question!",
        "i'd be happy to help", "certainly!", "absolutely! let me",
    ]

    # Patterns that suggest hallucinated product specifics
    _HALLUCINATION_SIGNALS = [
        r'\b\d{3,}\s*(clients|customers|users)\b',  # "500 customers" — specific numbers the AI makes up
        r'\b(founded in|established in|since)\s+\d{4}\b',  # Inventing company history
        r'\b(award|certification|patent)\s+(winning|certified)\b',  # Inventing credentials
    ]

    def _check_output(self, response: str, ctx: AgentContext) -> str:
        """
        Post-generation guardrail for AI customer output.
        Checks for character breaks, hallucinations, and off-topic drift.
        Returns cleaned response or flags issues via logging.
        """
        import re as _re
        lower = response.lower()

        # Check 1: Character break — LLM slipped out of persona
        for signal in self._CHARACTER_BREAK_SIGNALS:
            if signal in lower:
                logger.warning(f"PersonaAgent output guardrail: character break detected ('{signal}')")
                # Strip the offending sentence and keep the rest
                sentences = _re.split(r'(?<=[.!?])\s+', response)
                cleaned = [s for s in sentences if signal not in s.lower()]
                if cleaned:
                    return " ".join(cleaned)
                # Entire response was a character break — return a safe fallback
                return "Hmm, I'm not sure I follow. Can you explain what you mean?"

        # Check 2: Hallucination — AI inventing specific numbers/facts not in docs
        if ctx.document_context:
            for pattern in self._HALLUCINATION_SIGNALS:
                match = _re.search(pattern, lower)
                if match:
                    matched_text = match.group(0)
                    # Check if this specific claim appears in the document context
                    if matched_text not in ctx.document_context.lower():
                        logger.warning(
                            f"PersonaAgent output guardrail: possible hallucination "
                            f"('{matched_text}' not in document context)"
                        )
                        # Don't block — just log. The claim might be from the persona's scenario.

        # Check 3: Response too long (LLM ignored brevity rules)
        words = response.split()
        if len(words) > 100:
            # Trim to first 3-4 sentences
            sentences = _re.split(r'(?<=[.!?])\s+', response)
            trimmed = " ".join(sentences[:4])
            if len(trimmed) > 20:
                logger.info(f"PersonaAgent output guardrail: trimmed {len(words)} words to {len(trimmed.split())} words")
                return trimmed

        return response

    # ── Execution ────────────────────────────────────────────────────

    def run(self, ctx: AgentContext) -> AgentResult:
        """Call Ollama and return the customer reply."""
        prompts = self.build_prompt(ctx)

        def _call_llm():
            return self._client.generate_response(
                system_prompt=prompts["system"],
                user_message=prompts["user"],
            )

        try:
            response_text, latency = self._timed_run(_call_llm)
            # Strip stray quotes the model sometimes adds
            cleaned = response_text.strip().strip('"').strip("'")
            # Run output guardrails
            cleaned = self._check_output(cleaned, ctx)
            logger.info(
                f"PersonaAgent responded in {latency:.0f}ms "
                f"({len(cleaned)} chars)"
            )
            return self._make_result(
                data={"response": cleaned},
                latency_ms=latency,
            )
        except Exception as e:
            logger.error(f"PersonaAgent failed: {e}")
            return self._make_result(
                data={"response": ""},
                success=False,
                error=str(e),
            )
