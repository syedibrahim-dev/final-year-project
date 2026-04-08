import re
import requests
import json
from datetime import datetime
import traceback
from config.settings import settings
from services.rag_service import retrieve_relevant_chunks
from services.email_service import EmailService


# ---------------------------------------------------------------------------
# Quality-gate helpers
# ---------------------------------------------------------------------------

def _strip_bracket_placeholders(text: str) -> str:
    """
    Remove any leftover [placeholder] or [Your Name] style tokens the LLM
    failed to fill in.  Replace with empty string so the sentence still reads
    naturally (e.g. "Best, [Your Name]" → "Best,").
    """
    # Matches tokens like [Your Name], [Our Company], [CEO at Apex], etc.
    cleaned = re.sub(r'\[.*?\]', '', text)
    # Collapse double-spaces / trailing commas left behind
    cleaned = re.sub(r'  +', ' ', cleaned)
    cleaned = re.sub(r',\s*\.', '.', cleaned)   # ", ." → "."
    cleaned = re.sub(r',\s*$', '', cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _validate_and_fix_email(email_text: str, sender_name: str, sender_company: str) -> str:
    """
    Fast, deterministic quality gate applied AFTER LLM generation.
    Catches the most common issues without needing a second LLM call.

    Checks:
      1. Strip any [bracket placeholder] text
      2. Ensure signoff exists with real sender name
      3. Cap excessive length (truncate at last sentence before ~200 words)
    """
    issues = []

    # 1) Strip bracket placeholders
    if re.search(r'\[.*?\]', email_text):
        issues.append("bracket_placeholders")
        email_text = _strip_bracket_placeholders(email_text)

    # 2) Ensure there is a sign-off with the real sender name
    lines = email_text.rstrip().split('\n')
    last_line = lines[-1].strip() if lines else ""

    has_signoff = any(
        last_line.lower().startswith(kw)
        for kw in ["best", "cheers", "regards", "thanks", "warm", "sincerely", "talk soon"]
    )
    if not has_signoff:
        email_text = email_text.rstrip() + f"\n\nBest,\n{sender_name}\n{sender_company}"
    elif sender_name and sender_name not in email_text:
        # There's a signoff but it lacks the sender name — append it
        email_text = email_text.rstrip() + f"\n{sender_name}\n{sender_company}"

    # 3) Length cap — if over ~200 words, truncate at last complete sentence
    words = email_text.split()
    if len(words) > 200:
        issues.append(f"too_long ({len(words)} words)")
        truncated = ' '.join(words[:200])
        # Find last sentence-ending punctuation
        last_period = max(truncated.rfind('.'), truncated.rfind('?'), truncated.rfind('!'))
        if last_period > 0:
            truncated = truncated[:last_period + 1]
        email_text = truncated + f"\n\nBest,\n{sender_name}\n{sender_company}"

    if issues:
        print(f"   🔧 Validator fixed: {', '.join(issues)}")
    else:
        print(f"   ✅ Validator: email passed all checks")

    return email_text


# ---------------------------------------------------------------------------
# Core Outreach Service
# ---------------------------------------------------------------------------

class OutreachService:
    def __init__(self, org_id: int, sender_name: str = "Sales Team", sender_company: str = "Our Company"):
        self.org_id = org_id
        self.sender_name = sender_name
        self.sender_company = sender_company
        self.llm_url = settings.LOCAL_LLM_BASE_URL
        self.model_name = settings.ROLEPLAY_LLM_MODEL

    def generate_initial_email(self, lead_data: dict, goal: str) -> str:
        """
        Generates a personalized cold email using RAG context, then runs it
        through the quality-gate validator before returning.
        """
        # 1) RAG — pull relevant company knowledge
        search_query = (
            f"What are our key value propositions and solutions "
            f"for the {lead_data.get('industry', 'B2B')} industry?"
        )
        try:
            chunks = retrieve_relevant_chunks(search_query, self.org_id, k=3)
        except Exception as e:
            print(f"   ⚠️ RAG retrieval failed, continuing without context: {e}")
            chunks = []

        rag_context = ""
        if chunks:
            rag_context = "\n".join([c['chunk'] for c in chunks])

        # 2) Build prompt — explicitly identify the sender to prevent identity bleed
        contact_title = lead_data.get('decision_maker_job_title', '')
        contact_greeting = contact_title if contact_title else "there"

        system_prompt = f"""You are writing a cold outreach email on behalf of {self.sender_name} from {self.sender_company}.

STRICT RULES — violating ANY of these makes the email unusable:
1. You are {self.sender_name} from {self.sender_company}. NEVER pretend to be any other company.
2. Do NOT copy brand names, product names, or company names from the reference material below.
   Instead, describe the CAPABILITIES in your own words as if they are {self.sender_company}'s offerings.
3. Do NOT use bracket placeholders like [Your Name], [Company], [Insert X]. Every field must be filled in.
4. Keep the email under 120 words. Short emails get more replies.
5. End with a clear, single call-to-action and sign off as "{self.sender_name}, {self.sender_company}".
6. Be conversational and human. Do not sound like a template."""

        user_prompt = f"""PROSPECT INFO:
- Company: {lead_data.get('company_name', 'Unknown')}
- Role: {contact_title or 'Decision Maker'}
- Industry: {lead_data.get('industry', 'Unknown')}
- Company Size: {lead_data.get('employee_count', 'Unknown')} employees

REFERENCE MATERIAL (use for inspiration about capabilities, do NOT copy brand names):
{rag_context if rag_context else '(No reference material available — write a general value-focused pitch.)'}

CAMPAIGN GOAL: {goal}

Write the email now. Output ONLY the email body — no subject line, no commentary."""

        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        # 3) Call LLM to draft the email
        raw_email = self._call_llm(full_prompt)

        # 4) Deterministic quality gate (regex cleanup)
        cleaned_email = _validate_and_fix_email(raw_email, self.sender_name, self.sender_company)

        # 5) LLM Quality-Check Agent — evaluates and rewrites if needed
        final_email = self._quality_check_agent(cleaned_email, lead_data)

        return final_email

    def _quality_check_agent(self, email_text: str, lead_data: dict) -> str:
        """
        LLM-powered quality-check agent.
        Evaluates the draft email against 5 criteria and rewrites it if any fail.
        Returns the final email (original if it passed, rewritten if it didn't).
        """
        print(f"   🕵️ Quality Agent: reviewing draft...")

        checker_prompt = f"""You are an email quality-control agent. Your job is to review a cold outreach email draft and decide if it's ready to send.

SENDER IDENTITY: {self.sender_name} from {self.sender_company}

DRAFT EMAIL:
---
{email_text}
---

PROSPECT: {lead_data.get('decision_maker_job_title', 'Decision Maker')} at {lead_data.get('company_name', 'Unknown')} ({lead_data.get('industry', 'Unknown')} industry)

Evaluate the draft against these 5 criteria:
1. IDENTITY: Does it correctly identify the sender as {self.sender_name} from {self.sender_company}? It must NOT mention any other company name as the sender (e.g. DigiCert, HubSpot, etc.)
2. PLACEHOLDERS: Are there any unfilled placeholders like [Your Name], [Company], [Insert X]?
3. LENGTH: Is it under 150 words?
4. PERSONALIZATION: Does it reference the prospect's company name, industry, or role?
5. CTA: Does it end with a clear, single call-to-action?

If ALL 5 criteria pass, respond with EXACTLY:
VERDICT: PASS

If ANY criteria fail, respond with EXACTLY:
VERDICT: FAIL
REWRITE:
(then write a corrected version of the email that fixes all issues, under 120 words, signed off as {self.sender_name} from {self.sender_company})"""

        try:
            result = self._call_llm(checker_prompt)

            if "VERDICT: PASS" in result:
                print(f"   ✅ Quality Agent: PASSED — email is ready to send")
                return email_text
            elif "VERDICT: FAIL" in result:
                # Extract the rewritten email after "REWRITE:"
                rewrite_marker = "REWRITE:"
                idx = result.find(rewrite_marker)
                if idx != -1:
                    rewritten = result[idx + len(rewrite_marker):].strip()
                    # Run the deterministic validator on the rewrite too
                    rewritten = _validate_and_fix_email(rewritten, self.sender_name, self.sender_company)
                    print(f"   🔄 Quality Agent: FAILED — rewrote email ({len(rewritten)} chars)")
                    return rewritten
                else:
                    print(f"   ⚠️ Quality Agent: FAILED but no rewrite provided, using original")
                    return email_text
            else:
                # Couldn't parse the verdict — play it safe, use original
                print(f"   ⚠️ Quality Agent: unclear response, using original")
                return email_text

        except Exception as e:
            print(f"   ⚠️ Quality Agent failed ({e}), using original email")
            return email_text

    def _call_llm(self, prompt: str) -> str:
        """Call the local Ollama LLM and return the raw text response."""
        try:
            response = requests.post(
                f"{self.llm_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.5,
                        "num_predict": 300,   # Hard cap on tokens to prevent verbosity
                    }
                },
                timeout=(10, 300)
            )
            if response.status_code == 200:
                data = response.json()
                result = data.get("response", "").strip()
                print(f"   ✨ LLM generation complete ({len(result)} chars)")
                return result
            else:
                print(f"   ⚠️ LLM Error {response.status_code}, using fallback text.")
        except Exception as e:
            print(f"   ⚠️ LLM call failed: {e}")

        # Fallback — a minimal, clean email
        return (
            f"Hi there,\n\n"
            f"I'm {self.sender_name} from {self.sender_company}. "
            f"We help companies in your space drive growth and efficiency. "
            f"Would you have 15 minutes this week for a quick call?\n\n"
            f"Best,\n{self.sender_name}"
        )

    def send_and_log_email(self, db, lead, generated_email: str):
        """
        Transmits the email via SMTP and saves it to the AutomatedOutreach record.
        """
        from models.lead import AutomatedOutreach

        subject = f"Quick question for {lead.company_name}"

        actual_sent = False
        if lead.email:
            print(f"   ✉️  Transmitting email to {lead.email} via SMTP...")
            actual_sent = EmailService.send_email(lead.email, subject, generated_email)
            if not actual_sent:
                print(f"   ⚠️ SMTP failed for {lead.email}, saving as draft.")

        # Locate or create the AutomatedOutreach record
        outreach = db.query(AutomatedOutreach).filter(
            AutomatedOutreach.lead_id == lead.id
        ).first()
        if not outreach:
            outreach = AutomatedOutreach(
                lead_id=lead.id,
                conversation_state=[],
                escalated=False,
            )
            db.add(outreach)

        # Append to conversation state
        current_state = outreach.conversation_state or []
        current_state.append({
            "role": "ai",
            "content": generated_email,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "email",
            "sent_via_smtp": actual_sent,
        })

        from sqlalchemy.orm.attributes import flag_modified
        outreach.conversation_state = current_state
        outreach.last_message_at = datetime.utcnow()
        flag_modified(outreach, "conversation_state")

        lead.status = "AI_ACTIVE"
        db.commit()


# ---------------------------------------------------------------------------
# Background task entry-point
# ---------------------------------------------------------------------------

def process_bulk_outreach(org_id: int, goal: str, lead_ids: list):
    """
    Background task: generates + sends outreach emails for a batch of leads.
    Loads sender identity from the DB so emails are properly attributed.
    """
    from utils.database import SessionLocal
    from models.lead import Lead
    from models.organization import Organization
    from models.user import User

    db = SessionLocal()

    try:
        # Resolve sender identity
        org = db.query(Organization).filter(Organization.id == org_id).first()
        sender_company = org.name if org else "Our Company"

        # Find an admin or first user in the org to use as sender name
        admin_user = db.query(User).filter(
            User.organization_id == org_id,
            User.role.in_(["admin", "manager"])
        ).first()
        if not admin_user:
            admin_user = db.query(User).filter(User.organization_id == org_id).first()
        sender_name = (admin_user.full_name if admin_user and admin_user.full_name
                       else "Sales Team")

        service = OutreachService(org_id, sender_name=sender_name, sender_company=sender_company)

        leads = db.query(Lead).filter(Lead.id.in_(lead_ids)).all()
        print(f"\n🚀 Starting Bulk AI Outreach for {len(leads)} leads...")
        print(f"🎯 Goal: {goal}")
        print(f"📧 Sending as: {sender_name} @ {sender_company}")
        print("-" * 50)

        for lead in leads:
            try:
                lead_data = {
                    "decision_maker_job_title": lead.decision_maker_job_title,
                    "company_name": lead.company_name,
                    "industry": lead.industry,
                    "employee_count": lead.employee_count,
                }

                print(f"\n🤖 Processing Lead: {lead.company_name} ({lead.email})")
                email_body = service.generate_initial_email(lead_data, goal)

                service.send_and_log_email(db, lead, email_body)
                print(f"✅ Lead {lead.id} processed successfully.")

            except Exception as item_err:
                print(f"❌ Failed to process Lead {lead.id}: {item_err}")
                traceback.print_exc()
                lead.status = "PENDING"
                db.commit()

    except Exception as e:
        print(f"❌ Bulk outreach process failed: {e}")
        traceback.print_exc()
    finally:
        print(f"\n🏁 Finished Bulk Outreach at {datetime.now().strftime('%H:%M:%S')}")
        db.close()
