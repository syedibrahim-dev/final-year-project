"""
Lead → MCQ bridge.

When a sales lead converts (CLOSED_WON), this service reads the AutomatedOutreach
conversation transcript and generates a 5-question MCQ test that captures the
sales lessons from that won deal. The test is saved to the org's MCQ library so
trainees can learn from real won deals during their roleplay practice.

This is the cross-module link between friend's automation modules (Lead Scoring,
Outreach) and my MCQ + Roleplay modules — every closed win becomes a training
data point.

Why direct LLM (not the RAG-based MCQPipeline)?
  The MCQPipeline retrieves context from ChromaDB then generates questions. Here
  we already HAVE the full context (the conversation transcript), so RAG would
  add noise. We feed the transcript directly to the LLM and request structured
  Q&A output.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session

from config.settings import settings
from models.lead import Lead, AutomatedOutreach
from models.mcq import MCQTest

logger = logging.getLogger(__name__)


def _extract_transcript(outreach: AutomatedOutreach) -> str:
    """Flatten the conversation_state JSON into a readable transcript."""
    if not outreach or not outreach.conversation_state:
        return ""
    lines = []
    for msg in outreach.conversation_state:
        role = msg.get("role", "?").upper()
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _build_mcq_prompt(transcript: str, lead: Lead) -> str:
    """Construct the LLM prompt that extracts MCQs from a won-deal transcript."""
    return f"""You are a sales training designer. Below is the transcript of a sales
conversation that successfully closed (CLOSED_WON). Extract 5 multiple-choice
questions a trainee should be able to answer to learn from this win.

LEAD CONTEXT:
- Company: {lead.company_name}
- Industry: {lead.industry or 'Unknown'}
- Job Title: {lead.decision_maker_job_title or 'Unknown'}
- Win Probability: {lead.win_probability or 'N/A'}

TRANSCRIPT:
---
{transcript}
---

Generate 5 multiple-choice questions that test:
  1. The buyer's primary pain point
  2. The objection that was raised and how it was handled
  3. The value prop that resonated most
  4. The closing technique used
  5. A general best-practice illustrated by this conversation

Output ONLY valid JSON with this exact shape (no markdown, no preamble):

{{
  "questions": [
    {{
      "question": "What was the buyer's primary pain point?",
      "options": [
        {{"letter": "A", "text": "Option A text", "is_correct": false}},
        {{"letter": "B", "text": "Option B text", "is_correct": true}},
        {{"letter": "C", "text": "Option C text", "is_correct": false}},
        {{"letter": "D", "text": "Option D text", "is_correct": false}}
      ],
      "correct_answer": "B",
      "explanation": "One sentence explaining why B is correct, grounded in the transcript."
    }}
  ]
}}

Rules:
- Each question must have exactly 4 options (A, B, C, D) with exactly one correct.
- Distractors must be plausible but clearly wrong given the transcript.
- Use only facts that appear in the transcript or can be inferred from it."""


def _call_llm(prompt: str, timeout: int = 120) -> str:
    """Call the local Ollama LLM and return the raw response text."""
    response = requests.post(
        f"{settings.LOCAL_LLM_BASE_URL}/api/generate",
        json={
            "model": settings.MCQ_LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.4,    # lower = more grounded in transcript
                "num_predict": 2000,   # MCQs can be long
            },
        },
        timeout=(10, timeout),
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def _extract_json_block(text: str) -> Optional[dict]:
    """LLMs often wrap JSON in markdown or add commentary. Extract the JSON dict."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first { ... matching } block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        # Last resort: strip trailing commas
        cleaned = re.sub(r',\s*([}\]])', r'\1', match.group(0))
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM JSON output")
            return None


def _normalize_questions(parsed: dict) -> list:
    """
    Convert the LLM's questions into the schema MCQTest.questions_json expects.
    Tolerant of small format variations.
    """
    raw_qs = parsed.get("questions", []) if isinstance(parsed, dict) else []
    normalized = []

    for q in raw_qs:
        if not isinstance(q, dict):
            continue
        question_text = q.get("question") or q.get("stem", "")
        options = q.get("options", [])
        correct_letter = q.get("correct_answer", "")
        explanation = q.get("explanation", "")

        if not question_text or not options or len(options) != 4:
            continue

        # Some LLMs output options as plain strings — normalize to dicts
        normalized_options = []
        for i, opt in enumerate(options):
            letter = chr(ord('A') + i)
            if isinstance(opt, dict):
                text = opt.get("text", "")
                is_correct = opt.get("is_correct", False) or opt.get("letter") == correct_letter
                normalized_options.append({
                    "letter": letter,
                    "text": text,
                    "is_correct": is_correct,
                })
            else:
                normalized_options.append({
                    "letter": letter,
                    "text": str(opt),
                    "is_correct": (letter == correct_letter),
                })

        # Ensure exactly one correct answer
        correct_count = sum(1 for o in normalized_options if o["is_correct"])
        if correct_count != 1:
            continue

        normalized.append({
            "question": question_text,
            "options": normalized_options,
            "correct_answer": correct_letter,
            "explanation": explanation,
        })

    return normalized


def generate_mcq_from_lead_conversation(db: Session, lead_id: int) -> Optional[MCQTest]:
    """
    Read a won lead's conversation transcript and generate an MCQ test from it.
    Returns the created MCQTest, or None if generation failed.

    Idempotency: if a test already exists with title matching this lead, return
    the existing one instead of generating a duplicate.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        logger.warning(f"Lead {lead_id} not found — skipping MCQ generation")
        return None

    if lead.status != "CLOSED_WON":
        logger.warning(f"Lead {lead_id} status={lead.status} — only CLOSED_WON triggers MCQ gen")
        return None

    outreach = db.query(AutomatedOutreach).filter(
        AutomatedOutreach.lead_id == lead_id
    ).first()

    transcript = _extract_transcript(outreach)
    if not transcript or len(transcript) < 100:
        logger.warning(f"Lead {lead_id} has insufficient conversation history ({len(transcript)} chars)")
        return None

    test_title = f"Sales Lessons: {lead.company_name} (Won Deal)"

    # Idempotency check
    existing = db.query(MCQTest).filter(
        MCQTest.organization_id == lead.organization_id,
        MCQTest.title == test_title,
    ).first()
    if existing:
        logger.info(f"Test '{test_title}' already exists (id={existing.id}) — skipping regeneration")
        return existing

    print(f"📚 Generating MCQ from won deal: {lead.company_name}")
    prompt = _build_mcq_prompt(transcript, lead)

    try:
        raw = _call_llm(prompt)
    except Exception as e:
        logger.exception(f"LLM call failed for lead {lead_id}: {e}")
        return None

    parsed = _extract_json_block(raw)
    if not parsed:
        logger.warning(f"LLM response unparseable for lead {lead_id}")
        return None

    questions = _normalize_questions(parsed)
    if len(questions) < 3:
        logger.warning(f"Only {len(questions)} valid questions generated — need at least 3")
        return None

    # Find a user to attribute the test to (the org's first admin/manager, or any user)
    from models.user import User
    creator = db.query(User).filter(
        User.organization_id == lead.organization_id,
        User.role.in_(["admin", "manager", "trainer"]),
    ).first()
    if not creator:
        creator = db.query(User).filter(User.organization_id == lead.organization_id).first()
    if not creator:
        logger.warning(f"No user found for org {lead.organization_id} — cannot create test")
        return None

    test = MCQTest(
        title=test_title,
        description=(
            f"Auto-generated from the won-deal conversation with {lead.company_name}. "
            f"Trainees should answer these questions to learn what made this deal successful."
        ),
        topic=f"Won Deal: {lead.industry or lead.company_name}",
        difficulty="medium",
        questions_json=questions,
        organization_id=lead.organization_id,
        created_by=creator.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    print(f"✅ MCQ test created from lead {lead_id}: '{test.title}' (id={test.id}, {len(questions)} questions)")
    return test
