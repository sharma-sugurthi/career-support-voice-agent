from livekit.agents import Agent, RunContext, function_tool

from tools.agent_tools import get_plans, save_plan, web_search

from .base import BaseCareerAgent, UserData


class CareerCoach(BaseCareerAgent):
    """The orchestrator: first voice the user hears, owns general career
    direction, routes deep work to specialists via handoff tools."""

    prompt_name = "coach"
    extra_tools = (web_search, save_plan, get_plans)

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions=(
                "If the conversation is just starting, greet the user; when you "
                "already know them from before, recall in one sentence where you "
                "left off and ask if they want to continue. If a specialist just "
                "handed back to you, skip the greeting and ask what they would "
                "like to do next."
            )
        )

    @function_tool()
    async def transfer_to_resume_specialist(self, context: RunContext[UserData]) -> Agent:
        """Hand the conversation to the resume specialist. Call when the user
        wants their resume, CV, or portfolio reviewed or improved."""
        from .resume import ResumeCoach

        return ResumeCoach(memory_context=self.memory_context)

    @function_tool()
    async def transfer_to_interview_specialist(self, context: RunContext[UserData]) -> Agent:
        """Hand the conversation to the interview specialist. Call when the
        user wants a mock interview, practice questions, or feedback on their
        interview answers."""
        from .interview import InterviewCoach

        return InterviewCoach(memory_context=self.memory_context)

    @function_tool()
    async def transfer_to_linkedin_specialist(self, context: RunContext[UserData]) -> Agent:
        """Hand the conversation to the LinkedIn specialist. Call when the
        user wants to build or improve their LinkedIn profile or online
        presence."""
        from .linkedin import LinkedInCoach

        return LinkedInCoach(memory_context=self.memory_context)

    @function_tool()
    async def transfer_to_higher_studies_planner(self, context: RunContext[UserData]) -> Agent:
        """Hand the conversation to the higher studies planner. Call when the
        user wants to plan a masters, MBA, PhD, or study abroad, including
        costs, exams, and scholarships."""
        from .higher_studies import HigherStudiesPlanner

        return HigherStudiesPlanner(memory_context=self.memory_context)

    @function_tool()
    async def transfer_to_target_prep(self, context: RunContext[UserData]) -> Agent:
        """Hand the conversation to the target preparation specialist. Call
        when the user wants to prepare for one specific company's hiring
        process, one exam like UPSC, SSC, banking, CAT, or GATE, or a
        placement season."""
        from .target_prep import TargetPrep

        return TargetPrep(memory_context=self.memory_context)

    @function_tool()
    async def transfer_to_study_planner(self, context: RunContext[UserData]) -> Agent:
        """Hand the conversation to the study planner. Call when the user
        wants a weekly schedule or study plan for a goal they already chose."""
        from .study_planner import StudyPlanner

        return StudyPlanner(memory_context=self.memory_context)

    @function_tool()
    async def transfer_to_project_mentor(self, context: RunContext[UserData]) -> Agent:
        """Hand the conversation to the projects specialist. Call when the
        user wants project or portfolio ideas, or current hackathons and
        competitions."""
        from .projects import ProjectMentor

        return ProjectMentor(memory_context=self.memory_context)
