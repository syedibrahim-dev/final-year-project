# SalesForge

AI-powered sales training & automation SaaS platform.
**Stack:** FastAPI (Python) + Vite/React + TailwindCSS | MySQL (SQLAlchemy ORM) | ChromaDB (vectors) | Ollama (local LLMs) | APScheduler (background jobs)

## Architecture

```
main.py                    ← FastAPI entry point (uvicorn target)
config/settings.py         ← Pydantic BaseSettings (.env loaded automatically)
routes/                    ← API routers: auth, user, organization, content, mcq, chatbot, roleplay, marketing
models/                    ← SQLAlchemy ORM models (User, Organization, MCQ, Roleplay, Marketing, etc.)
schemas/                   ← Pydantic request/response schemas
services/                  ← Business logic (roleplay_service, marketing_service, mcq_service, knowledge_chatbot, rag_service, image_service)
rag/                       ← RAG pipeline: embeddings, vectorstore (ChromaDB), retriever, pipeline
roleplay/                  ← AI roleplay engine: prompts, LLM client, evaluator, NLP evaluator
utils/                     ← database.py (engine, SessionLocal, Base, init_db), security.py, dependencies.py
client/                    ← Vite + React frontend (src/pages/, src/utils/)
```

## Common Commands

```bash
# Backend (run from project root, venv activated)
uvicorn main:app --reload --port 8000      # Dev server
python -m pytest                            # Run tests
# No requirements.txt yet — install deps via: pip install fastapi sqlalchemy pymysql pydantic-settings chromadb apscheduler

# Frontend (run from client/)
npm run dev                                 # Vite dev server (port 5173)
npm run build                               # Production build
npm run preview                             # Preview production build

# Services
ollama serve                                # Start Ollama LLM server (required for MCQ, roleplay, chatbot)
# MySQL must be running on localhost:3306 with database salesforge_db
```

**API docs:** http://localhost:8000/docs | **Health:** http://localhost:8000/health

## Code Conventions

- **Routes** register routers with NO `/api` prefix — paths are at root level (e.g., `/auth/login`, `/content/upload`)
- **DB sessions** use `Depends(get_db)` in route handlers; never create sessions manually in routes
- **Models** inherit from `Base` (in `utils/database.py`) and auto-create tables on startup via `init_db()`
- **Settings** accessed via `from config.settings import settings` — add new config fields to `Settings` class with `.env` fallback
- **LLM models** are configured per-feature: `LOCAL_LLM_MODEL` (chatbot), `MCQ_LLM_MODEL` (quizzes), `ROLEPLAY_LLM_MODEL` (simulations)
- **Frontend pages** are single-file JSX components in `client/src/pages/` — no nested component directories
- **Imports** in Python: stdlib → third-party → local; `compat_patch` MUST remain the first import in `main.py`

## Gotchas & Warnings

- **`compat_patch.py` must be imported first** in `main.py` — it patches pydantic.v1 for Python 3.14+ compatibility with ChromaDB. Moving or removing this import will break ChromaDB initialization.
- **Route registration is fault-tolerant** — `main.py` catches import errors per-route and continues. If a route silently fails to register, check the startup console logs for `❌ Failed to import` messages.
- **MySQL, not PostgreSQL** — despite `salesforge.md` mentioning PostgreSQL, the actual codebase uses `mysql+pymysql`. Don't introduce PostgreSQL-specific SQL or drivers.
- **No migration tool** — tables are created via `Base.metadata.create_all()`. Schema changes to existing columns require manual `ALTER TABLE` or adding Alembic; prefer adding Alembic over raw SQL.
- **ChromaDB directories** (`chroma_db/`, `chroma_data/`) are gitignored and auto-created on startup. Don't commit them.
- **Image generation** depends on an external Colab FLUX API via ngrok URL in settings — this URL changes on every Colab restart. Check `IMAGE_GEN_URL` if image generation fails.
- **APScheduler** runs in-process — if the FastAPI server restarts, scheduled post publishing resets. No persistent job queue exists yet.
- **CORS whitelist** is hardcoded in `main.py` for `localhost:5173` and `localhost:3000`. Add new origins there when deploying.
- **Frontend** uses both `main.jsx` (Vite entry) and legacy `index.js` — the Vite entry point is `main.jsx`.

## Git & Workflow

- Keep `.env` out of version control (gitignored); use `.env.txt` as the shareable example template
- Commit message format: `[module] brief description` (e.g., `[roleplay] add TTS mute toggle`)

## Pointers

- For project requirements and module specs, see `salesforge.md`
- For roleplay implementation details, see `roleplay_implementation_plan.md`
- For roleplay engine internals (prompts, evaluation, NLP), see `roleplay/`
- For RAG pipeline (embeddings, chunking, retrieval), see `rag/`
- For database models and relationships, see `models/__init__.py`
- For auth and RBAC logic, see `routes/auth.py` and `utils/security.py`
- For environment config options, see `config/settings.py`
