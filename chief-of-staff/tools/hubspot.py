"""HubSpot CRM via a Private App access token (HUBSPOT_ACCESS_TOKEN).

Required private-app scopes: crm.objects.contacts.read/write,
crm.objects.companies.read/write (notes are covered by contacts write).
"""
import time

import requests

from core import config

BASE = "https://api.hubapi.com"


def _req(method, path, **kw):
    if not config.HUBSPOT_ACCESS_TOKEN:
        raise RuntimeError("HUBSPOT_ACCESS_TOKEN is not set in chief-of-staff/.env")
    r = requests.request(method, BASE + path, timeout=25,
                         headers={"Authorization": f"Bearer {config.HUBSPOT_ACCESS_TOKEN}",
                                  "Content-Type": "application/json"}, **kw)
    if not r.ok:
        raise RuntimeError(f"HubSpot {method} {path} -> HTTP {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def _search(obj, prop, value, props):
    res = _req("POST", f"/crm/v3/objects/{obj}/search", json={
        "filterGroups": [{"filters": [{"propertyName": prop, "operator": "EQ", "value": value}]}],
        "properties": props, "limit": 1})
    results = res.get("results") or []
    return results[0] if results else None


def _clean(d):
    return {k: v for k, v in d.items() if v not in (None, "")}


def _add_note(contact_id, body):
    _req("POST", "/crm/v3/objects/notes", json={
        "properties": {"hs_note_body": body, "hs_timestamp": int(time.time() * 1000)},
        "associations": [{"to": {"id": contact_id},
                          "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}]})


def upsert_company(name: str, domain: str = "", industry: str = "", city: str = "",
                   country: str = "", description: str = "", website: str = "") -> dict:
    props = _clean({"name": name, "domain": domain, "industry": industry, "city": city,
                    "country": country, "description": description, "website": website})
    existing = _search("companies", "domain", domain, ["name", "domain"]) if domain else None
    if not existing:
        existing = _search("companies", "name", name, ["name", "domain"])
    # 'industry' is an enumerated property in HubSpot; keep it out of writes to avoid rejections
    # and put it in the description instead.
    if "industry" in props:
        ind = props.pop("industry")
        props["description"] = (props.get("description", "") + f" | Industry: {ind}").strip(" |")
    if existing:
        _req("PATCH", f"/crm/v3/objects/companies/{existing['id']}", json={"properties": props})
        return {"action": "updated", "company_id": existing["id"], "name": name}
    res = _req("POST", "/crm/v3/objects/companies", json={"properties": props})
    return {"action": "created", "company_id": res["id"], "name": name}


def upsert_contact(email: str, firstname: str = "", lastname: str = "", jobtitle: str = "",
                   company: str = "", phone: str = "", website: str = "", city: str = "",
                   linkedin_url: str = "", note: str = "", company_domain: str = "") -> dict:
    if not email:
        return {"error": "email is required to create/update a HubSpot contact"}
    props = _clean({"email": email.lower(), "firstname": firstname, "lastname": lastname,
                    "jobtitle": jobtitle, "company": company, "phone": phone,
                    "website": website, "city": city})
    existing = _search("contacts", "email", email.lower(), ["email"])
    if existing:
        cid = existing["id"]
        _req("PATCH", f"/crm/v3/objects/contacts/{cid}", json={"properties": props})
        action = "updated"
    else:
        cid = _req("POST", "/crm/v3/objects/contacts", json={"properties": props})["id"]
        action = "created"
    out = {"action": action, "contact_id": cid, "email": email}

    note_parts = [p for p in [note, f"LinkedIn: {linkedin_url}" if linkedin_url else ""] if p]
    if note_parts:
        _add_note(cid, "<br>".join(note_parts) + "<br><i>Added by Alex (research agent)</i>")
        out["note_added"] = True

    if company:
        try:
            comp = upsert_company(company, domain=company_domain)
            _req("PUT", f"/crm/v4/objects/contacts/{cid}/associations/default/companies/{comp['company_id']}")
            out["associated_company_id"] = comp["company_id"]
        except Exception as e:
            out["company_association_error"] = str(e)
    return out


def search_contacts(query: str, limit: int = 10) -> dict:
    res = _req("POST", "/crm/v3/objects/contacts/search", json={
        "query": query, "limit": min(int(limit or 10), 50),
        "properties": ["email", "firstname", "lastname", "jobtitle", "company", "phone"]})
    return {"total": res.get("total"), "contacts": [{"id": r["id"], **r.get("properties", {})}
                                                     for r in res.get("results", [])]}
