"""Tool declarations (what Gemini sees) and their implementations."""
from . import config, store
from .agents import AGENTS, team_roster


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


S = {"type": "string"}

TOOLS = {
    "list_team": {
        "description": "List the specialist agents on the team and what each can do.",
        "parameters": _obj({}),
    },
    "delegate_to_agent": {
        "description": "Hand a task to a specialist agent and wait for its full result. The agent cannot see "
                       "your conversation, so make the instruction complete and self-contained.",
        "parameters": _obj({"agent_id": {**S, "description": "Agent id, e.g. 'alex'"},
                            "instruction": {**S, "description": "Complete task instructions and the expected output"}},
                           ["agent_id", "instruction"]),
    },
    "web_research": {
        "description": "Search the web (Google Search grounding) and get a synthesized answer with sources.",
        "parameters": _obj({"query": S, "focus": {**S, "description": "Optional: what details to focus on"}}, ["query"]),
    },
    "fetch_url": {
        "description": "Fetch a web page and return its text plus any email addresses on the page.",
        "parameters": _obj({"url": S}, ["url"]),
    },
    "find_email": {
        "description": "Find a person's work email from their name and company domain (or company name).",
        "parameters": _obj({"full_name": S, "domain": {**S, "description": "Company domain, e.g. acme.com"},
                            "company": {**S, "description": "Company name if domain unknown"}}, ["full_name"]),
    },
    "verify_email": {
        "description": "Check whether an email address is deliverable.",
        "parameters": _obj({"email": S}, ["email"]),
    },
    "company_email_directory": {
        "description": "List known people and emails at a company domain (needs Hunter.io key).",
        "parameters": _obj({"domain": S, "department": {**S, "description": "Optional, e.g. executive, hr, engineering, sales"},
                            "limit": {"type": "integer"}}, ["domain"]),
    },
    "hubspot_upsert_contact": {
        "description": "Create or update a HubSpot contact (matched by email), optionally attach a note and link the company.",
        "parameters": _obj({"email": S, "firstname": S, "lastname": S, "jobtitle": S, "company": S,
                            "company_domain": S, "phone": S, "website": S, "city": S, "linkedin_url": S,
                            "note": {**S, "description": "Context/research summary saved as a note"}}, ["email"]),
    },
    "hubspot_upsert_company": {
        "description": "Create or update a HubSpot company (matched by domain, then name).",
        "parameters": _obj({"name": S, "domain": S, "industry": S, "city": S, "country": S,
                            "description": S, "website": S}, ["name"]),
    },
    "hubspot_search_contacts": {
        "description": "Search existing HubSpot contacts by free-text query (name, email, company).",
        "parameters": _obj({"query": S, "limit": {"type": "integer"}}, ["query"]),
    },
    "send_email": {
        "description": "Send an email from your assigned Gmail account. Queued for the user's approval unless auto-send is enabled.",
        "parameters": _obj({"to": S, "subject": S, "body": {**S, "description": "Plain-text body including sign-off"},
                            "cc": S, "reason": {**S, "description": "One line on why this email is being sent"}},
                           ["to", "subject", "body"]),
    },
    "create_gmail_draft": {
        "description": "Save an email as a draft in your assigned Gmail account without sending.",
        "parameters": _obj({"to": S, "subject": S, "body": S, "cc": S}, ["to", "subject", "body"]),
    },
}


def declarations(tool_names):
    from google.genai import types
    return [types.FunctionDeclaration(name=n, description=TOOLS[n]["description"],
                                      parameters_json_schema=TOOLS[n]["parameters"]) for n in tool_names]


def execute(name, args, ctx):
    """Run a tool. ctx = {'agent_id':..., 'depth':...}."""
    from tools import email_finder, gmail, hubspot, research

    if name not in AGENTS[ctx["agent_id"]]["tools"]:
        return {"error": f"Tool {name} is not available to this agent."}
    if name == "list_team":
        return {"team": team_roster()}
    if name == "delegate_to_agent":
        target = (args.get("agent_id") or "").lower()
        if target not in AGENTS or target == ctx["agent_id"]:
            return {"error": f"Unknown agent '{target}'. Team: {', '.join(a for a in AGENTS if a != ctx['agent_id'])}"}
        if ctx["depth"] >= 2:
            return {"error": "Delegation depth limit reached."}
        from .runner import run_agent
        me = AGENTS[ctx["agent_id"]]["name"]
        store.add_activity(ctx["agent_id"], target, args["instruction"][:300])
        reply = run_agent(target, args["instruction"], sender=ctx["agent_id"], depth=ctx["depth"] + 1)
        store.add_activity(target, ctx["agent_id"], "Reported back: " + reply[:280])
        return {"agent": AGENTS[target]["name"], "delegated_by": me, "result": reply}
    if name == "web_research":
        return research.web_research(args["query"], args.get("focus", ""))
    if name == "fetch_url":
        return research.fetch_url(args["url"])
    if name == "find_email":
        return email_finder.find_email(args["full_name"], args.get("domain", ""), args.get("company", ""))
    if name == "verify_email":
        return email_finder.verify_email(args["email"])
    if name == "company_email_directory":
        return email_finder.company_email_directory(args["domain"], args.get("department", ""), args.get("limit", 10))
    if name == "hubspot_upsert_contact":
        return hubspot.upsert_contact(**{k: v for k, v in args.items() if k in TOOLS[name]["parameters"]["properties"]})
    if name == "hubspot_upsert_company":
        return hubspot.upsert_company(**{k: v for k, v in args.items() if k in TOOLS[name]["parameters"]["properties"]})
    if name == "hubspot_search_contacts":
        return hubspot.search_contacts(args["query"], args.get("limit", 10))
    if name == "send_email":
        mailbox = AGENTS[ctx["agent_id"]].get("gmail_account", "")
        if not mailbox:
            return {"error": "No Gmail account is assigned to this agent."}
        payload = {k: args.get(k, "") for k in ("to", "subject", "body", "cc", "reason")}
        payload["from_account"] = mailbox
        if config.AUTO_SEND_EMAIL:
            return gmail.send_now(mailbox, payload["to"], payload["subject"], payload["body"], payload["cc"])
        aid = store.add_approval(ctx["agent_id"], "send_email", payload)
        return {"queued_for_approval": True, "approval_id": aid,
                "note": "The email is waiting for the user's approval in the dashboard's Approvals panel."}
    if name == "create_gmail_draft":
        return gmail.create_draft(AGENTS[ctx["agent_id"]].get("gmail_account", ""), args["to"], args["subject"],
                                  args["body"], args.get("cc", ""))
    return {"error": f"Unknown tool {name}"}
