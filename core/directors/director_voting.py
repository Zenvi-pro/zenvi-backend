"""
Director Voting System.

Enables pre-execution voting where directors review and vote on proposed plan
steps. Supports approve / conditional / reject votes with conflict resolution.

Ported from core/src/classes/ai_directors/director_voting.py.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from logger import log


class VoteType(Enum):
    APPROVE = "approve"
    CONDITIONAL = "conditional"
    REJECT = "reject"


@dataclass
class DirectorVote:
    director_id: str
    director_name: str
    step_id: str
    vote: VoteType
    confidence: float
    rationale: str
    suggested_modifications: Dict[str, Any] = field(default_factory=dict)


class DirectorVotingPhase:
    def __init__(self, directors: List):
        self.directors = directors

    def run_voting(
        self,
        plan,
        analyses: List,
        model_id: str,
    ) -> Dict[str, List[DirectorVote]]:
        log.info(
            "Phase 4: Running voting with %d directors on %d steps",
            len(self.directors),
            len(plan.steps),
        )
        voting_results: Dict[str, List[DirectorVote]] = {}

        for step in plan.steps:
            step_votes: List[DirectorVote] = []
            for director in self.directors:
                try:
                    vote = self._get_director_vote(director, step, plan, analyses, model_id)
                    step_votes.append(vote)
                    log.debug(
                        "%s voted %s on step %s",
                        director.name,
                        vote.vote.value,
                        step.step_id[:8],
                    )
                except Exception as e:
                    log.error("Failed to get vote from %s: %s", director.name, e, exc_info=True)
                    step_votes.append(
                        DirectorVote(
                            director_id=director.id,
                            director_name=director.name,
                            step_id=step.step_id,
                            vote=VoteType.APPROVE,
                            confidence=0.5,
                            rationale="Default vote due to error",
                        )
                    )
            voting_results[step.step_id] = step_votes

        return voting_results

    # ------------------------------------------------------------------

    def _get_director_vote(self, director, step, plan, analyses, model_id: str) -> DirectorVote:
        voting_prompt = f"""Review this proposed action step and vote on whether it should be executed.

PROPOSED STEP:
  Description: {step.description}
  Tool: {step.tool_name}
  Arguments: {json.dumps(step.tool_args, indent=2)}
  Agent: {step.agent}
  Rationale: {step.rationale}
  Confidence: {step.confidence}

YOUR PERSPECTIVE as {director.name}:
{director.get_system_prompt()[:500]}

VOTE OPTIONS:
1. APPROVE - Execute as proposed
2. CONDITIONAL - Approve with modifications (suggest specific changes to tool_args)
3. REJECT - Do not execute (explain why)

Respond ONLY with valid JSON:
{{
  "vote": "approve|conditional|reject",
  "confidence": 0.85,
  "rationale": "Brief explanation",
  "suggested_modifications": {{
    "tool_args": {{"param_name": "new_value"}}
  }}
}}"""

        try:
            from core.llm import get_model
            from langchain_core.messages import SystemMessage, HumanMessage

            llm = get_model(model_id)
            response = llm.invoke([
                SystemMessage(content=director.get_system_prompt()),
                HumanMessage(content=voting_prompt),
            ])

            response_text = response.content if hasattr(response, "content") else str(response)

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                vote_data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

            vote_str = vote_data.get("vote", "approve").lower()
            if vote_str not in ("approve", "conditional", "reject"):
                vote_str = "approve"

            return DirectorVote(
                director_id=director.id,
                director_name=director.name,
                step_id=step.step_id,
                vote=VoteType(vote_str),
                confidence=float(vote_data.get("confidence", 0.7)),
                rationale=vote_data.get("rationale", "No rationale provided"),
                suggested_modifications=vote_data.get("suggested_modifications", {}),
            )

        except Exception as e:
            log.error("Failed to parse vote from %s: %s", director.name, e, exc_info=True)
            return DirectorVote(
                director_id=director.id,
                director_name=director.name,
                step_id=step.step_id,
                vote=VoteType.APPROVE,
                confidence=0.6,
                rationale=f"Default approve (parsing error: {str(e)[:100]})",
            )

    # ------------------------------------------------------------------

    def resolve_votes(self, voting_results: Dict[str, List[DirectorVote]]) -> Dict[str, Dict]:
        resolutions: Dict[str, Dict] = {}

        for step_id, votes in voting_results.items():
            approve_count = sum(1 for v in votes if v.vote == VoteType.APPROVE)
            conditional_count = sum(1 for v in votes if v.vote == VoteType.CONDITIONAL)
            reject_count = sum(1 for v in votes if v.vote == VoteType.REJECT)
            total = len(votes)

            approval_rate = approve_count / total if total > 0 else 0

            if approval_rate >= 0.7:
                approved = True
                consensus = "Strong approval"
                modifications: Dict[str, Any] = {}
            elif (approve_count + conditional_count) / total >= 0.7 if total else False:
                approved = True
                consensus = "Conditional approval"
                modifications = self._merge_modifications(
                    [v.suggested_modifications for v in votes if v.vote == VoteType.CONDITIONAL]
                )
            else:
                approved = False
                consensus = "Insufficient consensus"
                modifications = {}

            resolutions[step_id] = {
                "approved": approved,
                "modifications": modifications,
                "consensus": consensus,
                "votes": {
                    "approve": approve_count,
                    "conditional": conditional_count,
                    "reject": reject_count,
                },
            }

            log.debug(
                "Step %s: %s (A:%d C:%d R:%d)",
                step_id[:8],
                consensus,
                approve_count,
                conditional_count,
                reject_count,
            )

        return resolutions

    # ------------------------------------------------------------------

    def _merge_modifications(self, modifications_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not modifications_list:
            return {}

        all_tool_args = []
        for mods in modifications_list:
            if "tool_args" in mods and isinstance(mods["tool_args"], dict):
                all_tool_args.append(mods["tool_args"])

        if not all_tool_args:
            return {}

        param_values: Dict[str, list] = {}
        for tool_args in all_tool_args:
            for key, value in tool_args.items():
                param_values.setdefault(key, []).append(value)

        merged_tool_args: Dict[str, Any] = {}
        for key, values in param_values.items():
            if all(isinstance(v, (int, float)) for v in values):
                sorted_values = sorted(values)
                merged_tool_args[key] = sorted_values[len(sorted_values) // 2]
            else:
                most_common = Counter(values).most_common(1)
                if most_common:
                    merged_tool_args[key] = most_common[0][0]

        return {"tool_args": merged_tool_args}
