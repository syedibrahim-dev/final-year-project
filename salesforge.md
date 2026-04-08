# SalesForge — Project Context for Claude Code

## Project Overview

**SalesForge** is an AI-powered sales training and automation platform built for small to mid-sized businesses. It combines two core pillars:

1. **Adaptive Sales Training** — Personalized, AI-driven learning paths, interactive quizzes, and AI role-play simulations to develop sales talent.
2. **Sales & Operations Automation** — Autonomous lead engagement, marketing content generation, social media monitoring, inventory forecasting, and e-commerce analytics.

The platform is a **web-based, multi-tenant SaaS application** where multiple organizations each have isolated data and user management.

---

## Tech Stack (Planned)

| Layer | Technology |
|---|---|
| Frontend | React.js / Vue.js |
| Backend | Python (Django or FastAPI) with SQLAlchemy/Django ORM |
| Primary Database | PostgreSQL (relational, ORM-mapped) |
| Vector Database | Vector DB (for AI embeddings) |
| File Storage | AWS S3 or Firebase Storage (PDFs, transcripts, images) |
| Caching | Redis (high-frequency queries, dashboard metrics) |
| AI/LLM | LLM APIs (for simulations, content generation, NL queries) |
| External Integrations | Shopify (e-commerce), Social Media APIs, Email/LinkedIn/Voice |
| API Style | REST (HTTPS), API Gateway pattern |

---

## Architecture

The system follows a **3-Tier Architecture**:

### Tier 1 — Presentation Layer (Frontend)
- Single web app serving all user roles: Admin, Manager, Sales Rep, Store Owner
- Interfaces: dashboards, quiz/course UIs, AI role-play screens, automation panels
- Communicates with backend via secure HTTPS REST APIs

### Tier 2 — Application Layer (Backend Services)
Five key backend subsystems:
- **Identity Service** — User & organization management, auth, RBAC
- **Training Service** — Course creation, adaptive learning paths, quiz/progress tracking
- **AI Core Service** — Role-play simulations, content generation, scoring/feedback
- **Analytics Service** — Dashboards, performance aggregation, forecasting
- **Automation Service** — Lead outreach, marketing posts, social media monitoring, store chatbot

### Tier 3 — Data Layer
- PostgreSQL for all structured data
- Vector DB for AI embeddings (used by simulations and NL queries)
- Cloud object storage for files (PDFs, audio, images, CSVs)
- External APIs: Shopify, social platforms, email, voice

---

## Modules & Features

### Module 1 — User & Organization Management
**Purpose:** Multi-tenant account system with role-based access control.

**Features:**
- Organization admin can create a company account and invite team members via token-based invites
- Role-based access control (RBAC) with roles: Company Admin, Sales Manager, Sales Rep, Store Owner, Marketing Assistant
- Track each user's training completion status and certification progress
- Admin can manage (add/remove/edit) users within their organization
- Data isolation: users can only access data belonging to their organization

**Key Entities:** `User`, `Organization`, `Role`, `Invitation`

---

### Module 2 — Personalized Learning Content
**Purpose:** Generate and deliver adaptive training content tailored to each sales rep.

**Features:**
- Admin uploads sales materials (PDFs, product catalogs) → AI auto-generates lessons and MCQ quizzes from the content
- Interactive multiple-choice courses with progress tracking
- Adaptive learning paths generated based on quiz scores and identified knowledge gaps
- Track each user's progress per module (completion %, time spent, scores)
- Store all quiz scores and completion records per organization workspace

**Key Entities:** `SalesMaterial`, `TrainingContent`, `Course`, `Lesson`, `Quiz`, `UserProgress`

---

### Module 3 — AI Role-Play & Skill Assessment
**Purpose:** Let sales reps practice live sales conversations with AI-powered virtual customer personas.

**Features:**
- Simulate text and/or voice conversations with diverse virtual customer personas (e.g., angry, price-focused, undecided, enterprise buyer)
- Automatically transcribe and record each role-play session
- AI analyzes transcripts and scores performance across: product knowledge, objection handling, closing skills, communication quality
- Generate targeted improvement recommendations after each session
- Track session history and store feedback reports per user
- Surface weakest skill areas to drive adaptive learning path updates

**Key Entities:** `RoleplaysSession`, `Persona`, `Transcript`, `Feedback`, `PerformanceData`

---

### Module 4 — Performance Tracking & Dashboards
**Purpose:** Give managers and admins visibility into team training performance.

**Features:**
- Manager/Admin dashboard showing individual and team performance
- Visualize: completion rates, quiz scores, time spent learning, role-play scores
- Display data in both tabular and graphical formats (charts, progress bars)
- Monitor employee quiz scores over time
- Organization-level aggregated metrics vs individual breakdowns

**Key Entities:** `PerformanceMetrics`, `DashboardView`

---

### Module 5 — Sales, Marketing & Operations Automation
**Purpose:** Automate key e-commerce and outbound sales workflows for connected stores.

This module has several sub-components:

#### 5a — AI Lead Engagement Agent
- Admin/Manager uploads a lead list (CSV)
- AI agent autonomously contacts leads via multiple channels (email, LinkedIn, etc.)
- Agent conducts conversations, qualifies prospects, handles objections, negotiates within defined policies
- Generates personalized offers/proposals based on lead responses
- Converts closed leads into sales orders synced with the connected store (e.g., Shopify)
- Escalates complex cases to a human sales rep (human handoff flow)

**Implementation Status (March 2026): Completed baseline bulk outreach pipeline**
- Backend includes `services/outreach_service.py` for background bulk processing with RAG-grounded email drafting (from sales playbooks) and local Ollama generation (`llama3.2:3b`)
- SMTP delivery is implemented via `services/email_service.py` using Gmail SMTP (`smtp.gmail.com`) with app-password authentication
- FastAPI `BackgroundTasks` keep API/UI responsive while drafting and sending emails for large lead batches
- Frontend lead manager includes campaign-goal input modal, status badges, and lead detail visibility for outreach history
- Lead statuses currently used: `PENDING`, `DRAFTING`, `AI_ACTIVE`
- Test CSVs and environment setup are in place for safe end-to-end verification (`SMTP_EMAIL`, `SMTP_PASSWORD`)
- Database persistence is active for both lead status/allocation state and outreach conversation history JSON

**Next Build Targets**
- Add a chat simulation screen to view full AI-lead conversation threads
- Implement escalation triggers to move leads from `AI_ACTIVE` to `MANUAL_REVIEW` for high-interest or complex queries
- Add real-time status updates (WebSockets) so lead badges update without manual refresh

**Key Entities:** `Lead`, `AutomatedOutreach`, `Order`, `Transaction`

#### 5b — AI Marketing Post Generator
- Select products and social platforms → AI writes post content and generates images
- Manager can edit, approve, and schedule posts for publication
- Supports multiple platforms (Instagram, LinkedIn, Facebook, etc.)
- Track engagement trends per post

**Key Entities:** `MarketingPost`, `Campaign`

#### 5c — Social Media Sentiment Monitor
- Continuously monitors social media mentions of the brand
- Displays sentiment as green/yellow/red indicators on dashboard
- Sends automatic alerts to managers when negative sentiment spikes are detected

**Key Entities:** `SentimentRecord`, `Alert`

#### 5d — Store Owner Chatbot (NL Business Queries)
- Store owner connects their e-commerce account (e.g., Shopify)
- Can query business data in natural language: "What are my best-selling products this month?", "Which items are low on stock?"
- AI returns answers grounded in actual store data

#### 5e — Inventory Forecasting
- Predicts inventory depletion dates based on sales velocity
- Issues automatic low-stock alerts via dashboard or email
- Runs as a background task (updates at least every 3 hours)

**Key Entities:** `Store`, `Product`, `InventoryForecast`, `StockAlert`

#### 5f — Transaction Analysis
- Analyze store transaction history
- Surface trends, anomalies, and performance summaries

---

## User Roles & Permissions

| Role | Primary Responsibilities |
|---|---|
| **Company Admin** | Creates org, manages all users, uploads materials & lead lists, configures integrations, oversees all modules |
| **Sales Manager** | Monitors team training progress, reviews scores, approves marketing posts, receives sentiment alerts, views Manager Dashboard |
| **Sales Representative** | Takes courses, completes quizzes, practices AI role-play, receives personalized feedback and learning paths |
| **Store Owner** | Connects e-commerce store, queries AI chatbot for store insights, receives inventory forecasts and alerts |
| **Marketing Assistant** | Creates/approves/schedules AI-generated marketing content, monitors brand sentiment |
| **System AI Agent** | Background service — reads materials, generates lessons, conducts simulations, creates content, forecasts inventory, answers NL queries |

---

## Data Model Summary

### Core Entities

```
Organization
  └── Users (1:N)
       └── Role

SalesMaterial → generates → TrainingContent → Course → Lesson → Quiz
User → UserProgress (tracks per course/lesson)

RoleplaysSession (User ↔ Persona)
  └── Transcript
  └── Feedback
  └── PerformanceData

Lead → AutomatedOutreach → Order → Transaction

MarketingPost → Campaign
SentimentRecord → Alert

Store → Product → InventoryForecast → StockAlert

PerformanceMetrics → DashboardView
```

### Storage Strategy
- **PostgreSQL** — all structured relational data
- **Vector DB** — embeddings for AI simulations and NL search
- **Object Storage (S3/Firebase)** — PDFs, audio recordings, images, CSVs
- **Redis** — caching for dashboards and high-frequency queries

---

## Non-Functional Requirements

### Performance
- Support **100+ concurrent users** without degradation
- AI role-play response time: **≤ 30 seconds** per interaction
- Dashboard queries: **≤ 10 seconds** for up to 10,000 records
- File uploads up to **50 MB** processed within 15 seconds
- DB read/write: **≤ 2 seconds** average
- Background automation tasks update **every 3 hours** minimum
- Notification/alert delivery: **within 30 seconds** of trigger

### Reliability & Availability
- **99% uptime** during operational hours
- **24/7 availability** except scheduled maintenance (24hr advance notice)
- Data backup and recovery mechanisms in place

### Security
- HTTPS (TLS) for all data in transit
- Encryption at rest for sensitive data
- RBAC enforces data visibility per organization (multi-tenant isolation)
- Passwords stored with secure hashing (e.g., bcrypt)
- Session invalidation after inactivity
- Brute-force and intrusion detection/prevention
- 95%+ of unauthorized access attempts blocked
- Secure data sharing between modules and external APIs

### Scalability
- Horizontal scaling of backend services
- Multi-tenant architecture with per-organization data isolation

### Compatibility
- Runs on all major browsers: Chrome, Firefox, Edge (no plugins required)
- Deployable on cloud or on-premise
- Designed for future mobile expansion

---

## Key Implementation Notes for Claude Code

1. **Multi-tenancy is critical** — every database query must be scoped to the requesting user's `organization_id`. Never leak data across organizations.

2. **AI integrations** — The AI Core Service is central. It powers: lesson generation from PDFs, quiz creation, role-play simulation, transcript analysis, feedback scoring, marketing copy, sentiment analysis, NL query answering, and inventory forecasting.

3. **Background jobs** — Sentiment monitoring, inventory forecasting, and report generation run as scheduled background tasks (e.g., Celery with Redis, or similar).

4. **File processing pipeline** — When an admin uploads a PDF, it should be: stored in object storage → text extracted → passed to AI → lessons/quizzes generated → saved to DB → linked to the organization's training workspace.

5. **Lead outreach flow** — The AI agent must support multi-channel outreach (email, LinkedIn at minimum), maintain conversation state per lead, and trigger a human handoff when confidence or authority threshold is breached.

6. **API Gateway** — All frontend requests go through a single API Gateway which handles auth, routing, and rate limiting before reaching backend microservices.

7. **ORM** — Use SQLAlchemy (FastAPI) or Django ORM (Django) with migration management. Each major domain object maps to a DB table.

8. **Vector DB** — Required for: semantic search over training materials, AI persona simulation context, and NL-to-SQL/data queries for the store chatbot.

---

## Project Info

- **Institution:** National University of Computer and Emerging Sciences, Islamabad (FAST-NUCES)
- **Department:** Data Science
- **Session:** 2022–2026
- **Team:** Taha Bin Tariq (22I-2014), Bilal Fazal (22I-2035), Ibrahim Ali (22I-1872)
- **Supervisor:** Ms. Kanza Hamid
- **Report Date:** October 2025
