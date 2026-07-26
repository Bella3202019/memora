# Voice Agents (LiveKit + Memora)

Real-time voice agents built on [LiveKit](https://livekit.io), with memory
powered by **Memora itself** — no third-party memory service. The travel-guide
agent reads the user's memory graph through the `memora mcp` server (the same
MCP tools any client gets), and calls are turned into new memories afterward
by Memora's own extraction pipeline.

## How memory works

**Read (live).** `MemoryEnabledAgent` attaches the Memora MCP server as an MCP
backend (`Agent(mcp_servers=[MCPServerStdio(command="memora", args=["mcp"])])`).
During a call it can call `search_experiences`, `search_truths`,
`get_experiences_by_emotion`, and `get_emotional_patterns` to ground its replies
in the user's real history.

**Write (after the call).** `process_call.py` runs the call transcript through
Memora's extraction and stores the resulting experiences, emotions, and truths
in Neo4j. Extraction is kept out of the live loop so conversation stays fast,
and it reuses the exact pipeline the rest of Memora is evaluated on.

## Contents

- `entrypoints/`
  - `memory_agent.py` — LiveKit worker for the Memora-backed travel guide
  - `voice_agent.py` — LiveKit worker for the psychologist (Dr. Vela)
  - `process_call.py` — extract memories from a call transcript into Neo4j
- `src/agents/`
  - `memory_agent.py` — travel guide grounded in the Memora graph via MCP
  - `voice_agent.py` — basic voice agent (no memory)
- `src/memory/call_extractor.py` — transcript → experiences/emotions/truths
- `src/prompts/call_extraction_prompt.py` — call extraction prompt
- `main.py` — entrypoint to run either agent

## Setup

```bash
pip install -e .                        # install Memora (provides `memora mcp`)
pip install -r requirements-voice.txt   # LiveKit + plugins
```

Set the required env vars in `.env`: `LIVEKIT_URL`, `LIVEKIT_API_KEY`,
`LIVEKIT_API_SECRET`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, plus your `NEO4J_*`
connection (so the MCP server can reach your graph).

## Usage

```bash
python voice/main.py memory_agent    # Memora-backed travel guide
python voice/main.py voice_agent     # psychologist (Dr. Vela)

# After a call, turn its transcript into memories:
python -m voice.entrypoints.process_call <transcript.json> <user_id>
```
