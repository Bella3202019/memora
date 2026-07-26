"""memora CLI: init / ingest / chat / mcp."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from memora.config import ConfigError, load_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def cmd_ingest(args) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    from memora.ingest import ingest
    summary = asyncio.run(ingest(
        config, source_name=args.source, dry_run=args.dry_run
    ))
    print(f"\nTotal: {summary['total']}  Processed: {summary['processed']}  "
          f"Skipped: {summary['skipped']}  Errors: {summary['errors']}")
    return 1 if summary["errors"] else 0


def cmd_chat(args) -> int:
    from memora.agents.chat_agent import run_chat_loop
    asyncio.run(run_chat_loop())
    return 0


def cmd_mcp(args) -> int:
    from memora.mcp.server import main as mcp_main
    asyncio.run(mcp_main())
    return 0


def cmd_init(args) -> int:
    from memora.init_wizard import run_wizard
    return run_wizard(args.config)


def main() -> None:
    parser = argparse.ArgumentParser(prog="memora",
                                     description="Personal memory graph")
    parser.add_argument("--config", type=Path, default=None,
                        help="Path to config.yaml (default ~/.memora/config.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Interactive setup wizard")
    p_ingest = sub.add_parser("ingest", help="Extract and store memories")
    p_ingest.add_argument("--source", help="Only this named source")
    p_ingest.add_argument("--dry-run", action="store_true",
                          help="Extract but don't store")
    sub.add_parser("chat", help="Chat with your memory graph")
    sub.add_parser("mcp", help="Run the MCP server (stdio)")

    args = parser.parse_args()
    handler = {"init": cmd_init, "ingest": cmd_ingest,
               "chat": cmd_chat, "mcp": cmd_mcp}[args.command]
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
