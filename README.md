# Personal AI Trainer 🏋️ — Human in the Loop
**CWA Prompt-a-thon 2026 | The Twist: Confidence Scores + Human Override**

---

## The Twist — Implemented
> *Every AI output must display a confidence score or uncertainty indicator.
> The user must be able to override or correct the AI — with the AI
> acknowledging or adapting to that correction in the same session.*

**How it works:**
1. ConfidenceAgent scores every section of the plan (0–100%)
2. Each score shows the reason + uncertainty factors
3. User types corrections into the override form
4. AdaptAgent acknowledges each correction by name and regenerates affected sections
5. Updated confidence scores are shown — they go up after human input

**Demo video timestamp guide:**
- 0:00 → Show goal input, hit "Build My Plan"
- 0:20 → Watch 5 agents light up in sequence
- 0:50 → Show the confidence score cards (THE TWIST)
- 1:10 → Type a correction into one of the override fields
- 1:20 → Hit "Submit Corrections" — watch AdaptAgent respond
- 1:40 → Show acknowledgement cards + updated confidence scores
- 1:55 → Show downloaded artifacts

---

## 6-Agent Pipeline

```
User Goal
    │
    ▼
ProfilerAgent      extract level, style, time, goal type
    │
    ▼
ResearchAgent      skill gaps, best approach, risk factors
    │
    ▼
PlannerAgent       day-by-day weekly plan, milestones, resources
    │
    ▼
ExecutorAgent      create schedule file, daily task checklist (real files)
    │
    ▼
ConfidenceAgent ★  score each section 0-100%, explain uncertainty
    │
    [Human Override]
    ▼
AdaptAgent ★       acknowledge corrections, regenerate affected sections
```

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
uvicorn main:app --reload --port 8000
```

---

## API Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web UI |
| `/train/stream` | POST | Run 5-agent pipeline via SSE |
| `/override/stream` | POST | Submit corrections, AdaptAgent responds |
| `/artifact/{name}` | GET | Download generated file |
| `/artifact/{name}/content` | GET | Preview file in UI |
| `/health` | GET | Agent list |

---
*CWA Prompt-a-thon 2026 | codewithahsan.dev*
