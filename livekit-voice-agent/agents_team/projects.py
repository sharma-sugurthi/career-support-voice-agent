from tools.agent_tools import read_webpage, save_plan, web_search

from .base import SpecialistAgent


class ProjectMentor(SpecialistAgent):
    """Proof-of-work for any field: projects, portfolio pieces, and live
    hackathon/competition listings."""

    prompt_name = "projects"
    extra_tools = (web_search, read_webpage, save_plan)
    intro = (
        "introduce yourself as the projects specialist and ask what role they "
        "are building proof of work for"
    )
