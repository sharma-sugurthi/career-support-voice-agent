from tools.agent_tools import get_plans, read_webpage, save_plan, web_search

from .base import SpecialistAgent


class TargetPrep(SpecialistAgent):
    """Ace one specific target: a company's hiring process or an exam
    (UPSC, SSC, banking, CAT, GATE), with a dated, sourced roadmap."""

    prompt_name = "target_prep"
    extra_tools = (web_search, read_webpage, save_plan, get_plans)
    intro = (
        "introduce yourself as the target preparation specialist and ask which "
        "company or exam they are aiming for, and by when"
    )
