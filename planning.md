# Planning

## Design Decisions

### <u>Detection Signals</u>

For this project, I will use two detection signals: an **LLM-based classifier and stylometric heuristics.**

The LLM-based classifier measures the overall semantic and stylistic impression of the text. It evaluates whether the writing appears more human-written or AI-generated based on phrasing, coherence, specificity, tone, and structure. Its output is an AI-probability score between 0 and 1, where 0 means strongly human-like and 1 means strongly AI-like.

The stylometric signal measures statistical properties of the text, such as sentence length variance, vocabulary diversity, punctuation density, and repetition. This signal is useful because AI-generated writing often has smoother and more uniform structure, while human writing often contains more variation. Its output is also an AI-probability score between 0 and 1, along with the underlying feature values used to calculate that score.

The two scores will be combined using a weighted average:

**combined_ai_probability = (0.65 * llm_score) + (0.35 * stylometric_score)**

I am weighting the LLM signal more heavily because it captures semantic and stylistic meaning that simple statistics cannot. However, the stylometric signal is still important because it provides an independent structural check rather than relying entirely on a model judgment.

The final combined score will determine the attribution label. Scores of 0.75 or higher will be labeled as likely AI-generated. Scores of 0.25 or lower will be labeled as likely human-written. Scores between 0.26 and 0.74 will be labeled uncertain, so the system does not force a confident verdict when the evidence is mixed.

### <u>Uncertainty Representation</u>

The system reports a confidence score between 0 and 1.

A score near 0 indicates the content appears human-written.

A score near 1 indicates the content appears AI-generated.

A score near 0.5 indicates mixed evidence from the detection signals.

For example, a confidence score of 0.60 means the system found slightly stronger evidence for AI-generated content, but not enough to make a confident attribution. The transparency label therefore remains uncertain rather than making a strong claim.


| Combined score | Result |
| :--- | :---: | 
| 0.00 – 0.25 | Likely Human | 
| 0.26 – 0.74 | Uncertain | 
| 0.75 – 1.00 | Likely AI | 

### <u>Transparency label design</u>

## High Confidence AI 
### Likely AI-Generated

> This content was classified as likely AI-generated with high confidence. This result is based on multiple automated detection signals and may be appealed by the creator.

## High Confidence Human 
### Likely Human-written

> This content appears to be human-written with high confidence. This assessment is based on multiple automated detection signals and is not a guarantee of authorship.

## Uncertain
### Uncertain attribution

> The system could not confidently determine whether this content was human-written or AI-generated. Readers should treat this label as additional context rather than a final judgment.

### <u>Appeals Workflow</u>

Any creator whose content has been classified may submit an appeal.

Each appeal includes:

* content ID
* creator explanation
* submission timestamp

When an appeal is received, the system:

* retrieves the original classification
* records the creator's explanation
* updates the content status to `under_review`
* creates a new audit log entry linked to the original decision

A human reviewer would see:

* original submitted text
* attribution result
* confidence score
* LLM score
* stylometric score
* transparency label shown to users
* creator's appeal explanation
* submission timestamps
* current review status

### <u>Anticipated edge cases</u>

* *Poetry* : Poems often use repetition, short phrases, and simple vocabulary intentionally. The stylometric heuristics may incorrectly classify these writing patterns as AI-generated.

* *Edited Professional writing* : A highly polished article written by an experienced author may appear unusually consistent and structured, causing the LLM classifier to overestimate the likelihood of AI generation.

* *AI writing that mimics human style* : Modern language models can intentionally produce uneven sentence lengths, personal anecdotes, or minor grammatical imperfections. These techniques may reduce the effectiveness of both detection signals.

* *Very short text* : Short submissions provide too little information for reliable stylometric analysis, making confidence scores less reliable. The system should therefore return lower confidence for very short content whenever possible.

## Architecture

### System Overview

#### Submission Flow

```{text}
  `POST /submit`
          |
          v
+---------------------------+
| Validation + Rate Limiter |
+---------------------------+
          |
          v
+----------------------+
| Detection Pipeline   |
+----------------------+
      /           \
     /             \
    v               v
+----------------+  +----------------------+
| LLM Classifier |  | Stylometric Analyzer |
| score: 0-1     |  | score: 0-1           |
+----------------+  +----------------------+
      \             /
       \           /
        v         v
+----------------------+
| Confidence Scoring   |
+----------------------+
          |
          v
+----------------------+
| Transparency Label   |
+----------------------+
          |
          v
+----------------------+
| Audit Log            |
+----------------------+
          |
          v
+----------------------+
| API Response         |
+----------------------+
```

#### Appeal Flow

```{text}

    `POST /appeal `    

          |
          v
+----------------------+
| Appeal Handler       |
+----------------------+
          |
          v
+----------------------+
| Update Status        |
| `under_review`   |
+----------------------+
          |
          v
+----------------------+
| Audit Log            |
+----------------------+
          |
          v
+----------------------+
| API Response         |
-----------------------+
```

### Flow Narrative

When a creator submits text through `POST /submit`, the API validates the request and applies rate limiting before sending the text through two independent detection signals: an LLM-based classifier and a stylometric analyzer. Their outputs are combined into a single confidence score, which determines the attribution result and the transparency label shown to readers. Every decision including the individual signal scores and final confidence, is stored in the audit log before the API returns the response.

If a creator believes their work was misclassified, they can submit an appeal through POST /appeal. The system records the creator's explanation, updates the content's status to `under_review`, logs the appeal alongside the original attribution decision, and returns a confirmation response without automatically reclassifying the content.


## Extra Credit Plan — Analytics Dashboard

### Goal

I will add a simple analytics dashboard so the project can summarize detection patterns and appeal activity from the existing audit log. This uses the same `audit_log.jsonl` file rather than adding a new database.

### Metrics

The dashboard will show:

* total number of submissions
* number of submissions by attribution result (`likely_ai`, `likely_human`, `uncertain`)
* number of appeals filed
* appeal rate, calculated as `appeals / submissions`
* average confidence score across submissions
* average LLM score and average stylometric score

The additional metric I chose is **average confidence score** because it helps show whether the system is producing mostly uncertain outputs or making stronger classifications. This is useful for debugging the detector and for understanding whether the transparency labels are too cautious or too aggressive.

### Dashboard Flow

```text
GET /analytics
        |
        v
Read audit_log.jsonl
        |
        v
Separate submission events from appeal events
        |
        v
Calculate detection counts, appeal rate, and average scores
        |
        v
Return structured JSON analytics

GET /dashboard
        |
        v
Read analytics summary
        |
        v
Render a simple HTML dashboard view
```

## AI Tool Plan
### M3 — Submission Endpoint + First Signal

*What I'll provide to AI tool:* the Architecture section and the Detection Signals section from this planning document. These sections explain the submission flow, the system components, and the expected output format for the first detection signal.

*What I'll ask it to generate:* a basic Flask app skeleton with a `POST /submit` endpoint and an initial LLM-based classification function. The function should accept raw text and return an AI probability score between 0 and 1, plus a short reasoning string.

*How verify?*: Before connecting the function fully to the endpoint, I will test it directly with a few sample inputs, including one clearly human-written example, one clearly AI-generated example, and one ambiguous example. I will verify that the function returns the correct data shape and that the score changes based on the input.

### M4 — Second Signal + Confidence Scoring

*What I'll provide to the AI tool:* the Detection Signals, Uncertainty Representation, and Architecture sections. These define the stylometric signal, confidence scoring strategy, decision thresholds, and where scoring fits into the overall system.

*What I'll ask it to generate:* A stylometric analysis function that computes features such as sentence length variance, vocabulary diversity, punctuation density, and sentence complexity, along with the confidence scoring logic that combines both signals using the weighted formula defined in this plan.

*How I'll verify:* I will test several writing samples that are clearly AI-generated, clearly human-written, and intentionally ambiguous. I will verify that the confidence scores vary meaningfully and that the final classifications follow the planned thresholds for likely AI, uncertain, and likely human.

### M5 — Production Layer

*What I'll provide to the AI tool:* The Transparency Label Design, Appeals Workflow, and Architecture sections. These describe the three label variants, the appeal process, and how the production components interact.

*What I'll ask it to generate:* The transparency label generation logic, the `POST /appeal` endpoint, status update functionality, and audit log integration. The endpoint should record the creator's reasoning, update the content status to `under_review`, and log the appeal alongside the original attribution decision.

*How I'll verify:* I will confirm that all three transparency label variants can be reached by testing different confidence scores. I will also submit a test appeal and verify that the content status changes to `under_review`, the creator's explanation is recorded, and both the original classification and appeal appear in the audit log.