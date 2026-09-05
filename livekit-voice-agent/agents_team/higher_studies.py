from tools.agent_tools import (
    budget_total,
    currency_convert,
    get_plans,
    read_webpage,
    save_plan,
    web_search,
)

from .base import SpecialistAgent


class HigherStudiesPlanner(SpecialistAgent):
    """Higher studies in India and abroad - finance-aware, every number
    sourced, all math done by tools."""

    prompt_name = "higher_studies"
    extra_tools = (web_search, read_webpage, currency_convert, budget_total, save_plan, get_plans)
    intro = (
        "introduce yourself as the higher studies planner and ask what they "
        "want to study and where"
    )
