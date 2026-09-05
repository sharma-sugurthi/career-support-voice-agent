from tools.agent_tools import save_plan, web_search

from .base import SpecialistAgent


class InterviewCoach(SpecialistAgent):
    """Mock interview specialist: any role, any exam board, rubric-scored
    feedback."""

    prompt_name = "interview"
    extra_tools = (web_search, save_plan)
    intro = (
        "introduce yourself as the interview specialist and ask what role or "
        "exam they want to practice for"
    )
