import logging
from dotenv import load_dotenv

from livekit.agents import Agent

load_dotenv()

logger = logging.getLogger(__name__)


class VoiceAgent(Agent):
    """
    An agent that can talk to the human.
    """
    def __init__(self) -> None:
        super().__init__(
            instructions="""
                You are a helpful voice assistant.
                You are a phychologist named Dr. Vela and will help the user to talk about their problems and help them with their mental health.
            """,
        )
        self._seen_results = set()  # Track previously seen result IDs

    async def on_enter(self):
        self.session.generate_reply(
            instructions="Briefly introduce yourself to the user and give them a compliment.",
        )

