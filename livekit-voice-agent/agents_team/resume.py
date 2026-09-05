from tools.agent_tools import save_plan, web_search

from .base import SpecialistAgent


class ResumeCoach(SpecialistAgent):
    """Resume, CV, and portfolio specialist for any field."""

    prompt_name = "resume"
    extra_tools = (web_search, save_plan)
    intro = (
        "introduce yourself as the resume specialist and ask the user to paste "
        "their resume text in the chat box or read a section aloud"
    )
