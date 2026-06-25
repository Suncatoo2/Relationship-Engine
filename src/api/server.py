"""FastAPI Web 服务"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from ..engine import RelationshipEngine

app = FastAPI(title="Relationship Engine", version="0.1.0")

DATA_DIR = os.getenv("DATA_DIR", "data")
engine = RelationshipEngine(data_dir=DATA_DIR)

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


class ChatRequest(BaseModel):
    message: str
    person_name: str = ""


class AddPersonRequest(BaseModel):
    name: str
    relationship_type: str = "朋友"
    notes: str = ""
    birthday: str = ""


class RememberRequest(BaseModel):
    person_name: str
    content: str
    category: str = "general"
    importance: int = 5


class UpdateRelationRequest(BaseModel):
    person_name: str
    stage: str = ""
    chemistry_delta: int = 0
    event: str = ""


# ---- 页面 ----

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


# ---- API ----

@app.get("/api/dashboard")
async def dashboard():
    return engine.get_dashboard()


@app.post("/api/chat")
async def chat(req: ChatRequest):
    reply = engine.chat(req.message, req.person_name)
    return {"reply": reply}


@app.post("/api/people")
async def add_person(req: AddPersonRequest):
    result = engine.quick_add_person(req.name, req.relationship_type, req.notes)
    if req.birthday:
        engine.memory.update_person(req.name, birthday=req.birthday)
    return result


@app.get("/api/people")
async def list_people():
    return [p.model_dump() for p in engine.memory.list_people()]


@app.get("/api/people/{name}")
async def get_person(name: str):
    profile = engine.memory.get_person(name)
    if not profile:
        return {"error": "not found"}
    rel = engine.tracker.get(name)
    conv = engine.conversation.get_recent(name, 20)
    return {
        "profile": profile.model_dump(),
        "relationship": rel.model_dump() if rel else None,
        "recent_messages": [m.model_dump() for m in conv],
    }


@app.post("/api/remember")
async def remember(req: RememberRequest):
    return engine.quick_remember(req.person_name, req.content, req.category)


@app.post("/api/relationship/update")
async def update_relationship(req: UpdateRelationRequest):
    if req.stage:
        engine.tracker.update_stage(req.person_name, req.stage)
    if req.chemistry_delta:
        engine.tracker.update_chemistry(req.person_name, req.chemistry_delta)
    if req.event:
        engine.tracker.add_event(req.person_name, req.event)
    rel = engine.tracker.get(req.person_name)
    return rel.model_dump() if rel else {"error": "not found"}


@app.get("/api/reminders")
async def reminders():
    return engine.tracker.get_reminders()


@app.get("/api/stats")
async def stats():
    return {
        "memory": engine.memory.stats(),
        "relationships": engine.tracker.stats(),
    }
