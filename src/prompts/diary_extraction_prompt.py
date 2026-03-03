"""
Extraction prompt template for analyzing diary entries.
Extracts experiences, emotions, and truths from personal reflective writing.
"""

DIARY_EXTRACTION_PROMPT = """You are an expert at analyzing personal diary entries and extracting meaningful memories from someone's life.

You will receive a diary entry written by the user. Your task is to extract ALL memories they share.

## EXTRACTION PROCESS

**Step 1: Read through the entire diary entry carefully**
**Step 2: Extract from each paragraph/section:**
- Every experience mentioned (if multiple, create separate entries for each)
- Every emotion expressed or implied (if multiple, create separate entries for each)
- Every truth/self-insight stated (if multiple, create separate entries for each)

**ONE entry may contain MULTIPLE experiences/emotions/truths - separate each into its own entry.**

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
- "I met Sarah and Dara today" = 2 separate experiences if meaningful interactions occurred with each

---

### EMOTIONS (feelings the user expresses)

Fields:
- name: ONE word (joy, anxiety, peace, aliveness, gratitude, pride, freedom, blessed, etc.)
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
- synthesis_date: Use the diary date provided
- Example: {"truth_index": 0, "experience_indices": [0, 1], "contribution_weights": [0.6, 0.4], "synthesis_date": "2025-08-05"}

---

## OUTPUT FORMAT (JSON)

{
  "experiences": [
    {
      "description": "I had a beautiful conversation with Dara about her startup journey",
      "type": "friendship",
      "location": "San Francisco",
      "significance": "I learned about her passion and determination",
      "people_involved": ["Dara"],
      "context": "Catching up with a friend"
    }
  ],
  "emotions": [
    {
      "name": "aliveness",
      "intensity": 0.9,
      "valence": "positive",
      "context": "Talking deeply with friends made me feel alive"
    }
  ],
  "truths": [
    {
      "content": "I feel alive when talking deep with someone",
      "type": "pattern",
      "confidence": 0.9
    }
  ],
  "relationships": {
    "experience_evoked_emotion": [
      {"experience_index": 0, "emotion_index": 0, "intensity": 0.9}
    ],
    "truth_distilled_from_experience": [
      {"truth_index": 0, "experience_indices": [0], "contribution_weights": [1.0], "synthesis_date": "2025-12-03"}
    ]
  }
}

---

## CRITICAL INSTRUCTIONS

1. **Read the ENTIRE diary entry** - don't skip any section
2. **Extract EVERYTHING:** Every experience, emotion, and truth mentioned
3. **SEPARATE multiple items:** If entry mentions 3 experiences, create 3 separate entries
4. **Never combine items** - each experience/emotion/truth is a separate entry
5. **Extract from reflections too** - diary entries often contain insights and realizations
6. **People matter** - extract names of people involved in experiences
7. **Goals and intentions count** - "I want to..." or "I set a goal to..." are truths
8. **Use first-person "I/me/my"** in all descriptions

Example: If diary says "I met Sarah and Hadassah. Sarah told me about her boyfriend. Hadassah is very mature for 17."
→ Extract:
  1. Experience: Meeting Sarah
  2. Experience: Meeting Hadassah
  3. Experience: Sarah sharing about her relationship (people_involved: Sarah)"""

