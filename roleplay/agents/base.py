"""
Base classes for the multi-agent roleplay framework.
Provides AgentContext (shared input), AgentResult (output), and BaseAgent (interface).
"""
from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Shared data containers ──────────────────────────────────────────

@dataclass
class AgentContext:
    """
    Immutable context bundle passed to every agent on each turn.
    The orchestrator builds this once per message and fans it out.
    """
    # Core conversation data
    persona: Any                            # RoleplayPersona ORM object (or snapshot)
    messages: List[Any]                     # List[RoleplayMessage] history so far
    trainee_message: str                    # The latest trainee message text
    org_id: Optional[int] = None            # Organization ID (for RAG lookups)
    document_context: str = ""              # Pre-retrieved RAG text (filled by orchestrator)

    # Session metadata
    session_id: Optional[int] = None
    total_message_count: int = 0            # Running count of messages in session
    difficulty: str = "intermediate"

    # Cross-agent communication
    previous_results: Dict[str, AgentResult] = field(default_factory=dict)

    # Analyst cache (persisted between turns)
    cached_stage_info: Optional[Dict[str, Any]] = None

    # ── New agent fields ──
    # Set by ObjectionInjectionAgent, read by PersonaAgent
    objection_directive: Optional[str] = None
    # Set by AdaptiveDifficultyAgent, read by PersonaAgent
    difficulty_modifier: Optional[str] = None
    # Rolling EQ scores for trend tracking (persisted via session agent_cache)
    eq_scores: List[float] = field(default_factory=list)
    # Set by GuardrailAgent, read by PersonaAgent
    guardrail_redirect: Optional[str] = None


@dataclass
class AgentResult:
    """Standard output from any agent."""
    agent_name: str
    data: Dict[str, Any]
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


# ── Abstract base ────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    All roleplay agents inherit from this.
    Subclasses must implement `name`, `build_prompt`, and `run`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier, e.g. 'persona', 'analyst'."""
        ...

    @abstractmethod
    def build_prompt(self, ctx: AgentContext) -> Dict[str, str]:
        """
        Return {"system": "...", "user": "..."} ready for the LLM.
        """
        ...

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult:
        """Execute the agent and return structured result."""
        ...

    # ── Helpers available to all agents ──────────────────────────────

    def _timed_run(self, fn, *args, **kwargs) -> tuple:
        """
        Wrap *fn* so we capture wall-clock latency.
        Returns (result, latency_ms).
        """
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        latency = (time.perf_counter() - t0) * 1000
        return result, latency

    def _make_result(self, data: dict, latency_ms: float = 0.0,
                     success: bool = True, error: str = None) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            data=data,
            latency_ms=round(latency_ms, 1),
            success=success,
            error=error,
        )

    def _format_transcript(self, messages: list, max_turns: int = 20) -> str:
        """Build a plain-text transcript for prompts (recent window)."""
        recent = messages[-max_turns:] if len(messages) > max_turns else messages
        lines = []
        for m in recent:
            # Support both ORM objects (RoleplayMessage) and plain dicts
            if hasattr(m, "sender"):
                sender = m.sender
            else:
                sender = m.get("sender", "unknown") if isinstance(m, dict) else "unknown"

            if hasattr(m, "message_text"):
                text = m.message_text
            else:
                text = m.get("text", "") if isinstance(m, dict) else ""

            label = "Trainee" if sender == "trainee" else "Customer"
            lines.append(f"{label}: {text}")
        return "\n".join(lines)
