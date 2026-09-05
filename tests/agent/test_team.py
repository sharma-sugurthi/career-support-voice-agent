"""Tests for the multi-agent team: prompt composition, shared tools, and the
handoff graph. No live services needed."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))

from agents_team import (  # noqa: E402
    BaseCareerAgent,
    CareerCoach,
    HigherStudiesPlanner,
    InterviewCoach,
    LinkedInCoach,
    ProjectMentor,
    ResumeCoach,
    SpecialistAgent,
    StudyPlanner,
    TargetPrep,
    compose_instructions,
    load_prompt,
)

SPECIALISTS = [
    ResumeCoach,
    InterviewCoach,
    LinkedInCoach,
    HigherStudiesPlanner,
    TargetPrep,
    StudyPlanner,
    ProjectMentor,
]
ALL_AGENTS = [CareerCoach] + SPECIALISTS

# transfer tool on the coach -> specialist class it must return
ROUTES = {
    "transfer_to_resume_specialist": ResumeCoach,
    "transfer_to_interview_specialist": InterviewCoach,
    "transfer_to_linkedin_specialist": LinkedInCoach,
    "transfer_to_higher_studies_planner": HigherStudiesPlanner,
    "transfer_to_target_prep": TargetPrep,
    "transfer_to_study_planner": StudyPlanner,
    "transfer_to_project_mentor": ProjectMentor,
}


def _tool_names(agent) -> set[str]:
    names = set()
    for tool in agent.tools:
        info = getattr(tool, "info", None)
        names.add(info.name if info else getattr(tool, "__name__", str(tool)))
    return names


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestPromptComposition:
    def test_prompt_files_exist_for_all_agents(self):
        for cls in ALL_AGENTS:
            assert load_prompt(cls.prompt_name), f"prompts/{cls.prompt_name}.md is empty or missing"

    def test_every_agent_carries_base_and_grounding(self):
        """The persona and the anti-hallucination contract must reach every agent."""
        for cls in ALL_AGENTS:
            instructions = cls().instructions
            assert "1-2 short sentences" in instructions, f"{cls.__name__} lost the voice rules"
            assert "Grounding contract" in instructions, f"{cls.__name__} lost the grounding contract"

    def test_specialty_is_included(self):
        assert "resume and portfolio specialist" in ResumeCoach().instructions
        assert "interview specialist" in InterviewCoach().instructions
        assert "main career coach" in CareerCoach().instructions
        assert "higher studies planner" in HigherStudiesPlanner().instructions
        assert "target preparation specialist" in TargetPrep().instructions

    def test_memory_context_appended_last(self):
        text = compose_instructions("coach", memory_context="MEMORY_BLOCK")
        assert text.endswith("MEMORY_BLOCK")

    def test_grounding_bans_unverified_numbers(self):
        grounding = load_prompt("grounding")
        for word in ("fees", "deadlines", "tool result"):
            assert word in grounding

    def test_prompts_are_career_agnostic(self):
        """User requirement: UPSC aspirants and marketers, not just engineers."""
        base = load_prompt("base")
        assert "UPSC" in base
        assert "marketing" in base
        assert "Never assume the user is a technical person" in base
        # specialists honor it too
        assert "UPSC" in load_prompt("target_prep")
        assert "marketer" in load_prompt("projects")

    def test_finance_first_in_higher_studies(self):
        """User requirement: ask financial situation and plan within it."""
        prompt = " ".join(load_prompt("higher_studies").split())
        assert "financial situation" in prompt
        assert "budget" in prompt.lower()


class TestSharedTools:
    def test_every_agent_has_memory_tools(self):
        for cls in ALL_AGENTS:
            names = _tool_names(cls())
            assert "remember" in names, f"{cls.__name__} is missing the remember tool"
            assert "forget" in names, f"{cls.__name__} is missing the forget tool"

    def test_least_privilege_allowlists(self):
        names = _tool_names(HigherStudiesPlanner())
        assert {"currency_convert", "budget_total", "read_webpage"} <= names
        # the study planner needs no web access at all
        planner_names = _tool_names(StudyPlanner())
        assert "web_search" not in planner_names
        assert {"save_plan", "get_plans"} <= planner_names


class TestHandoffGraph:
    """Each transfer tool must return the right agent type, and the memory
    context must survive the handoff."""

    def test_coach_has_a_route_to_every_specialist(self):
        names = _tool_names(CareerCoach())
        for tool_name in ROUTES:
            assert tool_name in names, f"coach is missing {tool_name}"

    def test_each_route_returns_the_right_specialist(self):
        coach = CareerCoach(memory_context="Known: final year student")
        for tool_name, expected_cls in ROUTES.items():
            result = _run(getattr(coach, tool_name)(MagicMock()))
            assert isinstance(result, expected_cls), (
                f"{tool_name} returned {type(result).__name__}, expected {expected_cls.__name__}"
            )
            assert "final year student" in result.instructions, (
                f"memory context lost through {tool_name}"
            )

    def test_every_specialist_hands_back_to_coach(self):
        for cls in SPECIALISTS:
            specialist = cls(memory_context="Known: designer")
            assert "back_to_coach" in _tool_names(specialist), f"{cls.__name__} has no way back"
            result = _run(specialist.back_to_coach(MagicMock()))
            assert isinstance(result, CareerCoach), f"{cls.__name__} back_to_coach broken"
            assert "designer" in result.instructions

    def test_coach_prompt_mentions_every_route(self):
        """The router only routes well if its prompt describes each teammate."""
        coach_prompt = load_prompt("coach")
        for phrase in (
            "resume specialist",
            "interview",
            "LinkedIn",
            "higher studies",
            "target preparation",
            "study planner",
            "projects",
        ):
            assert phrase in coach_prompt, f"coach.md does not mention: {phrase}"


class TestBaseAgent:
    def test_specialists_share_specialist_base(self):
        for cls in SPECIALISTS:
            assert issubclass(cls, SpecialistAgent)

    def test_all_share_career_base(self):
        for cls in ALL_AGENTS:
            assert issubclass(cls, BaseCareerAgent)

    def test_every_specialist_has_a_distinct_intro(self):
        intros = [cls.intro for cls in SPECIALISTS]
        assert len(set(intros)) == len(intros), "specialists share intro lines"
