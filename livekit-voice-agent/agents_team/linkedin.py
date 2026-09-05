from tools.agent_tools import save_plan, web_search

from .base import SpecialistAgent


class LinkedInCoach(SpecialistAgent):
    """LinkedIn and online-presence specialist, built on user-provided
    profile text - no scraping."""

    prompt_name = "linkedin"
    extra_tools = (web_search, save_plan)
    intro = (
        "introduce yourself as the LinkedIn specialist and ask the user to "
        "paste their current headline or about section in the chat box"
    )
