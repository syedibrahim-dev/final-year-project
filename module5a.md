# SalesForge — Module 5a: Hybrid ML-LLM B2B Lead Engagement & Qualification Pipeline

## Module Purpose

Module 5a provides intelligent, semi-autonomous B2B lead outreach for small to mid-sized businesses.

Key goals:
- Allow Company Admin to upload a lead list (CSV) containing basic contact & firmographic data
- Use a trained ML model to score each lead's estimated win probability (conversion likelihood)
- Automatically decide: AI auto-engage (high-confidence leads) vs. immediate human handoff (low-confidence or uncertain leads)
- For auto-engaged leads: send personalized initial email via real SMTP, then handle multi-turn conversation via LLM-powered agent (grounded in company sales materials via RAG)
- Maintain conversation state per lead
- Escalate to human when needed (low confidence, complex objections, authority limits)
- Log all interactions and outcomes for dashboards (Module 4)

This module emphasizes **technical depth** via:
- Training a generalized XGBoost win-probability model on synthetic multi-industry B2B data (generated via SDV/CTGAN from public proxy dataset)
- Hybrid decision logic (ML scoring + simple thresholds)
- LLM conversation grounded in vector DB

Real email sending uses SMTP (no LinkedIn integration). Multi-turn replies are simulated in UI for demo/practicality, with option to send real follow-up emails.

## Key Features

1. **CSV Upload & Parsing**
   - Admin uploads CSV with minimal realistic B2B columns
   - Auto-map columns (case-insensitive, fuzzy matching) to internal schema
   - Validate required fields (at minimum: Company_Name, Email or Phone)

2. **Lead Scoring & Allocation (ML Core)**
   - Run pre-trained XGBoost model on each lead → output win_probability (0–1)
   - Simple threshold-based allocation:
     - ≥ 70%: AI auto-engage (send initial email + enable AI chat)
     - < 50%: Immediate human handoff (notify Sales Manager via dashboard/email)
     - 50–69%: AI engage with "medium confidence" flag visible in UI
   - Store score and decision per lead

3. **AI-Powered Initial Outreach & Conversation**
   - For auto-engage leads: generate & send personalized first email via real SMTP
   - Use RAG (vector DB) over uploaded sales materials to ground messages (product info, objections handling, policies)
   - Maintain per-lead conversation state
   - In UI: simulate replies (admin types "lead said X" → AI responds)
   - Optional: button to send real follow-up email via SMTP
   - Detect escalation triggers: repeated objections, budget questions beyond policy, confidence drop

4. **Human Handoff & Logging**
   - Manual or auto-escalation → notify Manager with full context (score, chat history, reason)
   - All interactions logged (transcripts, timestamps, outcomes)
   - Sync closed deals to mock/test Shopify store (or log as Transaction)

5. **Manager Visibility**
   - Dashboard table: leads with score, status (AI/Human/Pending), last interaction, action buttons (view chat, escalate, send follow-up)

## Realistic Lead CSV Columns (Minimal & Common in B2B)

Most SMB-uploaded CSVs come from LinkedIn exports, purchased lists (ZoomInfo/Apollo-style), or scraped data. They typically contain:

- Company_Name (required)
- Email (required if no Phone)
- Phone (required if no Email)
- Decision_Maker_Job_Title (e.g. CEO, VP Sales, Procurement Manager)
- Industry (e.g. SaaS, Manufacturing, Consulting)
- Country
- City
- Employee_Count (buckets: 1-50, 51-200, 201-1000, 1000+ or numeric)
- Annual_Revenue_Range (<$1M, $1-10M, $10-50M, >$50M)


No behavioral metrics (visits/time), no internal tags/quality fields.

On upload:
- Required: at least Company_Name + (Email or Phone)
- Missing values imputed (e.g. "Unknown" for Industry/City, median bucket for size/revenue)

## Synthetic Dataset Generation for Model Training

Use SDV (CTGAN) to create generalized multi-industry B2B training data:

1. Start with public lead scoring proxy (e.g. Kaggle education leads dataset ~9k rows, binary Converted target)
2. Remap/drop education-specific columns → align to above realistic schema
3. Add "Industry" column as conditioning feature
4. Train CTGAN on remapped data
5. Generate ~2,000 rows per industry (total ~20,000 rows) across 10 industries:
   - SaaS
   - Consulting
   - Manufacturing
   - Logistics & Supply Chain
   - Healthcare Services
   - Fintech
   - Retail Technology
   - Construction
   - Education Technology
   - Professional Services
6. Preserve realistic correlations (e.g. higher seniority job titles correlate with higher conversion in some industries)
7. Use "Converted" as target (realistic ~20–30% positive rate)

Train one single XGBoost classifier on full 20k synthetic rows → predict win_probability.

## Architecture Integration

Fits into existing 3-tier structure:

- **Frontend**: React — upload UI, prioritized lead dashboard, chat simulation screen
- **Backend (FastAPI)**:
  - Endpoints: /upload-leads, /get-leads, /simulate-reply, /send-followup-email, /escalate-lead
  - Services: LeadScoringService (XGBoost inference), ConversationAgentService (LangChain/LlamaIndex + RAG), EmailService (smtplib)
  - Background tasks: Celery/Redis for email sending & periodic re-scoring
- **Data Layer**:
  - PostgreSQL: enhanced Lead & AutomatedOutreach tables
  - Vector DB: RAG for conversation grounding (reuse Module 2/3)
  - Redis: cache scores, conversation state
- **ML Artifact**: pickled XGBoost model + preprocessing pipeline (loaded at startup)

Multi-tenancy: all queries filtered by organization_id.

## Data Model Changes (PostgreSQL)

Add/expand entities:

```sql
Lead (
  id: UUID PK
  organization_id: UUID FK
  company_name: str
  email: str (nullable)
  phone: str (nullable)
  job_title: str (nullable)
  industry: str (nullable)
  country: str (nullable)
  city: str (nullable)
  employee_count_bucket: str (nullable)  -- e.g. "51-200"
  revenue_range: str (nullable)
  website: str (nullable)
  win_probability: float (nullable)
  allocation_decision: str  -- "AI_ENGAGE", "HUMAN_HANDOFF", "MEDIUM_CONFIDENCE"
  status: str  -- "PENDING", "AI_ACTIVE", "HUMAN", "CLOSED_WON", "CLOSED_LOST"
  created_at, updated_at
)

AutomatedOutreach (
  id: UUID PK
  lead_id: UUID FK
  conversation_state: JSONB  -- messages list
  last_message_at: datetime
  escalated: bool
  escalated_to_user_id: UUID (nullable)
  outcome: str (nullable)  -- "WON", "LOST", etc.
)