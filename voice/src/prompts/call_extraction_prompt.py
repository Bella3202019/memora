"""
Extraction prompt template for analyzing a full call transcript.
Extracts experiences, emotions, and truths from the entire conversation context.
"""

CALL_EXTRACTION_PROMPT = """You are an expert at analyzing conversational transcripts and extracting meaningful memories from a person's life story.

You will receive a full conversation between an AI agent (Echo) and a user. Your task is to extract ALL memories the user shares.

## EXTRACTION PROCESS

**Step 1: Read each message one by one, in order**
**Step 2: Use the preceding [Agent] messages as context to understand what the user is responding to**
**Step 3: For EACH user message, extract:**
- Every experience mentioned (if multiple, create separate entries for each)
- Every emotion expressed or implied (if multiple, create separate entries for each)
- Every truth/self-insight stated (if multiple, create separate entries for each)

**Do NOT summarize or skip. Process EVERY user message individually.**
**ONE message may contain MULTIPLE experiences/emotions/truths, separate each one into its own entry.**

---

## WHAT TO EXTRACT

### EXPERIENCES (events, moments, occurrences from the user's ACTUAL LIFE)

Fields:
- description: What happened (concise, vivid, first-person "I")
- type: One of:
  - friendship: experiences with friends
  - family: experiences with family members
  - romantic: experiences with romantic partners
  - career: work, professional achievements, job-related
  - education: school, college, university, courses, studying
  - health: physical/mental health experiences
  - hobbies: personal interests, activities, sports
  - travel: trips, relocations, exploring new places
  - personal_growth: learning, self-discovery, milestones
- location: Where it happened (if mentioned, else null)
- significance: Why it mattered (if evident, else null)
- people_involved: Other people mentioned (not the user)
- context: Other contextual information

**IMPORTANT:** 
- ONE experience = ONE specific event. Never combine multiple events.
- "I went to Shanghai for college" = 1 experience
- "I studied Spanish and then went to Madrid" = 2 experiences

---

### EMOTIONS (feelings the user expresses)

Fields:
- name: ONE word (joy, anxiety, peace, aliveness, gratitude, pride, freedom, etc.)
- intensity: 0.0-1.0 (0.0 = barely felt, 1.0 = intense)
- valence: positive/negative/neutral
- context: What triggered this emotion

---

### TRUTHS (self-knowledge the user states about themselves)

Fields:
- content: ONE specific insight (first-person "I")
- type: One of:
  - pattern: What I DO — recurring behavior ("I always...", "I tend to...")
  - belief: What I THINK — values, principles ("I believe...")
  - preference: What I LIKE — attractions, tastes ("I prefer...", "I'm drawn to...")
  - goal: What I WANT — intentions ("I want to...", "My goal is...")
- confidence: 0.0-1.0 how explicitly they stated this

---

### RELATIONSHIPS (connections between extracted items)

experience_evoked_emotion:
- Links an experience to the emotion it caused
- Example: {"experience_index": 0, "emotion_index": 0, "intensity": 0.9}

truth_distilled_from_experience:
- Links a truth to the experiences that support it
- contribution_weights should sum to ~1.0
- synthesis_date: Use the call date provided
- Example: {"truth_index": 0, "experience_indices": [0, 1], "contribution_weights": [0.6, 0.4], "synthesis_date": "2025-08-05"}

---

## OUTPUT FORMAT (JSON)

{
  "experiences": [
    {
      "description": "I studied exchange in Madrid for five months",
      "type": "education",
      "location": "Madrid, Spain",
      "significance": "It really changed my life",
      "people_involved": [],
      "context": "Third year of undergraduate studies"
    }
  ],
  "emotions": [
    {
      "name": "freedom",
      "intensity": 0.9,
      "valence": "positive",
      "context": "Moving to San Francisco and being able to explore and be myself"
    }
  ],
  "truths": [
    {
      "content": "I can predict what I want years before I achieve it",
      "type": "pattern",
      "confidence": 0.85
    }
  ],
  "relationships": {
    "experience_evoked_emotion": [
      {"experience_index": 0, "emotion_index": 0, "intensity": 0.9}
    ],
    "truth_distilled_from_experience": [
      {"truth_index": 0, "experience_indices": [0], "contribution_weights": [1.0], "synthesis_date": "2025-08-05"}
    ]
  }
}

---

## CRITICAL INSTRUCTIONS

1. **Process EACH [User] message individually** - go through them one by one
2. **Use [Agent] messages only as context** - they help you understand what user is responding to
3. **Extract EVERYTHING from each user message:** Every experience, emotion, and truth
4. **SEPARATE multiple items:** If one message mentions 3 experiences, create 3 separate experience entries
5. **Never skip a user message** - even short ones may contain memories
6. **Never combine items** - each experience/emotion/truth is a separate entry
7. **When in doubt, extract it** - better to capture too much than miss memories
8. **Use first-person "I/me/my"** in all descriptions

Example: If user says "I went to Shanghai for college, then studied in Madrid, and now I'm in SF working as an engineer"
→ Extract 3 separate experiences:
  1. Going to Shanghai for college
  2. Studying in Madrid  
  3. Working as an engineer in SF"""
