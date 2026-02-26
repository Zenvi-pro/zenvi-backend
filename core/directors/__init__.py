"""
AI Directors System — backend port.

Directors are meta-agents that analyze video projects, critique them from
different perspectives, interact in debate-style discussions, and produce
actionable editing plans.

Architecture (split):
- Data structures (plan, voting) live here in the backend.
- Read-only analysis tools delegate to the frontend (they need Qt/project state).
- Orchestrator and voting run server-side with LLM calls.
"""

from core.directors.director_agent import Director, DirectorMetadata, DirectorPersonality
from core.directors.director_loader import DirectorLoader
from core.directors.director_plan import DirectorPlan, PlanStep, PlanStepType
from core.directors.director_orchestrator import DirectorOrchestrator

__all__ = [
    "Director",
    "DirectorMetadata",
    "DirectorPersonality",
    "DirectorLoader",
    "DirectorPlan",
    "PlanStep",
    "PlanStepType",
    "DirectorOrchestrator",
]
