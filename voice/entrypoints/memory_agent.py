import logging
from dotenv import load_dotenv

from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    RoomInputOptions,
    AgentSession,
)

from livekit.plugins import (
    openai,
    silero,
    deepgram,
    noise_cancellation,
)

from livekit.plugins.turn_detector.english import EnglishModel

import sys
from pathlib import Path
# Add project root to path to import voice agents
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from voice.src.agents.memory_agent import MemoryEnabledAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


async def entrypoint(ctx: JobContext):
    """main entrypoint for the memory-enabled agent"""
    await ctx.connect()

    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="ash"),
        turn_detection=EnglishModel(),
        vad=silero.VAD.load(),
    )

    await session.start(
        agent=MemoryEnabledAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Initial greeting
    await session.generate_reply(
        instructions="Greet the user warmly as Charles the travel guide and ask how you can help them plan their next adventure.",
        allow_interruptions=True,
    )


# Run the application
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

