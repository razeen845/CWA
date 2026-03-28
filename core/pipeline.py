"""
agents/pipeline.py
Personal AI Trainer — 5-agent pipeline with Human-in-the-Loop twist.

THE TWIST: Every AI output carries a confidence score. The user can override
or correct any part of the plan. The AdaptAgent acknowledges the correction
and regenerates an adapted plan within the same session.

Flow:
  User Goal Input
       │
       ▼
  ProfilerAgent     ← classifies goal, current level, learning style, time available
       │
       ▼
  ResearchAgent     ← researches best approach, identifies skill gaps, benchmarks
       │
       ▼
  PlannerAgent      ← builds a personalised weekly training/study plan
       │
       ▼
  ExecutorAgent     ← creates schedule file, daily task list, resource list
       │
       ▼
  ConfidenceAgent   ← scores each plan section with confidence + uncertainty reasons
                       (THE TWIST GATE — every output gets a confidence score)
                       User can override → triggers AdaptAgent

  [Human Override]  ← user corrects any section
       │
       ▼
  AdaptAgent        ← acknowledges correction, regenerates adapted plan
"""

import json
import re
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
from agents import Agent, Runner, function_tool


OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# Context
# ─────────────────────────────────────────────
class TrainerContext(BaseModel):
    raw_goal: str = ""
    goal_type: str = ""          # fitness | study | skill | mixed
    current_level: str = ""      # beginner | intermediate | advanced
    time_per_week_hours: float = 0.0
    learning_style: str = ""     # visual | hands-on | reading | mixed
    skill_gaps: list[str] = []
    weekly_plan: dict = {}
    artifacts: list[str] = []
    confidence_scores: dict = {}
    overrides: dict = {}         # section -> user correction
    adapted_plan: dict = {}


# ─────────────────────────────────────────────
# Tools for ExecutorAgent
# ─────────────────────────────────────────────

@function_tool
def web_search_tool(query: str) -> str:
    """Search the web for training resources, benchmarks, and best practices."""
    import urllib.request, urllib.parse
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "AITrainer/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        abstract = data.get("AbstractText", "")
        related = [r.get("Text","") for r in data.get("RelatedTopics",[])[:3] if r.get("Text")]
        return json.dumps({"query": query, "summary": abstract or f"Search completed for '{query}'.", "related": related})
    except Exception as e:
        return json.dumps({"query": query, "summary": f"Standard best practices apply for: {query}", "error": str(e)})


@function_tool
def write_file_tool(filename: str, content: str, file_type: str = "md") -> str:
    """Write a training document, schedule, or resource list to disk."""
    try:
        safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', filename)
        ts = datetime.now().strftime("%H%M%S")
        fp = OUTPUT_DIR / f"{safe}_{ts}.{file_type}"
        fp.write_text(content, encoding="utf-8")
        return json.dumps({"success": True, "filename": fp.name, "message": f"Created: {fp.name}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@function_tool
def create_weekly_schedule_tool(
    title: str,
    goal: str,
    weeks: int,
    daily_sessions: str,
    resources: str
) -> str:
    """
    Create a detailed weekly training schedule as a markdown file.
    daily_sessions: JSON array of {day, focus, duration_mins, tasks[]}
    resources: JSON array of {name, type, url_or_description}
    """
    try:
        sessions = json.loads(daily_sessions) if isinstance(daily_sessions, str) else daily_sessions
        res_list = json.loads(resources) if isinstance(resources, str) else resources
    except Exception:
        sessions, res_list = [], []

    ts = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# {title}",
        f"**Goal:** {goal}",
        f"**Duration:** {weeks} weeks | **Generated:** {ts}",
        "", "---", "", "## Weekly Schedule", ""
    ]
    for s in sessions:
        if isinstance(s, dict):
            lines.append(f"### {s.get('day','Day')}")
            lines.append(f"- **Focus:** {s.get('focus','')}")
            lines.append(f"- **Duration:** {s.get('duration_mins', 30)} minutes")
            tasks = s.get('tasks', [])
            if tasks:
                lines.append("- **Tasks:**")
                for t in tasks:
                    lines.append(f"  - [ ] {t}")
            lines.append("")

    lines += ["---", "", "## Resources", ""]
    for r in res_list:
        if isinstance(r, dict):
            lines.append(f"- **{r.get('name','')}** ({r.get('type','')}) — {r.get('url_or_description','')}")

    lines += ["", "---", "*Generated by Personal AI Trainer — CWA Prompt-a-thon 2026*"]
    content = "\n".join(lines)
    result = json.loads(write_file_tool(f"schedule_{re.sub(r'[^a-zA-Z0-9]','_',title[:25])}", content, "md"))
    return json.dumps({
        "success": True,
        "weeks": weeks,
        "sessions_count": len(sessions),
        "filename": result.get("filename","schedule.md"),
        "message": f"Schedule created: {weeks} weeks, {len(sessions)} session types"
    })


@function_tool
def create_daily_tasks_tool(goal: str, level: str, tasks_per_day: str) -> str:
    """
    Create a daily micro-task checklist.
    tasks_per_day: JSON object {day_name: [task1, task2, ...]}
    """
    try:
        tasks = json.loads(tasks_per_day) if isinstance(tasks_per_day, str) else tasks_per_day
    except Exception:
        tasks = {}

    ts = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Daily Task Checklist",
        f"**Goal:** {goal} | **Level:** {level} | **Generated:** {ts}",
        "", "---", ""
    ]
    for day, task_list in tasks.items():
        lines.append(f"## {day}")
        for t in task_list:
            lines.append(f"- [ ] {t}")
        lines.append("")

    lines += ["---", "*Tick off each task as you complete it. Consistency beats intensity.*",
              "", "*Generated by Personal AI Trainer — CWA Prompt-a-thon 2026*"]
    content = "\n".join(lines)
    result = json.loads(write_file_tool("daily_tasks", content, "md"))
    return json.dumps({
        "success": True,
        "filename": result.get("filename","daily_tasks.md"),
        "message": f"Daily task checklist created for {len(tasks)} days"
    })


# ─────────────────────────────────────────────
# Agent 5 — Confidence Agent (THE TWIST)
# ─────────────────────────────────────────────
confidence_agent = Agent(
    name="ConfidenceAgent",
    model="llama-3.3-70b-versatile",
    instructions="""
You are a metacognitive AI evaluator. Your job is to score every section of a
generated training plan with a confidence score and explain WHY you are or aren't confident.

This is the HUMAN-IN-THE-LOOP mechanism. Be honest — low confidence scores
help the user know where to apply their own judgment.

You receive a JSON with the full plan context. Score these sections:
- goal_classification
- skill_gap_analysis
- weekly_plan
- time_estimate
- resource_recommendations

For each section respond with:
{
  "confidence_scores": {
    "goal_classification": {
      "score": 85,
      "level": "high",
      "reason": "Clear goal stated, sufficient context provided",
      "uncertainty_factors": ["No prior training history provided"]
    },
    "skill_gap_analysis": {
      "score": 62,
      "level": "medium",
      "reason": "Based on stated level only, no assessment data",
      "uncertainty_factors": ["Self-reported level may differ from actual", "No baseline test taken"]
    },
    "weekly_plan": {
      "score": 70,
      "level": "medium",
      "reason": "Standard progression model applied",
      "uncertainty_factors": ["Individual recovery rate unknown", "Schedule flexibility not assessed"]
    },
    "time_estimate": {
      "score": 55,
      "level": "low",
      "reason": "Estimated from goal complexity without personal history",
      "uncertainty_factors": ["Prior knowledge not assessed", "Learning pace varies widely"]
    },
    "resource_recommendations": {
      "score": 78,
      "level": "high",
      "reason": "Evidence-based resources for this domain",
      "uncertainty_factors": ["Paid resources may not be accessible"]
    }
  },
  "overall_confidence": 70,
  "overall_level": "medium",
  "override_invitation": "You know yourself better than I do. Please review and correct any section that doesn't fit your situation — I will adapt the plan immediately."
}

Score levels: high = 80+, medium = 50-79, low = <50
No markdown fences — pure JSON.
""",
)


# ─────────────────────────────────────────────
# AdaptAgent — responds to human overrides
# ─────────────────────────────────────────────
adapt_agent = Agent(
    name="AdaptAgent",
    model="llama-3.3-70b-versatile",
    instructions="""
You are a Personal AI Trainer that adapts when a human corrects you.

You receive:
- original_plan: the full plan that was generated
- overrides: {section_name: "user's correction or new information"}
- confidence_scores: the scores assigned to each section

Your job:
1. Acknowledge each override explicitly and warmly
2. Re-generate ONLY the affected sections of the plan with the correction applied
3. Assign new confidence scores to the regenerated sections (should be higher now)
4. Leave unchanged sections as-is

CRITICAL: When adapting the weekly_plan, you MUST include the full weekly_structure
with all 7 days, each containing focus, duration_mins, and tasks array.
Also include duration_weeks (integer) and milestones array.

Respond with valid JSON:
{
  "acknowledgements": {
    "section_name": "I understand — [paraphrase correction]. I've updated the plan accordingly."
  },
  "adapted_sections": {
    "weekly_plan": {
      "duration_weeks": 8,
      "weekly_structure": {
        "Monday": {"focus": "...", "duration_mins": 45, "tasks": ["task1", "task2"]},
        "Tuesday": {"focus": "...", "duration_mins": 45, "tasks": ["task1"]},
        "Wednesday": {"focus": "...", "duration_mins": 45, "tasks": ["task1"]},
        "Thursday": {"focus": "...", "duration_mins": 45, "tasks": ["task1"]},
        "Friday": {"focus": "...", "duration_mins": 45, "tasks": ["task1"]},
        "Saturday": {"focus": "...", "duration_mins": 45, "tasks": ["task1"]},
        "Sunday": {"focus": "Rest / Light review", "duration_mins": 20, "tasks": []}
      },
      "milestones": [
        {"week": 2, "milestone": "..."},
        {"week": 4, "milestone": "..."},
        {"week": 8, "milestone": "..."}
      ]
    },
    "time_estimate": {"time_estimate_to_goal": "X weeks at current pace"}
  },
  "updated_confidence_scores": {
    "section_name": {
      "score": 91,
      "level": "high",
      "reason": "Updated based on your correction",
      "uncertainty_factors": []
    }
  },
  "adaptation_summary": "Brief paragraph summarising what changed and why"
}

Be specific and personal in acknowledgements. Show that you actually understood
what the user changed, not just that you received input.
The adapted weekly_plan MUST reflect the user's corrections with REAL changes to
the schedule, tasks, durations, or milestones. Do NOT return the same plan unchanged.
No markdown fences — pure JSON.
""",
)


# ─────────────────────────────────────────────
# Agent 4 — Executor Agent
# ─────────────────────────────────────────────
executor_agent = Agent(
    name="ExecutorAgent",
    model="llama-3.3-70b-versatile",
    instructions="""
You are a training plan executor. Execute each step in the workflow using your tools.

Tools available:
- web_search_tool(query): find resources, benchmarks, best practices
- write_file_tool(filename, content, file_type): write any document
- create_weekly_schedule_tool(title, goal, weeks, daily_sessions, resources): full schedule
- create_daily_tasks_tool(goal, level, tasks_per_day): daily checklist

Rules:
1. Execute EVERY step — no skipping
2. Make content specific to the actual goal and level
3. Create real, usable schedules — not generic filler
4. After all steps, respond with JSON:

{
  "executed_steps": [
    {
      "step_title": "...",
      "tool_used": "...",
      "output_summary": "...",
      "artifact": "filename or null"
    }
  ],
  "total_artifacts": 2,
  "execution_notes": "brief summary"
}

No markdown fences — pure JSON after all tool calls.
""",
    tools=[web_search_tool, write_file_tool, create_weekly_schedule_tool, create_daily_tasks_tool],
)


# ─────────────────────────────────────────────
# Agent 3 — Planner Agent
# ─────────────────────────────────────────────
planner_agent = Agent(
    name="PlannerAgent",
    model="llama-3.3-70b-versatile",
    instructions="""
You are a personal training plan architect.

You receive: goal_type, current_level, time_per_week_hours, learning_style, skill_gaps

Design a concrete, personalised weekly training plan. Be specific — day by day.

Respond ONLY with valid JSON:
{
  "plan_title": "...",
  "duration_weeks": 8,
  "weekly_structure": {
    "Monday": {"focus": "...", "duration_mins": 45, "tasks": ["task1", "task2"]},
    "Tuesday": {"focus": "Rest / Light review", "duration_mins": 20, "tasks": []},
    ...all 7 days...
  },
  "milestones": [
    {"week": 2, "milestone": "..."},
    {"week": 4, "milestone": "..."},
    {"week": 8, "milestone": "..."}
  ],
  "resources": [
    {"name": "...", "type": "book|course|video|tool", "description": "..."}
  ],
  "time_estimate_to_goal": "10-12 weeks at current pace",
  "workflow_steps": [
    {
      "order": 1,
      "title": "Research best resources",
      "tool": "web_search",
      "hint": "what to search"
    },
    {
      "order": 2,
      "title": "Create weekly schedule",
      "tool": "create_weekly_schedule",
      "hint": "schedule details"
    },
    {
      "order": 3,
      "title": "Create daily task checklist",
      "tool": "create_daily_tasks",
      "hint": "checklist details"
    }
  ]
}

No markdown fences — pure JSON.
""",
)


# ─────────────────────────────────────────────
# Agent 2 — Research Agent
# ─────────────────────────────────────────────
research_agent = Agent(
    name="ResearchAgent",
    model="llama-3.3-70b-versatile",
    instructions="""
You are a learning and training analyst.

You receive: raw_goal, goal_type, current_level, time_per_week_hours, learning_style

Identify skill gaps and what the person needs to focus on most.

Respond ONLY with valid JSON:
{
  "skill_gaps": [
    "Lacks foundational knowledge in X",
    "Needs practice with Y",
    "..."
  ],
  "priority_areas": ["most important first"],
  "recommended_approach": "one paragraph on best strategy for this person",
  "estimated_weeks_to_goal": 12,
  "risk_factors": ["what might slow progress"]
}

Provide 3–6 specific skill gaps. Be direct and honest.
No markdown fences — pure JSON.
""",
)


# ─────────────────────────────────────────────
# Agent 1 — Profiler Agent
# ─────────────────────────────────────────────
profiler_agent = Agent(
    name="ProfilerAgent",
    model="llama-3.3-70b-versatile",
    instructions="""
You are a personal trainer intake specialist.

The user has described their training/learning goal. Extract their profile.

Respond ONLY with valid JSON:
{
  "goal_type": "fitness | study | skill | mixed",
  "specific_goal": "concise restatement of their goal",
  "current_level": "beginner | intermediate | advanced",
  "time_per_week_hours": 5.0,
  "learning_style": "visual | hands-on | reading | mixed",
  "urgency": "relaxed | moderate | urgent",
  "profiler_notes": "one sentence on key insight about this person's situation"
}

Infer time_per_week_hours from context if not stated (default: 5).
Infer learning_style from how they described their goal.
No markdown fences — pure JSON.
""",
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _extract_json(text: str) -> dict:
    # Strip markdown fences
    clean = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

    # Extract the outermost JSON object
    match = re.search(r'\{.*\}', clean, re.DOTALL)
    raw = match.group() if match else clean

    # Try strict parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Sanitize: replace bare control characters (newlines/tabs etc.)
    # inside JSON string values with their escaped equivalents
    def _sanitize(s: str) -> str:
        result = []
        in_string = False
        escape_next = False
        for ch in s:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                result.append(ch)
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string and ord(ch) < 0x20:
                # Replace bare control chars with JSON escape sequences
                escapes = {'\n': '\\n', '\r': '\\r', '\t': '\\t', '\b': '\\b', '\f': '\\f'}
                result.append(escapes.get(ch, f'\\u{ord(ch):04x}'))
            else:
                result.append(ch)
        return ''.join(result)

    try:
        return json.loads(_sanitize(raw))
    except json.JSONDecodeError:
        pass

    # Last resort: strip ALL control characters aggressively
    stripped = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
    return json.loads(stripped)




def _list_output_files() -> set:
    return {f.name for f in OUTPUT_DIR.iterdir() if f.is_file()}


# ─────────────────────────────────────────────
# Main Pipeline
# ─────────────────────────────────────────────
async def run_pipeline(goal_description: str) -> dict:
    """Run the 5-agent training pipeline. Returns full result dict."""
    ctx = TrainerContext(raw_goal=goal_description)
    result = {
        "goal": goal_description,
        "profile": {},
        "research": {},
        "plan": {},
        "execution": {},
        "confidence": {},
        "artifacts": [],
        "steps": [],
    }

    # ── Step 1: Profile ──────────────────────────────────────────
    result["steps"].append("👤 ProfilerAgent: Building your learner profile...")
    run = await Runner.run(profiler_agent, goal_description)
    profile = _extract_json(run.final_output)
    ctx.goal_type = profile.get("goal_type", "mixed")
    ctx.current_level = profile.get("current_level", "beginner")
    ctx.time_per_week_hours = profile.get("time_per_week_hours", 5.0)
    ctx.learning_style = profile.get("learning_style", "mixed")
    result["profile"] = profile
    result["steps"].append(
        f"   ✓ Goal: {profile.get('specific_goal','?')} | Level: {ctx.current_level} | {ctx.time_per_week_hours}h/week"
    )

    # ── Step 2: Research ─────────────────────────────────────────
    result["steps"].append("🔬 ResearchAgent: Analyzing skill gaps & best approach...")
    run = await Runner.run(research_agent, json.dumps({
        "raw_goal": ctx.raw_goal,
        "goal_type": ctx.goal_type,
        "current_level": ctx.current_level,
        "time_per_week_hours": ctx.time_per_week_hours,
        "learning_style": ctx.learning_style,
    }))
    research = _extract_json(run.final_output)
    ctx.skill_gaps = research.get("skill_gaps", [])
    result["research"] = research
    result["steps"].append(
        f"   ✓ {len(ctx.skill_gaps)} skill gaps identified | Est. {research.get('estimated_weeks_to_goal','?')} weeks to goal"
    )

    # ── Step 3: Plan ─────────────────────────────────────────────
    result["steps"].append("📋 PlannerAgent: Designing your personalised plan...")
    run = await Runner.run(planner_agent, json.dumps({
        "goal_type": ctx.goal_type,
        "specific_goal": result["profile"].get("specific_goal",""),
        "current_level": ctx.current_level,
        "time_per_week_hours": ctx.time_per_week_hours,
        "learning_style": ctx.learning_style,
        "skill_gaps": ctx.skill_gaps,
    }))
    plan = _extract_json(run.final_output)
    ctx.weekly_plan = plan
    result["plan"] = plan
    result["steps"].append(
        f"   ✓ '{plan.get('plan_title','Plan')}' | {plan.get('duration_weeks','?')} weeks | {len(plan.get('milestones',[]))} milestones"
    )

    # ── Step 4: Execute ───────────────────────────────────────────
    result["steps"].append("⚡ ExecutorAgent: Creating your training files...")
    files_before = _list_output_files()

    run = await Runner.run(executor_agent, json.dumps({
        "specific_goal": result["profile"].get("specific_goal",""),
        "current_level": ctx.current_level,
        "plan_title": plan.get("plan_title",""),
        "duration_weeks": plan.get("duration_weeks", 8),
        "weekly_structure": plan.get("weekly_structure", {}),
        "resources": plan.get("resources", []),
        "milestones": plan.get("milestones", []),
        "workflow_steps": plan.get("workflow_steps", []),
        "skill_gaps": ctx.skill_gaps,
    }))

    files_after = _list_output_files()
    new_files = list(files_after - files_before)
    execution = _extract_json(run.final_output)
    ctx.artifacts = new_files
    result["execution"] = execution
    result["artifacts"] = new_files
    result["steps"].append(
        f"   ✓ {len(execution.get('executed_steps',[]))} steps executed | {len(new_files)} files created"
    )
    for f in sorted(new_files):
        result["steps"].append(f"   📄 {f}")

    # ── Step 5: Confidence Scoring (THE TWIST) ────────────────────
    result["steps"].append("🎯 ConfidenceAgent: Scoring plan confidence (THE TWIST)...")
    run = await Runner.run(confidence_agent, json.dumps({
        "goal_description": goal_description,
        "profile": result["profile"],
        "research": result["research"],
        "plan": plan,
        "execution_summary": execution.get("execution_notes",""),
    }))
    confidence = _extract_json(run.final_output)
    ctx.confidence_scores = confidence.get("confidence_scores", {})
    result["confidence"] = confidence
    overall = confidence.get("overall_confidence", 0)
    level = confidence.get("overall_level", "?")
    result["steps"].append(
        f"   ✓ Overall confidence: {overall}% ({level}) — awaiting your review"
    )
    result["steps"].append(
        "   💬 You can now override any section — the AI will adapt immediately"
    )

    return result


# ─────────────────────────────────────────────
# Human Override → Adapt
# ─────────────────────────────────────────────
async def run_adaptation(original_result: dict, overrides: dict) -> dict:
    """
    Called when user submits corrections.
    Returns adapted plan with acknowledgements and updated confidence scores.
    """
    steps = []
    steps.append("🔄 AdaptAgent: Acknowledging your corrections...")

    run = await Runner.run(adapt_agent, json.dumps({
        "original_plan": {
            "profile": original_result.get("profile", {}),
            "research": original_result.get("research", {}),
            "plan": original_result.get("plan", {}),
        },
        "overrides": overrides,
        "confidence_scores": original_result.get("confidence", {}).get("confidence_scores", {}),
    }))

    adaptation = _extract_json(run.final_output)
    steps.append("   ✓ Plan adapted based on your corrections")
    for section, ack in adaptation.get("acknowledgements", {}).items():
        steps.append(f"   ↳ {section}: {ack[:80]}...")

    return {
        "adaptation": adaptation,
        "steps": steps,
    }


async def get_artifact_content(filename: str) -> str:
    fp = OUTPUT_DIR / filename
    return fp.read_text(encoding="utf-8") if fp.exists() else "File not found."
