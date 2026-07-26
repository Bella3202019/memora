"""
Main entry point for the memory voice agent application.

This script allows you to choose which agent to run:
- memory_agent: Travel guide agent backed by the Memora memory graph (via MCP)
- voice_agent: Psychologist agent (Dr. Vela)

Usage:
    python main.py memory_agent    # Run memory-enabled travel guide
    python main.py voice_agent     # Run voice psychologist agent
    python main.py                 # Defaults to memory_agent
"""
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point that routes to the appropriate agent."""
    # Get agent type from command line args or default to memory_agent
    agent_type = sys.argv[1] if len(sys.argv) > 1 else "memory_agent"
    
    if agent_type == "memory_agent":
        logger.info("Starting Memora-backed agent (travel guide)...")
        from voice.entrypoints.memory_agent import entrypoint
        from livekit.agents import WorkerOptions, cli
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
    
    elif agent_type == "voice_agent":
        logger.info("Starting voice agent (Dr. Vela)...")
        from voice.entrypoints.voice_agent import entrypoint
        from livekit.agents import WorkerOptions, cli
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
    
    else:
        logger.error(f"Unknown agent type: {agent_type}")
        logger.info("Available agents: memory_agent, voice_agent")
        sys.exit(1)


if __name__ == "__main__":
    main()
