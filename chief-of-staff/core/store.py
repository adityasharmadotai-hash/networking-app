"""SQLite persistence: per-agent chat threads, the inter-agent activity feed,
and the approval queue for outward-facing actions (e.g. sending email)."""
import json
import os
import sqlite3
import threading
import time

DB_PATH = os.getenv("COS_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "chief_of_staff.db"))
_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row

_conn.executescript("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,          -- user | assistant | tool | error
    sender TEXT NOT NULL,        -- 'you', another agent id, or the agent itself
    content TEXT NOT NULL,
    meta TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_agent ON messages(agent_id, id);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected | failed
    result TEXT,
    created_at REAL NOT NULL
);
""")
_conn.commit()


def _rows(cur):
    out = []
    for r in cur.fetchall():
        d = dict(r)
        for k in ("meta", "payload"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except Exception:
                    pass
        out.append(d)
    return out


def add_message(agent_id, role, sender, content, meta=None):
    with _lock:
        cur = _conn.execute(
            "INSERT INTO messages(agent_id, role, sender, content, meta, created_at) VALUES (?,?,?,?,?,?)",
            (agent_id, role, sender, content, json.dumps(meta) if meta else None, time.time()),
        )
        _conn.commit()
        return cur.lastrowid


def get_messages(agent_id, after_id=0, limit=500):
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM messages WHERE agent_id=? AND id>? ORDER BY id LIMIT ?",
            (agent_id, after_id, limit),
        )
        return _rows(cur)


def chat_history(agent_id, limit=40):
    """Recent user/assistant turns (no tool chatter) used as model context."""
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM messages WHERE agent_id=? AND role IN ('user','assistant') ORDER BY id DESC LIMIT ?",
            (agent_id, limit),
        )
        return list(reversed(_rows(cur)))


def clear_thread(agent_id):
    with _lock:
        _conn.execute("DELETE FROM messages WHERE agent_id=?", (agent_id,))
        _conn.commit()


def add_activity(from_agent, to_agent, summary):
    with _lock:
        _conn.execute(
            "INSERT INTO activity(from_agent, to_agent, summary, created_at) VALUES (?,?,?,?)",
            (from_agent, to_agent, summary, time.time()),
        )
        _conn.commit()


def recent_activity(limit=30):
    with _lock:
        cur = _conn.execute("SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,))
        return _rows(cur)


def add_approval(agent_id, kind, payload):
    with _lock:
        cur = _conn.execute(
            "INSERT INTO approvals(agent_id, kind, payload, created_at) VALUES (?,?,?,?)",
            (agent_id, kind, json.dumps(payload), time.time()),
        )
        _conn.commit()
        return cur.lastrowid


def get_approval(approval_id):
    with _lock:
        cur = _conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,))
        rows = _rows(cur)
        return rows[0] if rows else None


def set_approval(approval_id, status, result=None):
    with _lock:
        _conn.execute("UPDATE approvals SET status=?, result=? WHERE id=?", (status, result, approval_id))
        _conn.commit()


def list_approvals(status="pending", limit=50):
    with _lock:
        cur = _conn.execute("SELECT * FROM approvals WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
        return _rows(cur)


def previews():
    """Latest visible message per agent, for the sidebar."""
    with _lock:
        cur = _conn.execute(
            "SELECT m.* FROM messages m JOIN (SELECT agent_id, MAX(id) mid FROM messages "
            "WHERE role IN ('user','assistant') GROUP BY agent_id) x ON m.id = x.mid")
        return {r["agent_id"]: {"id": r["id"], "content": r["content"][:160], "role": r["role"],
                                "sender": r["sender"], "created_at": r["created_at"]} for r in _rows(cur)}
