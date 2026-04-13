<p align="center">
  <h1 align="center">SalesForge AI — Intelligent Sales Training Platform</h1>
  <p align="center">
    An AI-powered platform that trains sales professionals through interactive roleplay simulations, document-grounded MCQ assessments, and real-time performance analytics — all running on local LLMs via Ollama with GPU acceleration.
  </p>
</p>

---

## Table of Contents

- [Project Overview](#project-overview)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Core Modules](#core-modules)
  - [1. AI Roleplay Simulation Module](#1-ai-roleplay-simulation-module)
  - [2. MCQ Generation Module](#2-mcq-generation-module)
  - [3. RAG Engine](#3-rag-retrieval-augmented-generation-engine)
  - [4. Knowledge Chatbot](#4-knowledge-chatbot)
  - [5. Content Management](#5-content-management)
  - [6. Organization & User Management](#6-organization--user-management)
  - [7. Performance Dashboard & Analytics](#7-performance-dashboard--analytics)
- [Evaluation Metrics](#evaluation-metrics)
- [Models & Training Data](#models--training-data)
- [Frontend Pages](#frontend-pages)
- [Setup & Installation](#setup--installation)
- [API Endpoints](#api-endpoints)

---

## Project Overview

**SalesForge AI** is a comprehensive AI-driven sales training platform designed to help organizations upskill their sales teams. It provides:

- **Realistic AI Roleplay Simulations** — trainees practice selling to AI-powered customer personas with company intelligence (industry, tech stack, buying stage) that adapt in real-time based on performance, with guardrails against prompt injection and off-topic input.
- **Three-Engine Analysis** — Engine A (DeBERTa NLI) for intent/objection detection, Engine B (Emotion-RoBERTa) for empathy/pressure analysis, Engine C (Ollama LLM) for reasoning, stage tracking, and coaching.
- **Real-Time Conversion Prediction** — SalesRLAgent (PPO reinforcement learning model trained on 1.2M conversations) predicts deal probability live during conversations.
- **LSTM Conversation Risk Model** — A 2-layer LSTM trained on 1,000 SaaS conversations predicts deal failure risk from the sequence of per-turn classifier outputs (27-dim feature vectors), providing trajectory-aware risk scoring that complements per-turn classifiers.
- **Document-Grounded MCQ Assessments** — quizzes generated from the organization's own training materials using RAG, ensuring assessments test real product knowledge.
- **Intelligent Knowledge Chatbot** — employees can ask questions about their training content and receive accurate, RAG-backed answers.
- **Comprehensive Analytics** — detailed performance tracking across roleplay sessions and MCQ attempts with per-category scoring and trend analysis.
- **Voice Roleplay Mode** — Whisper-based speech-to-text (via faster-whisper) with real-time voice analytics (WPM, filler words, pauses, confidence) plus browser TTS for AI responses.
- **Three Interaction Modes** — Chat (traditional text + full analytics panels), Avatar (animated SVG face-to-face driven by classifier outputs), and Voice (Whisper STT + voice metrics).

All AI inference runs **locally via Ollama** (Llama 3.1 8B, Q8_0 quantisation) with GPU/CPU hybrid offloading (22 GPU layers + 11 CPU layers), ensuring data privacy and eliminating cloud API costs.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.13, FastAPI |
| **Frontend** | React (Vite), Tailwind CSS |
| **Database** | SQLite (SQLAlchemy ORM) |
| **Vector Database** | ChromaDB (persistent, org-scoped) |
| **LLM Inference** | Ollama (local, GPU/CPU hybrid) — Llama 3.1 8B (Q8_0) |
| **EQ Engine A (Intent)** | DeBERTa NLI (`cross-encoder/nli-deberta-v3-base`) — objection detection, active listening |
| **EQ Engine B (Emotion)** | Emotion-RoBERTa (`j-hartmann/emotion-english-distilroberta-base`) + GoEmotions (`SamLowe/roberta-base-go_emotions`) |
| **Conversion Prediction** | Fine-tuned DistilBERT Outcome Predictor + XGBoost/MLP ensemble |
| **Fine-tuned Classifiers** | 6x DistilBERT-base-uncased (objection, handling, emotion, outcome, state, willingness) |
| **LSTM Risk Model** | 2-layer LSTM (hidden=64, dropout=0.3) — sequence-based conversation risk prediction |
| **Embeddings (RAG)** | Nomic Embed Text (`nomic-embed-text`, 768-dim, Ollama-served) |
| **Embeddings (ML)** | Sentence-Transformers (`all-MiniLM-L6-v2`, 384-dim) for intent similarity + conversion features |
| **NLP Libraries** | spaCy (NER), Transformers (classifiers) |
| **Charting** | D3.js (conversion trends, skill radar, score distributions) |
| **Voice STT** | faster-whisper (`base` model, CTranslate2 int8) — word-level timestamps, WPM, filler detection |
| **Voice TTS** | Web Speech API (browser-native) |
| **Authentication** | JWT (HS256) |
| **Architecture** | Multi-Agent System (9 agents), Three-Engine Pipeline, Two-Stage ML Pipeline (DistilBERT + LSTM), RAG, Modular Pipeline Pattern |

---

## System Architecture

```
+--------------------------------------------------------------+
|                        React Frontend                         |
|  (Login, Dashboard, Roleplay, MCQ, Chatbot, Content Mgmt)    |
+--------------------------------------------------------------+
                              | REST API
+--------------------------------------------------------------+
|                      FastAPI Backend                           |
|  +----------+ +----------+ +--------+ +------------------+   |
|  |  Auth    | | Roleplay | |  MCQ   | |  Content/Chatbot |   |
|  |  Routes  | |  Routes  | | Routes | |     Routes       |   |
|  +----------+ +----------+ +--------+ +------------------+   |
+--------------------------------------------------------------+
|  +--------------------+  +--------------------------+         |
|  | Agent Orchestrator  |  |     MCQ Pipeline         |        |
|  | (9 Agents +         |  |  Stem -> Distractor ->   |        |
|  |  3-Engine Pipeline) |  |  Filter -> Validator     |        |
|  +--------------------+  +--------------------------+         |
+--------------------------------------------------------------+
|  +---------------+  +----------------+  +----------------+    |
|  | RAG Pipeline  |  | NLP Evaluator  |  | Transformer    |    |
|  | (ChromaDB)    |  | (Tier 1 + 2)   |  | Engines A + B  |    |
|  +---------------+  +----------------+  +----------------+    |
|  +-----------------------------+  +------------------------+  |
|  | Two-Stage ML Pipeline       |  | Voice Analytics        |  |
|  | 6x DistilBERT → LSTM Risk  |  | faster-whisper (STT)   |  |
|  +-----------------------------+  +------------------------+  |
+--------------------------------------------------------------+
|  +--------------------------+  +---------------------------+  |
|  | SQLite (SQLAlchemy ORM)  |  | ChromaDB (Vector Store)   |  |
|  +--------------------------+  +---------------------------+  |
+--------------------------------------------------------------+
           |                              |
  Ollama (Local LLM Server)     SalesRLAgent Subprocess
  Llama 3.1 8B (GPU)            PPO + BGE-M3 (CPU)
```

---

## Core Modules

---

### 1. AI Roleplay Simulation Module

The roleplay module is the **primary module** of SalesForge AI. It creates realistic, interactive sales conversation simulations where trainees practice selling to AI-powered customer personas. The system is built on a **Multi-Agent Architecture** with a **Three-Engine Analysis Pipeline** that coordinates 9 specialized agents.

#### 1.1 Three-Engine Architecture

| Engine | Model | Purpose | Latency |
|--------|-------|---------|---------|
| **Engine A** | DeBERTa NLI (`cross-encoder/nli-deberta-v3-base`) | Intent analysis — objection detection, response classification, active listening | ~15-30ms (CPU) |
| **Engine B** | Emotion-RoBERTa + GoEmotions | Emotion analysis — empathy detection, pressure level classification | ~10-20ms (CPU) |
| **Engine C** | Llama 3.1 8B via Ollama | LLM reasoning — persona response generation, stage tracking, coaching hints | ~3-5s (GPU) |

#### 1.2 The 9 Specialized Agents

**Per-message agents (run every turn):**

| # | Agent | Engine | LLM Calls | Purpose |
|---|-------|--------|-----------|---------|
| 1 | **Guardrail Agent** | Rules | 0 | Input validation — blocks prompt injection, inappropriate content, off-topic messages, character-breaking attempts |
| 2 | **EQ Agent** | A + B | 0 | Emotional intelligence scoring using DeBERTa NLI (objection detection, active listening) + Emotion-RoBERTa (empathy, pressure level). Outputs weighted 0-100 EQ score. |
| 3 | **Knowledge Accuracy Agent** | RAG | 0 | Fact-checks trainee claims against uploaded company documents via ChromaDB similarity search. Flags unverified claims. |
| 4 | **Objection Injection Agent** | Rules | 0 | Decides when the AI customer should raise an objection based on stage, difficulty, and history. |
| 5 | **Adaptive Difficulty Agent** | Rules | 0 | Adjusts persona warmth/resistance based on trainee EQ scores and conversation stage. |
| 6 | **Persona Agent** | C | 1 | Generates the AI customer's in-character reply incorporating personality, company context, RAG documents, objection directives, and difficulty modifiers. |
| 7 | **Analyst Agent** | C | 1 (skip-N) | Detects sales stage and generates coaching hints. Uses skip-every-N to reduce LLM calls; falls back to NLP heuristic when skipped. |

**Async agent (non-blocking):**

| # | Agent | Engine | Purpose |
|---|-------|--------|---------|
| 8 | **SalesRLAgent** | PPO RL | Predicts deal conversion probability using a reinforcement learning model (trained on 1.2M conversations). Runs in a persistent subprocess, never blocks the response. |

**Post-session agents (run once after session ends):**

| # | Agent | Engine | Purpose |
|---|-------|--------|---------|
| 9 | **Performance Agent** | C | Deep LLM evaluation — category scores, summary, strengths, improvements, coaching tip, per-stage feedback. |
| 10 | **Replay Agent** | C | Annotated transcript — turning points, missed signals, strong/weak moments, alternative response suggestions. |
| 11 | **SalesRLAgent (Full)** | PPO RL | Complete turn-by-turn conversion trajectory, turning point analysis, data-driven coaching suggestions. |

#### 1.3 Company Intelligence Layer

Each persona includes a `company_context` that makes the roleplay closer to real B2B sales:

| Field | Example |
|-------|---------|
| `industry` | Manufacturing |
| `company_size` | 200-500 employees |
| `role` | Operations Manager |
| `tech_stack` | Microsoft 365, SAP, Excel |
| `business_problems` | Rising costs, manual tracking, audit pressure |
| `buying_stage` | Evaluation — comparing vendors |
| `budget_authority` | Controls $20K/year, CFO for more |
| `current_solution` | Free/low-cost tools cobbled together |
| `urgency` | Medium — next audit in 6 months |

The AI customer references this context naturally during conversation (e.g., "We're a 250-person manufacturing company" or "Our next audit is in six months").

#### 1.4 Document-Grounded Roleplay (RAG Integration)

When an organization has uploaded training documents (product brochures, playbooks, etc.), the roleplay becomes **document-grounded**:

- The **Persona Agent** uses document context to ask questions grounded in real company materials.
- The **Knowledge Accuracy Agent** fact-checks trainee claims against these documents in real-time.
- Each persona has a `rag_probing_style` (curious, challenge, gotcha) controlling how aggressively the AI customer probes product knowledge.

#### 1.5 Guardrails

The **Guardrail Agent** validates every trainee message before it reaches the AI:

| Check | Action | Example |
|-------|--------|---------|
| Empty / too short | Block | "Could you say that again?" |
| Too long (>3000 chars) | Block | "Can you break that down?" |
| Prompt injection | Block | "ignore your instructions..." |
| Character breaking | Block | "are you an AI?" |
| Inappropriate content | Block | "Let's keep this professional." |
| Keyboard mashing | Block | "asdfjkl;" |
| Off-topic (soft) | Redirect | PersonaAgent steers back to business |

#### 1.6 Real-Time Features

- **Stage Tracking**: LLM-detected sales stage (Opening, Discovery, Presentation, Objection, Closing) with progress bar.
- **Coaching Hints**: Context-aware tips from the Analyst Agent (e.g., "Ask about their timeline to move toward closing").
- **EQ Score**: Transformer-powered emotional intelligence badge (empathetic/neutral/pushy) with empathy and pressure metrics.
- **Deal Probability**: SalesRLAgent conversion gauge with trend chart (D3).
- **LSTM Risk Score**: Sequence-based deal failure prediction with trend (rising/falling/stable), updated every turn.
- **Deal Intelligence Panel**: 5 inline metrics — Deal Confidence, Momentum, Buyer State, Willingness, LSTM Risk.
- **Fact-Check Alerts**: Flagged claims when trainee makes unverified statements.
- **Voice Analytics**: Whisper-powered WPM, filler word ratio, pause analysis, confidence scoring with coaching feedback.
- **Three Modes**: Chat (text + full analytics), Avatar (animated SVG persona), Voice (Whisper STT + voice metrics).

#### 1.7 Post-Session Evaluation

When a session ends, three agents run:

1. **Performance Agent** — Category scores (5 x 0-20), summary, strengths, improvements, coaching tip, per-stage analysis
2. **Replay Agent** — Annotated transcript with turning points, missed signals, alternative responses
3. **SalesRLAgent** — Full turn-by-turn conversion trajectory with turning point analysis

These are blended with the **NLP Evaluator** scores: `Final = 60% NLP + 40% LLM` per category.

#### 1.8 Persona System

8 pre-built personas covering different difficulty levels:

| Persona | Difficulty | Key Challenge |
|---------|------------|---------------|
| The Friendly Prospect | Beginner | Easy rapport, needs team buy-in |
| The Budget Hunter | Beginner | Price-focused, demands ROI proof |
| The Busy Executive | Intermediate | Short attention span, wants efficiency |
| The Detail Seeker | Intermediate | Deep technical questions |
| The Skeptic | Advanced | Evidence-based, trusts nothing |
| The Gatekeeper | Intermediate | Not the decision maker |
| The Competitor Loyalist | Advanced | Happy with current vendor |
| The Overwhelmed Owner | Beginner | Non-technical, needs simplicity |

Each persona has: personality traits (5 dimensions), trigger topics, common objections, company context, scenario brief, tone, and difficulty level.

---

### 2. MCQ Generation Module

Generates high-quality, document-grounded multiple-choice questions using a **4-stage pipeline**:

```
RAG Retrieval -> Stem Generator (LLM) -> Distractor Generator (LLM)
    -> Distractor Filter (rules) -> MCQ Validator (embeddings + LLM + rules)
```

- **Diversity Enforcement**: Levenshtein similarity filtering, anti-duplication prompts
- **3-Dimensional Validation**: Content relevance (embeddings), answer correctness (LLM-as-judge), question clarity (rules)
- **Complete Test System**: Test creation, MCQ practice mode, attempt tracking with analytics

---

### 3. RAG (Retrieval-Augmented Generation) Engine

| Component | Responsibility |
|-----------|---------------|
| **Embedding Manager** | Nomic Embed Text (`nomic-embed-text`, 768-dim, Ollama-served) |
| **Vector Store** | ChromaDB with org-scoped collections, 500-token chunks with 50 overlap |
| **Retriever** | Similarity search with distance-based ranking |

Used by: Roleplay (persona knowledge + fact-checking), MCQ (question generation), Chatbot (Q&A).

---

### 4. Knowledge Chatbot

RAG-powered interactive Q&A with training materials. Streaming responses via Ollama, conversational memory, source citations.

---

### 5. Content Management

Document upload (PDF, TXT), content library management, semantic search, version tracking. Multi-format support including URL scraping and media transcription.

---

### 6. Organization & User Management

Multi-tenant architecture with isolated data per organization. Role-based access (Admin/Employee), invite system, JWT authentication.

---

### 7. Performance Dashboard & Analytics

D3.js-powered analytics dashboard with:
- **Overview**: MCQ/Roleplay averages, practice time, improvement trends, strongest/weakest skills
- **MCQ Tab**: Score distribution chart, progress trend, attempts table
- **Roleplay Tab**: Score trend chart, skill radar (5-axis), per-persona performance, category progress bars

---

## Evaluation Metrics

### Roleplay Evaluation — Hybrid 3-Tier Architecture

| Tier | Method | What It Produces |
|------|--------|-----------------|
| **Tier 1** | Rule-based NLP (questions, keywords, flow, dynamics) | Per-category scores (0-20 x 5) |
| **Tier 2** | ML/NLP (sentiment trajectory, named entities, dialogue acts) | Modifier scores adjusting Tier 1 |
| **Tier 3** | LLM (Performance Agent + Replay Agent) | Qualitative feedback, coaching, annotated transcript |

**Final Score** = 60% NLP + 40% LLM per category (max 100).

### MCQ Evaluation — 6-Criteria Weighted Rubric

Relevance (25%), Correctness (25%), Stage Fit (15%), Persona Fit (15%), Distractor Plausibility (15%), Independence (5%). Each scored 1-5, normalized to 0-100.

---

## Models & Training Data

SalesForge AI uses **15 AI components** spanning pre-trained transformer models, 6 domain fine-tuned DistilBERT classifiers, a 2-layer LSTM sequence model, a traditional ML ensemble, and Whisper-based voice analytics — trained across **9 distinct datasets**.

### Pre-trained Models (Off-the-shelf)

| # | Component | Model | Source | Use in System |
|---|-----------|-------|--------|---------------|
| 1 | **LLM** | `llama3.1:8b-instruct-q8_0` | Meta (Ollama) | Persona responses, MCQ generation, evaluation, coaching, chatbot |
| 2 | **RAG Embeddings** | `nomic-embed-text` (768-dim) | Nomic AI (Ollama) | RAG retrieval (ChromaDB), MCQ content validation |
| 2b | **ML Embeddings** | `all-MiniLM-L6-v2` (384-dim) | Sentence-BERT | Intent similarity (active listening), conversion feature extraction |
| 3 | **NLI Classifier** | `cross-encoder/nli-deberta-v3-base` | DeBERTa v3 | Zero-shot objection detection, active listening (Engine A) |
| 4 | **Emotion 7-class** | `j-hartmann/emotion-english-distilroberta-base` | DistilRoBERTa | Emotion analysis (Engine B) |
| 5 | **Emotion 28-class** | `SamLowe/roberta-base-go_emotions` | RoBERTa | Fine-grained empathy detection (Engine B) |
| 6 | **RAG Re-ranker** | `ms-marco-MiniLM-L-6-v2` | Cross-Encoder | Chunk re-ranking, Knowledge Agent fact-checking |
| 7 | **Voice STT** | `faster-whisper` (base, int8) | OpenAI Whisper via CTranslate2 | Speech-to-text with word-level timestamps, WPM, filler detection, confidence scoring |

### Fine-tuned DistilBERT Classifiers (Domain-specific)

All 6 classifiers use **DistilBERT-base-uncased** (67M params) as the base model, fine-tuned with weighted cross-entropy loss for class imbalance.

#### C1 — Objection Detection (92.1% accuracy)

| Detail | Value |
|--------|-------|
| **Task** | 8-class objection type classification |
| **Labels** | `objection_price`, `objection_timing`, `objection_authority`, `objection_need`, `objection_trust`, `objection_value`, `objection_fairness`, `not_objection` |
| **Training Data** | 4,181 examples |
| **Datasets** | CaSiNo (4,119) + synthetic B2B (62) |
| **Citation** | Chawla et al., "CaSiNo: A Corpus of Campsite Negotiation Dialogues", NAACL 2021 |
| **Ensemble** | Runs alongside DeBERTa NLI; fine-tuned takes priority when confidence > 0.6 |

#### C2 — Response Handling Quality (82.7% accuracy)

| Detail | Value |
|--------|-------|
| **Task** | 3-class response quality scoring |
| **Labels** | `resolved`, `deflected`, `escalated` |
| **Training Data** | 795 examples |
| **Datasets** | CaSiNo objection-response pairs (765) + synthetic B2B (30) |
| **Input Format** | `"Concern: {text} Response: {text}"` |
| **Citation** | CaSiNo (NAACL 2021) — same source as C1 |

#### C3 — Emotion + Pressure Detection (84.4% accuracy)

| Detail | Value |
|--------|-------|
| **Task** | 8-class emotion/pressure classification |
| **Labels** | `positive`, `negative`, `neutral`, `empathetic`, `anxious`, `consultative`, `urgent`, `demanding` |
| **Training Data** | 25,000 examples from 5 independent sources |
| **Datasets** | GoEmotions — 10K (Demszky et al., ACL 2020), dair-ai/emotion — 4K (Saravia et al., EMNLP 2018), ESConv — 3.5K (Liu et al., ACL 2021), DeepMost SaaS — 1.1K, Augmented pressure — 6.4K (Gong Labs research-informed) |
| **Citations** | Demszky et al., "GoEmotions: A Dataset of Fine-Grained Emotions", ACL 2020; Saravia et al., "CARER: Contextualized Affect Representations", EMNLP 2018; Liu et al., "Towards Emotional Support Dialog Systems", ACL 2021 |
| **Key Result** | Pressure types (consultative/demanding/urgent) achieve 100% F1; empathetic 96% F1 |

#### C4 — Outcome Predictor (81.3% accuracy)

| Detail | Value |
|--------|-------|
| **Task** | Binary conversion prediction (`converted` / `failed`) |
| **Training Data** | 3,425 examples |
| **Datasets** | DeepMost SaaS (1,000) + CraigslistBargains (2,142) + goendalf666 (283) |
| **Citations** | CraigslistBargains via DialogStudio (Salesforce); goendalf666/sales-conversations (HuggingFace) |
| **Replaces** | SalesRLAgent PPO — 50ms inference vs 5-15s |

#### C5 — Sales State Model (85.1% accuracy)

| Detail | Value |
|--------|-------|
| **Task** | 6-class buyer state classification |
| **Labels** | `interest`, `trust`, `objection`, `evaluation`, `decision`, `drop_off_risk` |
| **Training Data** | 18,236 examples with context windows (utterance + 2 prior turns) |
| **Datasets** | DeepMost SaaS semantically relabeled (12,409) + CraigslistBargains (5,118) + Claude Opus-labeled B2B conversations (709, 5x weighted) |
| **Data Engineering** | Intelligent labeling (4-signal conversation-arc reasoning: content + position + outcome + style), context windowing (3-turn), minority class oversampling (drop_off_risk 44→500, trust 429→500), `comparison` merged into `evaluation`, data leakage prevention (Claude sets 3-4 train only, sets 1-2 validation only) |
| **Citations** | DeepMost Innovations SaaS dataset (HuggingFace); CraigslistBargains via DialogStudio |

#### C6 — Willingness Predictor (82.6% accuracy)

| Detail | Value |
|--------|-------|
| **Task** | 3-class buyer engagement classification |
| **Labels** | `engaged`, `neutral`, `disengaged` |
| **Training Data** | 13,148 examples with context windows |
| **Datasets** | DeepMost SaaS intelligently relabeled (12,413) + Claude Opus-labeled B2B (735, 5x weighted) |
| **Data Engineering** | Same as C5 — intelligent labeling (conversation-arc reasoning), context windowing, disengaged oversampled (61→500) |
| **Key Result** | Disengaged detection: 100% precision & recall |

### LSTM Conversation Risk Model (Two-Stage ML Pipeline)

The LSTM model represents a **second-stage ML architecture** that operates on top of the 6 DistilBERT classifiers, providing trajectory-aware risk prediction rather than per-turn classification.

| Detail | Value |
|--------|-------|
| **Architecture** | 2-layer LSTM (hidden_dim=64, dropout=0.3) + linear classifier |
| **Input** | 27-dimensional feature vector per turn (6 state + 3 willingness + 7 objection + 8 emotion + 1 position + 1 resolved + 1 speaker) |
| **Task** | Binary risk prediction — P(deal failure) from partial conversation sequences |
| **Training Data** | 1,000 SaaS sales conversations (DeepMost), ~12K partial sequences |
| **Training Method** | Partial sequence training (turns 1..N at each step), position-weighted loss (later turns weighted higher), 30 epochs, Adam optimizer |
| **Sequence Length** | Max 30 turns, zero-padded with pack_padded_sequence |
| **Results** | 58.3% accuracy, **0.65 AUC-ROC**, late-turn accuracy **70.6%** |
| **Inference** | Per-turn encoding + full sequence prediction, <5ms on CPU |
| **Trend Detection** | Compares current risk to risk at 2 turns ago; threshold 0.08 for rising/falling |

**Two-Stage Pipeline Design:**
```
Turn N → [C1: State] [C2: Willingness] [C4: Objection] [C3: Emotion] → 27-dim vector
                                                                              ↓
Sequence [Turn 1, ..., Turn N] → LSTM → P(deal failure) + trend (rising/falling/stable)
```

This is architecturally distinct from the DistilBERT classifiers: classifiers extract per-turn features, the LSTM learns **conversation trajectories**. A conversation can have good per-turn signals (engaged buyer, no objections) but a failing trajectory (engagement dropping over time) — the LSTM catches this.

### Traditional ML — Conversion Predictor Ensemble

| Detail | Value |
|--------|-------|
| **Models** | XGBoost (300 estimators) + MLP ensemble |
| **Features** | 58 total: 28 keyword features + 30 PCA-compressed embeddings |
| **Based on** | SalesRLAgent (arXiv:2503.23303) |

### Frontier Model Validation

Classifiers validated against **Claude Opus-labeled B2B conversations** (10 conversations, 60 turns) — data never seen during training.

| Dimension | Agreement with Claude |
|-----------|----------------------|
| Emotion | **91.7%** |
| Pressure | 73.3% |
| Outcome | 60.0% |
| Objection | 56.7% |
| Willingness | 48.3% |
| Sales State | 31.7% |
| **Overall** | **57.8%** |

### Training Dataset Summary

| # | Dataset | Source | Size | Used By | Citation |
|---|---------|--------|------|---------|----------|
| 1 | **CaSiNo** | NAACL 2021 | 1,030 dialogues | C1, C2 | Chawla et al. (2021) |
| 2 | **GoEmotions** | ACL 2020 | 43K comments | C3 | Demszky et al. (2020) |
| 3 | **dair-ai/emotion** | EMNLP 2018 | 16K examples | C3 | Saravia et al. (2018) |
| 4 | **ESConv** | ACL 2021 | 25K conversations | C3 | Liu et al. (2021) |
| 5 | **DeepMost SaaS** | HuggingFace | 1,000 conversations | C3, C4, C5, C6 | DeepMost Innovations (2025) |
| 6 | **CraigslistBargains** | DialogStudio | 3,946 dialogues | C4, C5 | He et al. via DialogStudio |
| 7 | **goendalf666/sales** | HuggingFace | 3,411 conversations | C4 | Community dataset |
| 8 | **gwenshap/sales-transcripts** | HuggingFace | 50 real transcripts | C5 | Community dataset |
| 9 | **Claude Opus B2B** | Generated | 20 conversations | C5, C6 (train), validation | Knowledge distillation |

### Why Multi-Source Over Synthetic Data

We deliberately chose multi-source academic + real-world datasets over purely synthetic (LLM-generated) data:

1. **Distributional diversity** — Each dataset captures different conversation dynamics (negotiation, emotional support, sales). A single synthetic source inherits one LLM's output distribution.
2. **Peer-reviewed provenance** — CaSiNo, GoEmotions, ESConv, dair-ai/emotion are all published at top NLP venues (NAACL, ACL, EMNLP). This gives the committee verifiable, citable training sources.
3. **Non-circular validation** — Training on academic data and validating against Claude Opus labels proves the classifiers generalize beyond their training distribution. Synthetic-only would risk teaching and testing the same patterns.
4. **Complementary coverage** — GoEmotions covers general emotion, ESConv covers empathetic dialogue, CaSiNo covers negotiation strategy, DeepMost covers B2B sales specifically. No single dataset covers all dimensions.

---

## Frontend Pages

| Page | File | Description |
|------|------|-------------|
| **Login** | `Login.jsx` | JWT-based authentication |
| **Register Organization** | `RegisterOrg.jsx` | Create organization with admin account |
| **Roleplay Personas** | `RoleplayPersonas.jsx` | Browse personas with Chat/Voice buttons |
| **Roleplay Chat** | `RoleplayChat.jsx` | Live chat with stage tracking, coaching hints, EQ badge, conversion gauge, D3 trend chart, voice mode |
| **Roleplay Feedback** | `RoleplayFeedback.jsx` | Post-session: scores, coaching, replay annotations, conversion trajectory, alternative responses |
| **MCQ Generator** | `MCQGenerator.jsx` | Generate MCQs from training materials |
| **MCQ Test Creator** | `MCQTestCreator.jsx` | Create assessments from questions |
| **MCQ Practice** | `MCQPractice.jsx` | Take tests with real-time feedback |
| **Content Upload** | `ContentUpload.jsx` | Upload PDF, TXT, URL, media |
| **Content Manager** | `ContentManager.jsx` | Manage training content |
| **Content Retriever** | `ContentRetriever.jsx` | Semantic search |
| **Knowledge Chatbot** | `KnowledgeChatbot.jsx` | RAG-powered Q&A |
| **Performance Dashboard** | `PerformanceDashboard.jsx` | D3 analytics (scores, trends, radar) |

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai/) installed locally
- NVIDIA GPU recommended (6GB+ VRAM for full GPU offloading)

### 1. Install Ollama Models

```bash
ollama pull llama3.1:8b-instruct-q4_K_M
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows

# Install Python dependencies
pip install fastapi uvicorn sqlalchemy pymysql pydantic-settings
pip install langchain langchain-community langchain-ollama
pip install chromadb sentence-transformers pypdf
pip install spacy transformers torch
pip install faster-whisper  # Voice analytics (Whisper STT)
python -m spacy download en_core_web_sm

# Configure database (SQLite — no external DB server needed)
# Edit config/settings.py or create .env file

# Initialize database and seed personas
python migrate_and_seed.py
python seed_personas.py

# Start backend
PYTHONIOENCODING=utf-8 uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd client
npm install
npm run dev
```

### 4. SalesRLAgent Setup (Optional)

Requires a separate Python 3.11 environment with the `deepmost` library:

```bash
# In a separate venv (Python 3.11)
pip install deepmost
# Configure SALESRL_PYTHON path in config/settings.py
```

---

## API Endpoints

| Module | Endpoint | Method | Description |
|--------|----------|--------|-------------|
| **Auth** | `/auth/register` | POST | Register organization + admin |
| **Auth** | `/auth/login` | POST | Login and receive JWT token |
| **Roleplay** | `/roleplay/personas` | GET | List available personas |
| **Roleplay** | `/roleplay/sessions/start` | POST | Start new roleplay session |
| **Roleplay** | `/roleplay/sessions/{id}/message` | POST | Send message, get AI response + all agent data + LSTM risk |
| **Roleplay** | `/roleplay/sessions/{id}/voice-message` | POST | Upload audio, Whisper transcription + voice analytics + full pipeline |
| **Roleplay** | `/roleplay/sessions/{id}/end` | POST | End session, trigger NLP evaluation |
| **Roleplay** | `/roleplay/sessions/{id}/evaluate` | POST | Full LLM + NLP + SalesRL evaluation |
| **Roleplay** | `/roleplay/sessions/{id}/evaluation` | GET | Get evaluation results |
| **Roleplay** | `/roleplay/analytics/user` | GET | User performance analytics |
| **Roleplay** | `/roleplay/analytics/org` | GET | Organization analytics (admin) |
| **MCQ** | `/mcq/generate` | POST | Generate MCQs for a topic |
| **MCQ** | `/mcq/tests` | POST | Create a test from questions |
| **MCQ** | `/mcq/tests/{id}/attempt` | POST | Submit a test attempt |
| **Content** | `/content/upload` | POST | Upload training document |
| **Content** | `/content/retrieve` | POST | Search content via RAG |
| **Chatbot** | `/chatbot/chat` | POST | Send message to knowledge chatbot |
| **Users** | `/users/me` | GET | Get current user profile |
| **Org** | `/org/invite` | POST | Generate invite token |

---

<p align="center">
  <b>SalesForge AI</b> — Turning Sales Teams into Closing Machines
</p>
