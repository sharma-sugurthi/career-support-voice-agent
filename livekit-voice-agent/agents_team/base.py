"""Shared foundation for the career agent team.

Every agent's instructions are composed from prompt files:
    prompts/base.md       persona, voice rules, memory rules, honesty
    prompts/grounding.md  the anti-hallucination contract
    prompts/<name>.md     the agent's specialty
plus the per-user memory context loaded at session start.
"""
from dataclasses import dataclass
from pathlib import Path

from livekit.agents import Agent, RunContext, function_tool  # noqa: F401 (Agent re-used by subclasses)

from memory import MemoryStore

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class UserData:
    """Shared state every agent in the session can reach via RunContext."""

    user_id: str
    store: MemoryStore


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def compose_instructions(specialty: str, memory_context: str = "") -> str:
    parts = [load_prompt("base"), load_prompt("grounding"), load_prompt(specialty)]
    if memory_context:
        parts.append(memory_context)
    return "\n\n".join(p.strip() for p in parts if p.strip())


class BaseCareerAgent(Agent):
    """Base class: prompt composition + the memory tools every agent shares.

    Subclasses set `prompt_name` to their prompts/<name>.md file. The memory
    context travels along on every handoff so a new specialist knows the user
    too.
    """

    prompt_name = "base"
    # per-subclass allowlist of shared tools from tools/agent_tools.py
    extra_tools: tuple = ()

    def __init__(self, memory_context: str = "", **kwargs) -> None:
        self.memory_context = memory_context
        super().__init__(
            instructions=compose_instructions(self.prompt_name, memory_context),
            tools=list(self.extra_tools),
            **kwargs,
        )

    @function_tool()
    async def remember(self, context: RunContext[UserData], key: str, value: str) -> str:
        """Save one lasting fact the user told you about themselves, so the
        next conversation can continue from it. Call this whenever the user
        states something durable: their target role, education, skills,
        location, constraints, or financial situation.

        Args:
            key: short snake_case name for the fact, e.g. target_role, education, current_skills
            value: the fact itself, phrased the way the user said it
        """
        userdata = context.userdata
        userdata.store.remember_fact(userdata.user_id, key, value, source="user_said")
        return f"Remembered {key}."

    @function_tool()
    async def forget(self, context: RunContext[UserData], key: str) -> str:
        """Delete a fact previously saved about the user. Call this when the
        user asks you to forget something or says a saved fact is wrong.

        Args:
            key: the snake_case name of the fact to delete
        """
        userdata = context.userdata
        userdata.store.forget_fact(userdata.user_id, key)
        return f"Forgot {key}."


class SpecialistAgent(BaseCareerAgent):
    """A specialist teammate: introduces itself on entry and can always hand
    the conversation back to the coach. Subclasses set `intro` to what the
    specialist should say/ask when it joins."""

    intro = "introduce yourself and ask how you can help"

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions=(
                "You just joined the conversation as this specialist. In one short "
                f"sentence, {self.intro}, unless the conversation already answers it."
            )
        )

    @function_tool()
    async def back_to_coach(self, context: RunContext[UserData]) -> Agent:
        """Return the conversation to the main career coach. Call when this
        specialist topic is finished or the user asks about something outside
        your specialty."""
        from .coach import CareerCoach

        return CareerCoach(memory_context=self.memory_context)
