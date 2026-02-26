"""
Director Orchestrator — coordinates multiple directors through analysis,
debate, and consensus phases.

Ported from core/src/classes/ai_directors/director_orchestrator.py.
Qt ``thinking_dock`` UI is replaced with an optional *status_callback*.
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import uuid
from typing import Any, Callable, Dict, List, Optional

from logger import log
from core.directors.director_agent import Director, DirectorAnalysis
from core.directors.director_plan import (
    DebateMessage,
    DirectorPlan,
    PlanStep,
    PlanStepType,
)


# Optional callback for streaming status updates to a UI (e.g. WebSocket).
# Signature: (source: str, message: str, phase: str) -> None
StatusCallback = Callable[[str, str, str], None]


class DirectorOrchestrator:
    """
    Orchestrates multiple directors through analysis → debate → synthesis → voting.
    """

    def __init__(
        self,
        directors: List[Director],
        max_debate_rounds: int = 3,
        max_workers: int = 3,
    ):
        self.directors = directors
        self.max_debate_rounds = max_debate_rounds
        self.max_workers = max_workers

    def run_directors(
        self,
        model_id: str,
        task: str,
        tool_executor=None,
        project_data: Optional[Dict[str, Any]] = None,
        status_callback: Optional[StatusCallback] = None,
    ) -> DirectorPlan:
        log.info("Running %d directors for task: %s", len(self.directors), task)
        self.model_id = model_id
        self.tool_executor = tool_executor

        cb = status_callback or (lambda *_: None)

        # Phase 1 — parallel analysis
        cb("Orchestrator", f"Starting analysis with {len(self.directors)} directors...", "Phase 1: Analysis")
        analyses = self._parallel_analysis(project_data or {}, cb)

        # Phase 2 — structured debate
        cb("Orchestrator", "Directors are now debating their findings...", "Phase 2: Debate")
        debate_messages = self._run_debate(analyses, cb)

        # Phase 3 — synthesize consensus plan
        cb("Orchestrator", "Synthesizing consensus plan...", "Phase 3: Synthesis")
        plan = self._synthesize_consensus(task, analyses, debate_messages)
        cb("Orchestrator", f"Generated plan with {len(plan.steps)} steps", "Phase 3: Synthesis")

        # Phase 4 — voting
        cb("Orchestrator", "Directors are voting on each proposed step...", "Phase 4: Voting")
        try:
            from core.directors.director_voting import DirectorVotingPhase

            voting_phase = DirectorVotingPhase(self.directors)
            voting_results = voting_phase.run_voting(plan, analyses, model_id)

            for step in plan.steps:
                for vote in voting_results.get(step.step_id, []):
                    cb(vote.director_name, f"Vote: {vote.vote.value.upper()} — {vote.rationale}", "voting")

            resolutions = voting_phase.resolve_votes(voting_results)
            plan = self._apply_voting_resolutions(plan, voting_results, resolutions)

            cb("Orchestrator", "Voting complete. Plan updated based on director consensus.", "Complete")
        except Exception as e:
            log.error("Voting phase failed: %s", e, exc_info=True)
            cb("Orchestrator", f"Voting phase error: {str(e)[:100]}", "Complete")

        log.info("Generated plan with %d steps (after voting)", len(plan.steps))
        return plan

    # ------------------------------------------------------------------
    # Phase 1
    # ------------------------------------------------------------------

    def _parallel_analysis(
        self,
        project_data: Dict[str, Any],
        cb: StatusCallback,
    ) -> List[DirectorAnalysis]:
        log.info("Phase 1: Parallel analysis with %d directors", len(self.directors))

        for director in self.directors:
            cb(director.name, f"Starting analysis from {director.name} perspective...", "analysis")

        from core.directors.director_tools import get_director_analysis_tools_for_langchain

        analysis_tools = get_director_analysis_tools_for_langchain()
        analyses: List[DirectorAnalysis] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_director = {
                executor.submit(
                    director.analyze_project,
                    self.model_id,
                    analysis_tools,
                    self.tool_executor,
                ): director
                for director in self.directors
            }
            for future in concurrent.futures.as_completed(future_to_director):
                director = future_to_director[future]
                try:
                    analysis = future.result()
                    analyses.append(analysis)
                    log.info("%s: Analysis complete", director.name)
                    cb(director.name, f"Analysis complete: {analysis.analysis_text[:100]}...", "analysis")
                except Exception as e:
                    log.error("%s: Analysis failed: %s", director.name, e, exc_info=True)
                    cb(director.name, f"Analysis failed: {str(e)[:100]}", "analysis")

        return analyses

    # ------------------------------------------------------------------
    # Phase 2
    # ------------------------------------------------------------------

    def _run_debate(
        self,
        analyses: List[DirectorAnalysis],
        cb: StatusCallback,
    ) -> List[DebateMessage]:
        log.info("Phase 2: Running debate (%d rounds)", self.max_debate_rounds)

        debate_messages: List[DebateMessage] = []

        # Seed with initial analyses
        for analysis in analyses:
            debate_messages.append(
                DebateMessage(
                    director_id=analysis.director_id,
                    director_name=analysis.director_name,
                    round_number=0,
                    message_type="analysis",
                    content=analysis.analysis_text,
                )
            )

        for round_num in range(1, self.max_debate_rounds + 1):
            log.info("Debate round %d/%d", round_num, self.max_debate_rounds)
            cb("Orchestrator", f"Round {round_num}/{self.max_debate_rounds}", "debate")

            for director in self.directors:
                try:
                    response = director.critique_peer_analysis(self.model_id, analyses, round_num)
                    content = f"Round {round_num} response from {director.name}"
                    if response.agreements:
                        content += f"\n\nAgreements: {', '.join(response.agreements)}"
                    if response.disagreements:
                        content += f"\n\nDisagreements: {', '.join(response.disagreements)}"
                    if response.new_insights:
                        content += f"\n\nNew Insights: {', '.join(response.new_insights)}"
                    if response.revised_recommendations:
                        content += f"\n\nRevised Recommendations: {', '.join(response.revised_recommendations)}"

                    debate_messages.append(
                        DebateMessage(
                            director_id=director.id,
                            director_name=director.name,
                            round_number=round_num,
                            message_type="critique",
                            content=content,
                            references=[a.director_id for a in analyses if a.director_id != director.id],
                        )
                    )
                    summary = content[:150] + "..." if len(content) > 150 else content
                    cb(director.name, summary, "debate")
                except Exception as e:
                    log.error("%s: Debate round %d failed: %s", director.name, round_num, e, exc_info=True)

        return debate_messages

    # ------------------------------------------------------------------
    # Phase 3
    # ------------------------------------------------------------------

    def _synthesize_consensus(
        self,
        task: str,
        analyses: List[DirectorAnalysis],
        debate_messages: List[DebateMessage],
    ) -> DirectorPlan:
        log.info("Phase 3: Synthesizing consensus plan")

        plan = DirectorPlan(
            title=f"Director Plan: {task}",
            summary="Aggregated recommendations from directors",
            created_by=[d.id for d in self.directors],
        )
        for msg in debate_messages:
            plan.add_debate_message(msg)

        try:
            from core.llm import get_model
            from langchain_core.messages import SystemMessage, HumanMessage
            from core.directors.tool_registry import ToolRegistry

            director_summaries = [
                f"**{a.director_name}:**\n{a.analysis_text[:800]}" for a in analyses
            ]
            tool_catalog = ToolRegistry.get_tool_catalog()

            synthesis_prompt = f"""Based on the director analyses below, create executable action steps.

Original Task: {task}

Director Analyses:
{chr(10).join(director_summaries)}

Create 3-7 specific steps as a JSON array. Each step:
- description, rationale, tool_name, tool_args, agent (video/transitions/tts/music), confidence

{tool_catalog}

Use actual tool names, not "manual_action". Reference vision scores when available.
Respond with ONLY a JSON array."""

            llm = get_model(self.model_id)
            messages = [
                SystemMessage(content="You are a video editing expert synthesizing feedback into an actionable plan."),
                HumanMessage(content=synthesis_prompt),
            ]
            response = llm.invoke(messages)
            response_text = response.content if hasattr(response, "content") else str(response)
            plan.summary = response_text

            steps = self._parse_plan_steps(response_text, analyses)
            for step in steps:
                plan.add_step(step)

        except Exception as e:
            log.error("Plan synthesis failed: %s", e, exc_info=True)
            plan.add_step(
                PlanStep(
                    step_id=str(uuid.uuid4()),
                    type=PlanStepType.EDIT_TIMELINE,
                    description="Review director feedback and apply improvements manually",
                    agent="video",
                    tool_name="manual_review",
                    tool_args={},
                    rationale="Plan synthesis encountered an error",
                    confidence=0.5,
                )
            )

        if analyses:
            plan.confidence = sum(a.confidence for a in analyses) / len(analyses)

        return plan

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_plan_steps(self, plan_text: str, analyses: List[DirectorAnalysis]) -> List[PlanStep]:
        json_match = re.search(r"\[[\s\S]*\]", plan_text)
        if json_match:
            try:
                steps_data = json.loads(json_match.group())
                steps: List[PlanStep] = []
                for sd in steps_data:
                    step_type = self._map_tool_to_step_type(sd.get("tool_name", ""))
                    steps.append(
                        PlanStep(
                            step_id=str(uuid.uuid4()),
                            type=step_type,
                            description=sd.get("description", "Unnamed step"),
                            agent=sd.get("agent", "video"),
                            tool_name=sd.get("tool_name", "manual_action"),
                            tool_args=sd.get("tool_args", {}),
                            rationale=sd.get("rationale", ""),
                            confidence=sd.get("confidence", 0.7),
                            dependencies=sd.get("dependencies", []),
                        )
                    )
                if steps:
                    log.info("Parsed %d steps from JSON", len(steps))
                    return steps
            except Exception as e:
                log.warning("JSON parsing failed: %s, falling back to text", e)

        return self._parse_text_plan(plan_text)

    def _parse_text_plan(self, plan_text: str) -> List[PlanStep]:
        steps: List[PlanStep] = []
        step_description = ""

        for line in plan_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if any(line.startswith(f"{i}.") or line.startswith(f"Step {i}") for i in range(1, 20)):
                if step_description:
                    steps.append(self._create_step_from_description(step_description))
                step_description = line
            elif step_description:
                step_description += " " + line

        if step_description:
            steps.append(self._create_step_from_description(step_description))

        if not steps:
            steps.append(
                PlanStep(
                    step_id=str(uuid.uuid4()),
                    type=PlanStepType.EDIT_TIMELINE,
                    description="Apply director recommendations",
                    agent="video",
                    tool_name="manual_action",
                    tool_args={},
                    rationale="Based on director consensus",
                    confidence=0.7,
                )
            )
        return steps

    def _create_step_from_description(self, description: str) -> PlanStep:
        desc = description
        for i in range(1, 20):
            desc = desc.replace(f"{i}. ", "").replace(f"Step {i}: ", "").replace(f"Step {i}. ", "")

        dl = desc.lower()
        if any(w in dl for w in ("cut", "trim", "split", "clip")):
            st = PlanStepType.SPLIT_CLIP
        elif any(w in dl for w in ("transition", "fade", "dissolve")):
            st = PlanStepType.ADD_TRANSITION
        elif any(w in dl for w in ("audio", "sound", "music", "volume")):
            st = PlanStepType.ADJUST_AUDIO
        elif any(w in dl for w in ("effect", "filter", "color", "grading")):
            st = PlanStepType.ADD_EFFECT
        elif any(w in dl for w in ("reorder", "move", "rearrange")):
            st = PlanStepType.REORDER_CLIPS
        else:
            st = PlanStepType.EDIT_TIMELINE

        return PlanStep(
            step_id=str(uuid.uuid4()),
            type=st,
            description=desc[:200],
            agent="video",
            tool_name="manual_action",
            tool_args={},
            rationale="Based on director recommendations",
            confidence=0.7,
        )

    @staticmethod
    def _map_tool_to_step_type(tool_name: str) -> PlanStepType:
        t = tool_name.lower()
        if "split" in t or "cut" in t:
            return PlanStepType.SPLIT_CLIP
        if "transition" in t:
            return PlanStepType.ADD_TRANSITION
        if "audio" in t or "volume" in t:
            return PlanStepType.ADJUST_AUDIO
        if "effect" in t or "filter" in t:
            return PlanStepType.ADD_EFFECT
        if "music" in t or "generate_music" in t:
            return PlanStepType.ADD_MUSIC
        if "tts" in t or "voice" in t or "generate_tts" in t:
            return PlanStepType.ADD_VOICE
        if "remove" in t or "delete" in t:
            return PlanStepType.REMOVE_CLIP
        if "reorder" in t or "move" in t:
            return PlanStepType.REORDER_CLIPS
        return PlanStepType.EDIT_TIMELINE

    def _apply_voting_resolutions(
        self,
        plan: DirectorPlan,
        voting_results: Dict,
        resolutions: Dict,
    ) -> DirectorPlan:
        filtered: List[PlanStep] = []

        for step in plan.steps:
            resolution = resolutions.get(step.step_id)
            if not resolution:
                filtered.append(step)
                continue

            if not resolution["approved"]:
                step.director_notes["voting"] = f"Rejected: {resolution['consensus']}"
                step.director_notes["vote_breakdown"] = str(resolution["votes"])
                step.confidence = 0.3
                filtered.append(step)
                log.info("Step rejected: %s", step.description[:50])
                continue

            mods = resolution.get("modifications", {})
            if mods:
                tool_args_mods = mods.get("tool_args", {})
                if tool_args_mods:
                    step.tool_args.update(tool_args_mods)
                    step.director_notes["voting"] = f"Modified: {resolution['consensus']}"
                    step.director_notes["modifications"] = str(tool_args_mods)
                    log.info("Step modified: %s — %s", step.description[:50], tool_args_mods)
            else:
                step.director_notes["voting"] = resolution["consensus"]

            step.director_notes["vote_breakdown"] = str(resolution["votes"])
            filtered.append(step)

        plan.steps = filtered
        if plan.metadata is None:
            plan.metadata = {}
        plan.metadata["voting_results"] = voting_results
        plan.metadata["resolutions"] = resolutions
        return plan


# ---------------------------------------------------------------------------
# Convenience entry-point (called from root_agent invoke_directors)
# ---------------------------------------------------------------------------


def run_directors(
    model_id: str,
    task: str,
    director_ids: List[str],
    tool_executor=None,
    status_callback: Optional[StatusCallback] = None,
) -> str:
    """Load directors, orchestrate analysis/debate/voting, return summary."""
    try:
        from core.directors.director_loader import get_director_loader

        loader = get_director_loader()
        directors: List[Director] = []
        for did in director_ids:
            d = loader.load_director(did)
            if d:
                directors.append(d)
            else:
                log.warning("Failed to load director: %s", did)

        if not directors:
            return "Error: No directors loaded"

        orchestrator = DirectorOrchestrator(directors)
        plan = orchestrator.run_directors(
            model_id,
            task,
            tool_executor=tool_executor,
            status_callback=status_callback,
        )

        return (
            f"Directors analysed the project and created a plan with "
            f"{len(plan.steps)} steps.\n\n"
            f"Plan: {plan.title}\n"
            f"Summary: {plan.summary[:500]}\n"
            f"Confidence: {plan.confidence:.2f}"
        )

    except Exception as e:
        log.error("run_directors failed: %s", e, exc_info=True)
        return f"Error: {e}"
