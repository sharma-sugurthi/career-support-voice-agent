import os
from pathlib import Path
from dotenv import load_dotenv

# Use absolute path so subprocesses find .env.local regardless of CWD
load_dotenv(Path(__file__).parent / ".env.local")

from openai import AsyncOpenAI
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import assemblyai, cartesia, openai as lk_openai, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful career support voice AI assistant for RGUKT 
            (Rajiv Gandhi University of Knowledge Technologies).
            You eagerly assist students with career-related questions - resume building, 
            placement preparation, interview tips, higher studies, and skill development.
            Keep every response to 1-2 sentences maximum. Voice responses must be brief.
            Never use formatting, emojis, asterisks, bullet points, or special symbols.
            You are warm, friendly, and encouraging.""",
        )


server = AgentServer()


@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    # Create the Groq client here (inside the subprocess) so env vars are available
    groq_client = AsyncOpenAI(
        api_key=os.environ.get("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )

    session = AgentSession(
        stt=assemblyai.STT(),
        llm=lk_openai.LLM(
            model="groq/compound-mini",
            client=groq_client,
        ),
        tts=cartesia.TTS(
            model="sonic-2",
            voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

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