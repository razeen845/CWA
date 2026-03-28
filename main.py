"""
main.py — Personal AI Trainer FastAPI app
"""

import os, json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise EnvironmentError("OPENAI_API_KEY not set...")

# Point SDK to Groq BEFORE importing agents
import os
import openai
from agents import set_default_openai_api, set_default_openai_client
from openai import AsyncOpenAI

openai.api_key = os.getenv("OPENAI_API_KEY")
openai.base_url = "https://api.groq.com/openai/v1"

# Groq uses chat.completions — NOT the new Responses API
set_default_openai_api("chat_completions")
set_default_openai_client(AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
))

from core.pipeline import run_pipeline, run_adaptation, get_artifact_content, OUTPUT_DIR
app = FastAPI(title="Personal AI Trainer", version="1.0.0")
Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── In-memory session store (single-user hackathon demo) ──
session_store: dict = {}


class GoalRequest(BaseModel):
    goal: str

class OverrideRequest(BaseModel):
    session_id: str
    overrides: dict   # {section_name: "user correction text"}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("templates/index.html", encoding= "utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/train/stream")
async def train_stream(req: GoalRequest):
    """SSE stream — runs pipeline and yields live step updates + final result."""
    async def gen():
        try:
            if not req.goal.strip():
                yield f"data: {json.dumps({'error': 'Empty goal'})}\n\n"
                return
            result = await run_pipeline(req.goal.strip())
            session_id = str(abs(hash(req.goal.strip())))
            session_store[session_id] = result
            for step in result["steps"]:
                yield f"data: {json.dumps({'step': step})}\n\n"
            yield f"data: {json.dumps({'done': True, 'result': result, 'session_id': session_id})}\n\n"
        except Exception as e:
            import traceback
            err_msg = f"{type(e).__name__}: {str(e)}"
            print("[train/stream ERROR]", traceback.format_exc())
            yield f"data: {json.dumps({'error': err_msg})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/override/stream")
async def override_stream(req: OverrideRequest):
    """SSE stream — user submits corrections, AdaptAgent responds."""
    async def gen():
        try:
            original = session_store.get(req.session_id)
            if not original:
                yield f"data: {json.dumps({'error': 'Session not found. Please re-run the analysis.'})}\n\n"
                return
            adaptation_result = await run_adaptation(original, req.overrides)
            session_store[req.session_id]["adaptation"] = adaptation_result["adaptation"]
            for step in adaptation_result["steps"]:
                yield f"data: {json.dumps({'step': step})}\n\n"
            yield f"data: {json.dumps({'done': True, 'adaptation': adaptation_result['adaptation']})}\n\n"
        except Exception as e:
            import traceback
            err_msg = f"{type(e).__name__}: {str(e)}"
            print("[override/stream ERROR]", traceback.format_exc())
            yield f"data: {json.dumps({'error': err_msg})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/artifact/{filename}")
async def download_artifact(filename: str):
    safe = Path(filename).name
    fp = OUTPUT_DIR / safe
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(fp), filename=safe, media_type="text/plain")


@app.get("/artifact/{filename}/content")
async def artifact_content(filename: str):
    safe = Path(filename).name
    content = await get_artifact_content(safe)
    return {"filename": safe, "content": content}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agents": ["ProfilerAgent", "ResearchAgent", "PlannerAgent",
                   "ExecutorAgent", "ConfidenceAgent (TWIST)", "AdaptAgent (TWIST)"]
    }
