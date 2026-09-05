import logging
from pathlib import Path
from dotenv import load_dotenv

# Use absolute path so subprocesses find .env.local regardless of CWD
load_dotenv(Path(__file__).parent / ".env.local")

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import assemblyai, cartesia, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from llm_providers import classify_llm_error, create_llm, SPOKEN_ERROR_MESSAGES

logger = logging.getLogger("career-agent")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a voice AI career coach. You help anyone,
            anywhere with their career - resume and portfolio building, job search
            strategy, interview preparation, salary negotiation, career switches,
            higher studies, freelancing, and skill development plans.
            Ask one clarifying question when the user's goal is vague, then give
            concrete, actionable advice tailored to their situation.
            Keep every response to 1-2 sentences maximum. Voice responses must be brief.
            Never use formatting, emojis, asterisks, bullet points, or special symbols.
            You are warm, direct, and encouraging.""",
        )


server = AgentServer()


@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    # Create the LLM here (inside the subprocess) so env vars are available
    # and the client object isn't lost across the IPC process boundary.
    session = AgentSession(
        stt=assemblyai.STT(),
        llm=create_llm(),
        tts=cartesia.TTS(
            model="sonic-2",
            voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    @session.on("error")
    def on_session_error(ev) -> None:
        # When the LLM fails, say so out loud (TTS still works) instead of
        # leaving the caller in silence. Credits gone vs. temporary rate
        # limit get different messages.
        error = getattr(ev, "error", ev)
        kind = classify_llm_error(error)
        logger.warning("session error (classified as %s): %s", kind, error)
        if kind is not None:
            session.say(SPOKEN_ERROR_MESSAGES[kind], allow_interruptions=True)

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    await session.generate_reply(
        instructions="Greet the user warmly and offer career support assistance."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
