from tools.agent_tools import get_plans, save_plan

from .base import SpecialistAgent


class StudyPlanner(SpecialistAgent):
    """Week-by-week schedules that fit the user's real life, built on and
    revising their saved plans."""

    prompt_name = "study_planner"
    extra_tools = (save_plan, get_plans)
    intro = (
        "introduce yourself as the study planner and ask what goal they want "
        "a schedule for and how many hours a week they can give"
    )
