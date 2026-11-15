"""The agent loop: Gemini function calling with every step logged to the agent's thread."""
import json
import threading

from google.genai import types

from . import config, store, toolbox
from .agents import AGENTS, system_prompt
from .gemini import client

_status = {aid: {"state": "idle", "detail": ""} for aid in AGENTS}
_status_lock = threading.Lock()


def set_status(agent_id, state, detail=""):
    with _status_lock:
        _status[agent_id] = {"state": state, "detail": detail}


def statuses():
    with _status_lock:
        return {k: dict(v) for k, v in _status.items()}


def _history_contents(agent_id):
    contents = []
    for m in store.chat_history(agent_id):
        role = "model" if m["role"] == "assistant" else "user"
        text = m["content"]
        if role == "user" and m["sender"] != "you":
            sender = AGENTS.get(m["sender"], {}).get("name", m["sender"])
            text = f"[Message from {sender}, your teammate]\n{text}"
        if contents and contents[-1].role == role:
            contents[-1].parts.append(types.Part(text=text))
        else:
            contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    while contents and contents[0].role != "user":
        contents.pop(0)
    return contents


def _short(obj, n=4000):
    s = json.dumps(obj, default=str, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + "...(truncated)"


def run_agent(agent_id, text, sender="you", depth=0):
    """Run one turn for an agent and return its final reply (also stored)."""
    agent = AGENTS[agent_id]
    store.add_message(agent_id, "user", sender, text)
    set_status(agent_id, "working", "Thinking…")
    try:
        contents = _history_contents(agent_id)
        cfg = types.GenerateContentConfig(
            system_instruction=system_prompt(agent_id),
            tools=[types.Tool(function_declarations=toolbox.declarations(agent["tools"]))],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        for _ in range(config.MAX_TOOL_STEPS):
            resp = client().models.generate_content(model=agent["model"], contents=contents, config=cfg)
            calls = resp.function_calls or []
            if not calls:
                reply = (resp.text or "").strip() or "(no response)"
                store.add_message(agent_id, "assistant", agent_id, reply)
                return reply
            contents.append(resp.candidates[0].content)
            parts = []
            for call in calls:
                args = dict(call.args or {})
                set_status(agent_id, "working", f"Using {call.name}")
                try:
                    result = toolbox.execute(call.name, args, {"agent_id": agent_id, "depth": depth})
                    ok = "error" not in result
                except Exception as e:  # tool failures go back to the model so it can adapt
                    result, ok = {"error": f"{type(e).__name__}: {e}"}, False
                store.add_message(agent_id, "tool", agent_id, call.name,
                                  {"args": args, "result": _short(result, 1500), "ok": ok})
                full = json.dumps(result, default=str, ensure_ascii=False)
                response = result if len(full) <= 12000 else {"result_truncated": full[:12000]}
                parts.append(types.Part.from_function_response(name=call.name, response=response))
            contents.append(types.Content(role="user", parts=parts))
        reply = "I hit my step limit before finishing. Here's where I got to; ask me to continue."
        store.add_message(agent_id, "assistant", agent_id, reply)
        return reply
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        store.add_message(agent_id, "error", agent_id, msg)
        return f"Error: {msg}"
    finally:
        set_status(agent_id, "idle")


def run_in_background(agent_id, text):
    threading.Thread(target=run_agent, args=(agent_id, text), daemon=True).start()
