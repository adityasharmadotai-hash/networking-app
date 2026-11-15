"""Chief of Staff dashboard server.

    cd chief-of-staff
    pip install -r requirements.txt
    cp .env.example .env    # add GEMINI_API_KEY etc.
    python app.py           # open http://localhost:8000
"""
import base64
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from core import config, store  # noqa: E402
from core.agents import AGENTS, public  # noqa: E402
from core.runner import run_in_background, statuses  # noqa: E402
from tools import gmail  # noqa: E402

app = FastAPI(title="Chief of Staff")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def password_gate(request: Request, call_next):
    if config.APP_PASSWORD:
        ok = False
        auth = request.headers.get("authorization", "")
        if auth.startswith("Basic "):
            try:
                _, _, pw = base64.b64decode(auth[6:]).decode().partition(":")
                ok = secrets.compare_digest(pw, config.APP_PASSWORD)
            except Exception:
                ok = False
        if not ok:
            return JSONResponse({"detail": "auth required"}, status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="Chief of Staff"'})
    return await call_next(request)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/agents")
def agents():
    return {"agents": [public(a) for a in AGENTS],
            "user": {"name": config.SENDER_NAME or "You", "title": config.USER_TITLE},
            "integrations": {
        "gemini": bool(config.GEMINI_API_KEY),
        "hubspot": bool(config.HUBSPOT_ACCESS_TOKEN),
        "gmail": gmail.is_connected(),
        "hunter": bool(config.HUNTER_API_KEY),
        "auto_send": config.AUTO_SEND_EMAIL,
    }}


@app.get("/api/state")
def state(agent: str, after: int = 0):
    if agent not in AGENTS:
        raise HTTPException(404, "unknown agent")
    return {
        "status": statuses(),
        "messages": store.get_messages(agent, after),
        "approvals": store.list_approvals("pending"),
        "activity": store.recent_activity(25),
        "previews": store.previews(),
    }


class ChatIn(BaseModel):
    text: str


@app.post("/api/agents/{agent_id}/chat")
def chat(agent_id: str, body: ChatIn):
    if agent_id not in AGENTS:
        raise HTTPException(404, "unknown agent")
    if not body.text.strip():
        raise HTTPException(400, "empty message")
    if statuses()[agent_id]["state"] == "working":
        raise HTTPException(409, f"{AGENTS[agent_id]['name']} is still working on the previous request.")
    run_in_background(agent_id, body.text.strip())
    return {"ok": True}


@app.delete("/api/agents/{agent_id}/messages")
def clear(agent_id: str):
    if agent_id not in AGENTS:
        raise HTTPException(404, "unknown agent")
    store.clear_thread(agent_id)
    return {"ok": True}


class ApprovalIn(BaseModel):
    to: str | None = None
    subject: str | None = None
    body: str | None = None


@app.post("/api/approvals/{approval_id}/{decision}")
def decide(approval_id: int, decision: str, edits: ApprovalIn | None = None):
    ap = store.get_approval(approval_id)
    if not ap or ap["status"] != "pending":
        raise HTTPException(404, "approval not found or already decided")
    p = ap["payload"]
    if edits:
        p.update({k: v for k, v in edits.model_dump().items() if v})
    if decision == "reject":
        store.set_approval(approval_id, "rejected")
        store.add_message(ap["agent_id"], "tool", "system", "approval",
                          {"ok": False, "result": f"You rejected the email to {p['to']}."})
        return {"ok": True}
    if decision != "approve":
        raise HTTPException(400, "decision must be approve or reject")
    try:
        res = gmail.send_now(p["to"], p["subject"], p["body"], p.get("cc", ""))
        store.set_approval(approval_id, "approved", str(res))
        store.add_message(ap["agent_id"], "tool", "system", "approval",
                          {"ok": True, "result": f"Email to {p['to']} approved and sent: \"{p['subject']}\""})
        return {"ok": True, "result": res}
    except Exception as e:  # stays pending so you can retry after fixing Gmail
        raise HTTPException(500, f"Send failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.env("HOST", "127.0.0.1"), port=int(config.env("PORT", "8000")))
