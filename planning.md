# Planning — Provenance Guard

## Architecture
A creator sends text to `POST /submit`. The text first goes to Signal 1
(Groq LLM), which reads it holistically and returns a guess of how AI-like
it is. The same text then goes to Signal 2 (stylometric heuristics), which
measures structure (sentence variety, vocabulary diversity, punctuation). Both
scores are combined into one confidence score. That score is mapped to a
transparency label (one of three variants). The whole decision — scores,
signals, label — is written to the audit log, and the response (with a new
`content_id`) goes back to the creator. Later, a creator can dispute a result
with `POST /appeal`; this flips the content status to "under review" and logs
the appeal next to the original decision.

## Detection Signals
**Signal 1 — Groq LLM classification**
- Measures: whether the text *reads* as AI-written (semantic + stylistic feel).
- Why it differs: AI text is often smooth, balanced, and generic; humans writing are
  messier and more personal.
- Blind spot: can be fooled by lightly edited AI text or polished human writing;
  also non-deterministic and depends on the prompt.

**Signal 2 — Stylometric heuristics**
- Measures: structure — sentence-length variance, type-token ratio (vocabulary
  diversity), punctuation density.
- Why it differs: AI writing tends to be uniform; human writing varies more.
- Blind spot: short texts give unreliable stats; formal human writing can look
  "too clean" and score AI-like.

These are independent: one is meaning-based, one is structure-based.

## False-Positive Scenario
A non-native English speaker writes a formal, clean blog post. The LLM may call
it AI-like, and the stylometrics may see low variation. To avoid harm:
- The combined score should stay in the **uncertain** band, not jump to
  "likely AI", because the two signals only weakly agree.
- The label uses soft language and never accuses.
- The creator can appeal, which marks the content "under review" and logs it.
Design rule: a false positive (human flagged as AI) is worse than a miss, so
the system leans toward "uncertain" when signals disagree.

## API 
- `POST /submit` — body: `text`, `creator_id`. Returns `content_id`,
  `attribution`, `confidence`, `label`.
- `POST /appeal` — body: `content_id`, `creator_reasoning`. Returns confirmation;
  sets status to "under review".
- `GET /log` — returns recent audit-log entries as JSON.

## Architecture 
Submission flow:
```
POST /submit (text, creator_id)
      |
      v
[Signal 1: Groq LLM] --llm_score--> +
      |                             |
      v                             v
[Signal 2: Stylometrics] --style_score--> [Confidence Scoring]
                                                |
                                                v combined_score
                                        [Transparency Label]
                                                |
                                                v label_text
                                          [Audit Log] --> response
                                          (content_id, attribution,
                                           confidence, label)
```

Appeal flow:
```
POST /appeal (content_id, creator_reasoning)
      |
      v
[Update status -> "under review"]
      |
      v
[Audit Log: appeal + original decision]
      |
      v
response (confirmation)
```

## Spec

### 1. Detection signals
- **Signal 1 (Groq LLM):** prompt the model to return a JSON `ai_likelihood`
  float `0.0–1.0` (0 = clearly human, 1 = clearly AI). Output = `llm_score`.
- **Signal 2 (Stylometrics):** compute 3 metrics in pure Python —
  sentence-length variance, type-token ratio, punctuation density. Each is
  normalized so "more uniform / less diverse" pushes toward AI, then averaged
  into one `style_score` float `0.0–1.0`.
- **Combine:** `confidence = 0.6 * llm_score + 0.4 * style_score`.
  LLM is weighted higher because it reads meaning; stylometrics is a noisier
  structural check. Result is the single AI-likelihood confidence `0.0–1.0`.

### 2. Uncertainty representation
- `confidence` = how AI-like the text is (0 = human, 1 = AI).
- A score of **0.6** means "leaning AI but not sure" — it lands in the
  **uncertain** band on purpose, so the label hedges instead of accusing.
- Calibration: signals already output 0–1; the weighted blend keeps the scale.
  We test with known AI / known human / borderline samples (M4) and adjust
  thresholds if scores don't match intuition.
- **Thresholds (false-positive averse):**
  - `confidence >= 0.70` → **likely AI**
  - `0.40 <= confidence < 0.70` → **uncertain**
  - `confidence < 0.40` → **likely human**
  The AI band starts high (0.70) so it is hard to wrongly flag a human.

### 3. Transparency label variants (final text)
- **High-confidence AI** (`confidence >= 0.70`):
  > 🤖 *This content is likely AI-generated.* Our analysis found strong signals
  > of automated writing (confidence: {pct}%). This is an automated estimate,
  > not a certainty — the creator can appeal.
- **High-confidence human** (`confidence < 0.40`):
  > ✍️ *This content appears to be human-written.* We found no strong signs of
  > AI generation (confidence it is human: {100-pct}%). This is an automated
  > estimate, not a guarantee.
- **Uncertain** (`0.40 <= confidence < 0.70`):
  > ❓ *We're not sure who wrote this.* Our signals were mixed, so we can't
  > confidently say whether it is AI-generated or human-written
  > (AI-likelihood: {pct}%). Treat this result with caution.

### 4. Appeals workflow
- **Who:** the creator of the content
- **Provides:** `content_id` + `creator_reasoning` (free text).
- **System does:** look up the content, set status to `under_review`, log the
  appeal next to the original decision (scores + label), return a confirmation.
- **Reviewer view:** opening the appeal queue (via `GET /log`) shows the
  original record — text id, scores, label — plus the creator's reasoning and
  the `under_review` status. No automated re-classification.

### 5. Anticipated edge cases
- **Repetitive simple-vocabulary poem:** low type-token ratio + uniform short
  lines push stylometrics toward "AI" even though a human wrote it → risk of a
  false positive. Mitigated by the wide uncertain band.
- **Lightly edited AI text:** human edits break the smooth AI pattern, so both
  signals soften and it lands mid-range (uncertain) — acceptable but not a
  clear catch.
- **Very short input (1–2 sentences):** stylometric stats are unreliable on
  little text; we will note this limitation and lean on the LLM signal there.

## AI Tool Plan
- **M3 (submission + Signal 1):** provided the *Detection signals* section +
  diagram. Ask for: Flask skeleton with `POST /submit` stub + the Groq signal
  function returning `llm_score`. Verify by calling the function directly on a
  few inputs and checking it returns a 0–1 float before wiring it in.
- **M4 (Signal 2 + scoring):** provide *Detection signals* + *Uncertainty
  representation* + diagram. Ask for: the stylometrics function + the combine
  logic. Verify the thresholds match this spec and that clearly-AI vs
  clearly-human inputs produce clearly different scores.
- **M5 (production layer):** provide *Transparency label variants* + *Appeals
  workflow* + diagram. Ask for: the label-mapping function + `POST /appeal`.
  Verify all 3 labels are reachable and that an appeal flips status to
  `under_review` and logs correctly.


- Rate limit: 10/min;100/day. A real creator submits a few pieces a day, so
  10/min is generous for humans but blocks a flooding script; 100/day caps
  sustained abuse while staying above any plausible single-writer day.
- Verified: 12 rapid requests -> ten 200s then 429s.
- Evidence files: `sample_audit_log.json` (3 entries incl. one appeal).
  
