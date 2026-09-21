"""FastAPI surface. Routing and validation only -- all logic lives in modules/."""
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import constants as C
from modules.brain.store import build_brain
from modules.chat.orchestrator import handle, handle_stream
from modules.llm.registry import available_providers
from modules.profile import service
from modules.session.store import build_sessions

app = FastAPI(title="MyNaksh Astrobot", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

brain, sessions = build_brain(), build_sessions()


class ChatIn(BaseModel):
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=4000)
    provider: str | None = None
    model: str | None = None


class ProfileIn(BaseModel):
    user_id: str = Field(min_length=1)
    name: str | None = None
    dob: str | None = None
    tob: str | None = None
    birth_place: str | None = None
    language: str | None = None


@app.post("/chat")
def chat(body: ChatIn):
    if body.provider and body.provider not in C.PROVIDER_MODELS:
        raise HTTPException(400, f"unknown provider '{body.provider}'")
    return handle(body.message, body.user_id, body.session_id, brain, sessions,
                  provider=body.provider, model=body.model)


@app.post("/chat/stream")
def chat_stream(body: ChatIn):
    """Server-sent events: one `context` event, then `token` events, then `done`.

    The done event carries the same payload as POST /chat, so a client can use
    either endpoint and get identical data -- one just arrives progressively.
    """
    if body.provider and body.provider not in C.PROVIDER_MODELS:
        raise HTTPException(400, f"unknown provider '{body.provider}'")

    def events():
        try:
            for kind, payload in handle_stream(body.message, body.user_id, body.session_id,
                                               brain, sessions, provider=body.provider,
                                               model=body.model):
                yield f"event: {kind}\ndata: {json.dumps(payload)}\n\n"
        except Exception as e:                   # noqa: BLE001 - never break the stream open
            yield f"event: error\ndata: {json.dumps({'detail': str(e)[:200]})}\n\n"

    # identity encoding stops an upstream proxy from gzipping the stream: Chrome's
    # gzip decoder buffers the whole body, which turns streaming back into one chunk.
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "Content-Encoding": "identity",
                                      "X-Accel-Buffering": "no"})


@app.post("/users")
def create_user(body: ProfileIn):
    return service.upsert(brain, body.user_id, body.model_dump())


@app.get("/users")
def list_users():
    return brain.list_users()


@app.get("/users/{user_id}")
def get_user(user_id: str):
    user = service.get(brain, user_id)
    if not user:
        raise HTTPException(404, f"no user '{user_id}'")
    return user


@app.get("/users/{user_id}/brain")
def get_brain(user_id: str):
    return brain.graph(user_id)


@app.get("/users/{user_id}/sessions")
def get_sessions(user_id: str):
    return sessions.sessions_for(user_id)


@app.get("/sessions/{session_id}/turns")
def get_turns(session_id: str):
    return [{k: v for k, v in t.items() if k != "embedding"}
            for t in sessions.last_turns(session_id, n=200)]


@app.delete("/users/{user_id}/memory")
def forget(user_id: str):
    brain.clear_memories(user_id)
    return {"cleared": True, "user_id": user_id}


@app.get("/evals")
def evals(run: str | None = None):
    """Latest eval results (or a named historical run) for the dashboard."""
    import pathlib
    d = pathlib.Path(__file__).parent / "evals" / "results"
    f = d / f"{run or 'latest'}.json"
    if not f.exists():
        raise HTTPException(404, "no eval results yet - run: python evals/run.py")
    return json.loads(f.read_text())


@app.get("/evals/datasets")
def eval_datasets():
    """The golden datasets the evals run against, so the dashboard can show them."""
    import pathlib
    d = pathlib.Path(__file__).parent / "evals"
    out = {"rules": (d / "rules.md").read_text() if (d / "rules.md").exists() else ""}
    for name in ("a", "b", "c"):
        f = d / "datasets" / f"set_{name}.json"
        if f.exists():
            out[name] = json.loads(f.read_text())
    return out


@app.get("/evals/runs")
def eval_runs():
    import pathlib
    d = pathlib.Path(__file__).parent / "evals" / "results"
    if not d.exists():
        return []
    return sorted((f.stem for f in d.glob("run-*.json")), reverse=True)


@app.get("/providers")
def providers():
    return available_providers()


@app.get("/health")
def health():
    return {"ok": True, "brain": brain.kind, "brain_healthy": brain.healthy(),
            "sessions": sessions.kind, "sessions_healthy": sessions.healthy()}
