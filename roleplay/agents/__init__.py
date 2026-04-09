"""
Multi-agent roleplay framework.
"""
from roleplay.agents.base import AgentContext, AgentResult, BaseAgent
from roleplay.agents.persona_agent import PersonaAgent
from roleplay.agents.analyst_agent import AnalystAgent
from roleplay.agents.performance_agent import PerformanceAgent
from roleplay.agents.eq_agent import EQAgent
from roleplay.agents.knowledge_agent import KnowledgeAccuracyAgent
from roleplay.agents.objection_agent import ObjectionInjectionAgent
from roleplay.agents.adaptive_agent import AdaptiveDifficultyAgent
from roleplay.agents.replay_agent import ReplayAgent

__all__ = [
    "AgentContext", "AgentResult", "BaseAgent",
    "PersonaAgent", "AnalystAgent", "PerformanceAgent",
    "EQAgent", "KnowledgeAccuracyAgent",
    "ObjectionInjectionAgent", "AdaptiveDifficultyAgent",
    "ReplayAgent",
]
