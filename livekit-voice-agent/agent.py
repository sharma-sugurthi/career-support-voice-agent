import logging
from pathlib import Path
from dotenv import load_dotenv

# Use absolute path so subprocesses find .env.local regardless of CWD
load_dotenv(Path(__file__).parent / ".env.local")

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, room_io
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from agents_team import CareerCoach, UserData
from llm_providers import classify_llm_error, create_llm, SPOKEN_ERROR_MESSAGES
from memory import MemoryStore
from memory.summarizer import summarize_session
from stt_providers import create_stt
from tts_providers import create_tts

logger = logging.getLogger("career-agent")

server = AgentServer()


@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    user_id = participant.identity or f"anon_{ctx.room.name}"

    store = MemoryStore()
    is_returning = store.touch_user(user_id)
    memory_context = store.build_memory_context(user_id) if is_returning else ""

    # Create the LLM here (inside the subprocess) so env vars are available
    # and the client object isn't lost across the IPC process boundary.
    llm = create_llm()

    session = AgentSession(
        userdata=UserData(user_id=user_id, store=store),
        stt=create_stt(),
        llm=llm,
        tts=create_tts(),
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

    async def save_memory() -> None:
        # Runs when the session shuts down. Memory must never crash close.
        try:
            summary = await summarize_session(llm, session.history)
            if summary:
                store.add_session_summary(user_id, summary)
            store.save_chat_snapshot(user_id, session.history.to_dict())
            logger.info("memory saved for %s (summary: %s)", user_id, bool(summary))
        except Exception:
            logger.exception("failed to save session memory")

    ctx.add_shutdown_callback(save_memory)

    # The CareerCoach greets on_enter; specialists introduce themselves on handoff.
    await session.start(
        room=ctx.room,
        agent=CareerCoach(memory_context=memory_context),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
