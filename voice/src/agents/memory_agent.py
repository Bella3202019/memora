"""Memory-enabled voice agent backed by the Memora memory graph.

Instead of a third-party memory service, this agent reads from the user's own
Memora graph through the `memora mcp` server — the same MCP tools any client
gets: search_experiences, search_truths, get_experiences_by_emotion,
get_emotional_patterns. The agent calls those tools when it needs the user's
history to ground a reply.

Writes happen out of band: after a call, `voice/entrypoints/process_call.py`
extracts memories from the full transcript into Neo4j. That keeps the live
conversation fast (no per-turn extraction) and reuses the exact extraction
pipeline the rest of Memora is evaluated on.
"""

import logging

from dotenv import load_dotenv

from livekit.agents import Agent, mcp

load_dotenv()

logger = logging.getLogger(__name__)


class MemoryEnabledAgent(Agent):
    """Travel guide (Charles) that grounds answers in the Memora memory graph."""

    def __init__(self) -> None:
        super().__init__(
            instructions="""
                You are Charles, a warm and knowledgeable travel guide who helps
                the user plan the trip of their dreams — work retreats, solo
                backpacking, self-reflection journeys.

                You have access to the user's personal memory graph through tools:
                - search_experiences: past events and moments from their life
                - search_truths: their stated beliefs, patterns, preferences, goals
                - get_experiences_by_emotion / get_emotional_patterns: how places
                  and activities made them feel

                Use these tools to ground your suggestions in who the user actually
                is: recall trips they loved, preferences they've expressed, and
                what energizes vs. drains them. When a suggestion draws on a memory,
                reference it naturally.

                Never suggest anything dangerous, illegal, or inappropriate.
            """,
            # Dogfood Memora's own MCP server as the memory backend.
            mcp_servers=[mcp.MCPServerStdio(command="memora", args=["mcp"])],
        )
        logger.info("Memory agent initialized with Memora MCP backend")

    async def on_enter(self):
        self.session.generate_reply(
            instructions="Briefly introduce yourself as Charles and share a short, light travel joke.",
        )
