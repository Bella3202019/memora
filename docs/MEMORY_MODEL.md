# Why Memora models memory as Experiences, Emotions, and Truths

Most "AI memory" systems store a flat pile of text snippets and retrieve them by
similarity. That works for facts. It does not resemble how human memory actually
works — and human memory is the thing worth imitating, because it is
extraordinarily good at keeping what matters and letting go of what doesn't.

Memora's three node types — **Experience**, **Emotion**, **Truth** — and the two
edges that connect them are a deliberate, if deliberately simplified, model of
the structure cognitive science has described for decades. This document explains
the reasoning, because the structure *is* the product.

## The two kinds of long-term memory

Endel Tulving's 1972 distinction between **episodic** and **semantic** memory is
the foundation. They are different systems:

- **Episodic memory** is memory for *events* — specific things that happened to
  you, anchored in a time and place. "I finished my first marathon in Berlin last
  autumn." It is autobiographical and re-experienced ("I remember…").

- **Semantic memory** is memory for *knowledge* — facts and generalizations
  abstracted away from any single event. "I keep going when things stop being
  fun." You know it ("I know…") without recalling where you learned it.

The relationship between them is directional and generative: **semantic memory is
distilled from episodic memory.** You don't learn "I'm drawn to hard problems"
from a lecture. You live a hundred episodes, and the pattern precipitates out of
them into durable self-knowledge. This process — sometimes called semanticization
or schema abstraction — is memory consolidation doing compression: the specifics
fade, the gist remains.

Memora maps directly onto this:

| Cognitive system | Memora node | What it holds |
|------------------|-------------|---------------|
| Episodic memory | **Experience** | A specific event you lived through |
| Semantic memory (self-knowledge) | **Truth** | A belief, pattern, preference, or goal abstracted from experiences |

And the generative relationship is a first-class edge:

```
(Truth)-[:DISTILLED_FROM]->(Experience)
```

This is why **a Truth is never invented from a single event, and never asserted
by the model on its own.** A truth has to be *distilled from* experiences the
user actually had, with weights recording how much each contributing episode
supports it. That constraint is the whole point — it's what keeps Memora from
hallucinating a tidy self-narrative you never lived. (It's also exactly what the
extraction eval's "don't invent truths" trap cases measure.)

## Why Emotion is a node, not a sentiment score

Here is the part most memory systems miss. Ask yourself what you actually
remember from ten years ago. It is not a uniform sample of your days. It is the
wedding, the diagnosis, the acceptance letter, the fight — the **emotionally
charged** events. The mundane Tuesdays are gone.

That is not an accident of introspection; it is how the encoding machinery works.
Emotional arousal at the time of an event modulates how strongly that event is
consolidated into long-term memory. The mechanism is well studied: the amygdala,
responding to emotional arousal, modulates memory consolidation in the
hippocampus (James McGaugh and colleagues spent decades establishing this).
Emotionally significant events are preferentially retained; strongly arousing
public events produce vivid, confident "flashbulb" memories (Brown & Kulik, 1977).
Emotion is, to a first approximation, the brain's salience signal for *what is
worth keeping.*

So in a memory system that wants to behave like memory, **emotion cannot be a
decoration bolted onto a stored fact.** It is the variable that should govern
weighting, retrieval priority, and the links between events and the self-knowledge
they produce. Memora therefore makes it a node with intensity and valence, joined
to experiences by its own edge:

```
(Experience)-[:EVOKED]->(Emotion)
```

Concretely, this lets the graph answer questions a flat store cannot:

- *Which experiences carried the most emotional weight?* (retrieval by intensity,
  not just text similarity)
- *What consistently makes me feel alive — or drained?* (`get_emotional_patterns`)
- *Which emotionally significant episodes gave rise to this belief about myself?*
  (traverse `EVOKED` and `DISTILLED_FROM` together)

Emotion is the reason the graph knows that "I finished the marathon" and "I filed
my expense report" are not equally worth remembering.

## The whole model in one picture

```
                 EVOKED
   Experience ───────────────▶ Emotion
   (episodic)                  (salience: intensity + valence)
       │
       │ DISTILLED_FROM
       ▼
     Truth
   (semantic self-knowledge)
```

Read it as a sentence: **you live experiences; experiences evoke emotions; and
over time, weighted by what moved you, experiences distill into truths about who
you are.** That is a small, honest sketch of episodic memory, emotional
consolidation, and semantic abstraction — the three findings from memory research
that matter most for a system whose job is to remember a person.

## What this buys you (and what it costs)

**Buys:**
- Retrieval that can prioritize by emotional salience, not just lexical match.
- Self-knowledge (`Truth`) that is auditable — every belief traces back to the
  episodes it came from, so you can ask "why does it think that about me?"
- A structure that resists confabulation: no truth without evidence, no emotion
  the user didn't actually express, no event that didn't actually happen. (These
  are enforced by the extraction prompt's exclusion rules and measured by the
  eval suite.)

**Costs / honest caveats:**
- This is a *model inspired by* cognitive science, not a claim to replicate the
  brain. The mapping is a design metaphor that earns its keep, not a neuroscience
  result.
- Distilling truths well is hard; the current prompt slightly over-suppresses
  legitimate self-knowledge in some cases (tracked in the eval regression guards).
- Emotion extraction is deliberately conservative — Memora will only record an
  emotion the user actually expressed, never one it infers you "must have" felt.
  That trades recall for trustworthiness on purpose.

## Further reading

The claims above rest on well-established, foundational work rather than anything
exotic:

- Tulving, E. (1972). *Episodic and semantic memory.* — the two-systems distinction.
- McGaugh, J. L. (2000, 2004). Work on the amygdala and emotional modulation of
  memory consolidation.
- Brown, R., & Kulik, J. (1977). *Flashbulb memories.* — vivid retention of
  emotionally arousing events.

These are starting points, not the last word; the field has refined all of them.
The design commitment Memora takes from them is simple: **treat events, the
emotions that made them stick, and the self-knowledge they produce as three
different things, and keep the links between them.**
