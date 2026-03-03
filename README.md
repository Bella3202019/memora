# Memora - Personal Memory Graph

A system for extracting and storing personal memories from diary entries into a Neo4j graph database. Extracts episodic memory (experiences) and personal semantic memory (truths), along with emotions, using LLM-based analysis. 


## Overview

This project provides tools to:
- **Extract memories** from personal diary entries
- **Store memories** in a Neo4j graph database with relationships
- **Query memories** to understand patterns, experiences, and personal insights

### Memory Types

| Type | Description | Example |
|------|-------------|---------|
| **Experience** (Episodic Memory) | Specific events, moments, occurrences from life | "I studied in Madrid for 5 months" |
| **Emotion** | Feelings expressed or implied | "freedom", "gratitude", "anxiety" |
| **Truth** (Personal Semantic Memory) | Abstracted self-knowledge, patterns, beliefs distilled from experiences | "I feel alive when talking deeply with someone" |

## Project Structure

```
memory/
├── src/
│   ├── memory/
│   │   ├── diary_extractor.py     # Extract from diary entries
│   │   ├── storage.py             # Neo4j storage operations
│   │   └── client.py              # Neo4j client wrapper
│   ├── prompts/
│   │   └── diary_extraction_prompt.py  # Prompt for diaries
│   └── agents/                    # Chat agent for querying memories
│
├── entrypoints/
│   ├── extract_diary_memories.py  # Extract memories from diary entries
│   ├── chat.py                    # Interactive chat interface
│   └── embed_existing.py          # Backfill embeddings for existing nodes
│
├── tests/
│                
│
├── data/
│   ├── output/                    # Extracted JSON outputs (gitignored)
│   ├── chat/                      # Chat history files (gitignored)
│   └── processed_diaries.txt      # Processed diary log (gitignored)
│
└── docs/
    └── MEMORY_SCHEMA.md           # Neo4j schema documentation
```

## Setup

### 1. Clone and Install

```bash
git clone <repo-url>
cd memory

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file with the following:

```env
# OpenAI (required for extraction)
OPENAI_API_KEY=your_openai_api_key

# Neo4j (required for storage)
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
```

### 3. Test Neo4j Connection

```bash
python -m tests.test_neo4j_connection
```

## Usage

### Extract Memories from Diary Entries

Diary files are markdown files with filenames in format: `[UUID]-[YYYY-MM-DD-HH-MM-SS].md`

**Dry run single diary:**
```bash
python -m entrypoints.extract_diary_memories "/path/to/diary.md" "user_123" --dry-run
```

**Extract and store single diary:**
```bash
python -m entrypoints.extract_diary_memories "/path/to/diary.md" "user_123"
```

**Batch process all diaries:**
```bash
python -m entrypoints.extract_diary_memories --dir "/path/to/diaries/" "user_123"
```

### Query Memories via Chat Interface

Interactive chat interface for querying your memory knowledge graph:

```bash
python -m entrypoints.chat
```

The chat interface allows you to:
- Search experiences by semantic similarity
- Find truths and self-knowledge patterns
- Explore emotional patterns
- Discover connections between experiences and emotions

### Backfill Embeddings

If you have existing Experience or Truth nodes without embeddings, you can backfill them:

```bash
python -m entrypoints.embed_existing
```

## Neo4j Schema

### Nodes

- **User** - `{userId}`
- **Experience** - `{description, type, date, location, significance}`
- **Emotion** - `{name, valence}`
- **Truth** - `{content, type, confidence, first_synthesized}`

### Relationships

- `(User)-[:HAD]->(Experience)` - User had an experience
- `(User)-[:FELT]->(Emotion)` - User felt an emotion
- `(User)-[:GOT]->(Truth)` - User discovered a truth
- `(Experience)-[:EVOKED]->(Emotion)` - Experience triggered emotion
- `(Truth)-[:DISTILLED_FROM]->(Experience)` - Truth derived from experiences

### Query Examples

```cypher
-- Get all experiences for a user
MATCH (u:User {userId: "user_123"})-[:HAD]->(exp:Experience)
RETURN exp.description, exp.type, exp.date, exp.location

-- Get emotions with intensity
MATCH (u:User {userId: "user_123"})-[f:FELT]->(em:Emotion)
RETURN em.name, f.intensity, f.context, em.valence

-- Get truths/self-knowledge
MATCH (u:User {userId: "user_123"})-[:GOT]->(t:Truth)
RETURN t.content, t.type, t.confidence

-- Full graph for a user
MATCH path = (u:User {userId: "user_123"})-[*1..2]-(n)
RETURN path LIMIT 200
```

## Experience Types

| Type | Description |
|------|-------------|
| `friendship` | Experiences with friends |
| `family` | Experiences with family members |
| `romantic` | Experiences with romantic partners |
| `career` | Work, professional achievements |
| `education` | School, college, courses |
| `health` | Physical/mental health |
| `hobbies` | Personal interests, activities |
| `travel` | Trips, relocations |
| `personal_growth` | Learning, self-discovery |

## Truth Types

| Type | Description | Example |
|------|-------------|---------|
| `pattern` | Recurring behavior | "I always choose what I really want" |
| `belief` | Values, principles | "I believe deep connections matter" |
| `preference` | Tastes, attractions | "I'm drawn to challenging work" |
| `goal` | Intentions, aspirations | "I want to build great AI products" |

## Contributing

### Adding New Data Sources

1. Create a new extractor in `src/memory/` (e.g., `journal_extractor.py`)
2. Create a prompt in `src/prompts/` (e.g., `journal_extraction_prompt.py`)
3. Create an entrypoint in `entrypoints/` (e.g., `process_journal.py`)
4. The storage layer (`storage.py`) can be reused as-is

### Modifying Extraction Prompts

Prompts are in `src/prompts/`. Key guidelines:
- Use first-person "I/me/my" in extracted content
- Extract only real life events, not conversation meta-events
- Separate multiple items (don't combine experiences)
- Include relationships between experiences, emotions, and truths

### Running Tests

```bash
# Test Neo4j connection
python -m tests.test_neo4j_connection

```


