"""
Company Filter
--------------
Screens discovered companies against two rules the team asked for:

  1. Skip very large / highly distributed global organisations. These run big
     centralised recruiting orgs with hundreds of req owners, so a cold intro to
     one recruiter goes nowhere (Uber, Google DeepMind, Deloitte, OpenAI,
     Scale AI, Capgemini, Atlassian, Stripe, Anthropic, ...).

  2. Skip third-party staffing / recruiting / outsourcing firms even when they
     have open technical roles - we want direct employers hiring for their own
     internal positions.

Both lists are tunable without a code change:
    EXCLUDED_COMPANIES=Foo Inc,Bar Labs     # add extra blocks
    ALLOWED_COMPANIES=Stripe                # force-allow (wins over everything)
"""

import os
import re

# -- Reasons (constants so the UI can group/style them) -----------------------
REASON_ENTERPRISE = "Large / global enterprise"
REASON_STAFFING   = "Staffing / recruiting firm"
REASON_SERVICES   = "IT services / outsourcing firm"
REASON_MANUAL     = "Manually excluded"


def _norm(name: str) -> str:
    """Lowercase, punctuation -> spaces, collapse whitespace. Unlike
    dedup.normalize this keeps every word, because words like 'staffing',
    'consulting' and 'solutions' are exactly the signal we match on."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (name or "").lower())).strip()


def _contains_phrase(haystack_norm: str, phrase: str) -> bool:
    """Word-boundary phrase match, so 'co' never matches 'cognizant'."""
    return f" {phrase} " in f" {haystack_norm} "


# -- 1. Large / globally distributed organisations ---------------------------
# Named explicitly by the team, plus the obvious peers in the same bracket.
ENTERPRISE_COMPANIES = {
    # called out by the team
    "uber", "google", "google deepmind", "deepmind", "deloitte", "openai",
    "scale ai", "capgemini", "atlassian", "stripe", "anthropic",
    # big tech / mega-cap peers
    "alphabet", "amazon", "amazon web services", "aws", "apple", "microsoft",
    "meta", "facebook", "netflix", "nvidia", "tesla", "ibm", "intel", "oracle",
    "salesforce", "adobe", "cisco", "qualcomm", "broadcom", "dell",
    "hewlett packard", "vmware", "sap", "siemens", "samsung", "sony",
    "linkedin", "paypal", "shopify", "snowflake", "databricks", "palantir",
    "servicenow", "workday", "intuit", "twilio", "datadog", "cloudflare",
    "airbnb", "lyft", "doordash", "instacart", "pinterest", "snap", "reddit",
    "spotify", "coinbase", "robinhood", "bytedance", "tiktok", "twitter",
    "yahoo", "ebay", "booking", "expedia", "walmart", "target", "costco",
    "nike", "disney", "comcast", "verizon", "t mobile", "boeing",
    "lockheed martin", "raytheon", "northrop grumman", "general electric",
    "general motors", "ford motor", "johnson johnson", "pfizer", "merck",
    "unitedhealth", "cvs health",
    # big consultancies / professional services (huge + centralised)
    "accenture", "pwc", "pricewaterhousecoopers", "ernst young", "kpmg",
    "mckinsey company", "bain company", "boston consulting group",
    # large banks / insurers with centralised recruiting orgs
    "jpmorgan chase", "jp morgan", "goldman sachs", "morgan stanley",
    "bank of america", "wells fargo", "citigroup", "american express",
    "capital one", "mastercard", "blackrock",
    # frontier-AI labs in the same "huge inbound" bracket
    "mistral ai", "cohere", "inflection ai", "xai", "perplexity ai",
    "hugging face", "stability ai",
}

# Hints that a listing belongs to a giant global org even when the exact legal
# entity name is not on the list above.
ENTERPRISE_PATTERNS = (
    "global services", "worldwide", "multinational",
)


# -- 2. Third-party staffing / recruiting firms ------------------------------
# Unambiguous keywords - if any appears in the name it is an agency, not an employer.
STAFFING_KEYWORDS = (
    "staffing", "staff augmentation", "recruiting", "recruitment", "recruiters",
    "recruiter", "headhunters", "headhunting", "executive search",
    "search partners", "search group", "talent solutions", "talent partners",
    "talent group", "talent acquisition", "talent network", "manpower",
    "workforce solutions", "workforce management", "placement services",
    "placements", "employment agency", "temp agency", "temporary staffing",
    "contract staffing", "resourcing", "hr solutions", "hr services",
    "job consultancy", "personnel services", "employment services",
)

# Well-known agencies whose names carry no obvious keyword.
STAFFING_FIRMS = {
    "robert half", "randstad", "adecco", "kelly services", "manpowergroup",
    "kforce", "teksystems", "insight global", "aerotek", "apex systems",
    "allegis group", "motion recruitment", "jobot", "cybercoders",
    "hays", "michael page", "page group", "korn ferry", "heidrick struggles",
    "spencer stuart", "egon zehnder", "russell reynolds associates",
    "collabera", "diverse lynx", "mindlance", "compunnel", "sunrise systems",
    "artech", "kyyba", "nlb services", "intelliswift", "eteam",
    "us tech solutions", "net2source", "akraya", "zolon tech", "amtex systems",
    "harnham", "averity", "storm2", "burtch works", "signify technology",
    "oxford global resources", "beacon hill", "addison group", "vaco",
    "creative circle", "on assignment", "asgn", "experis", "volt workforce",
    "roth staffing", "hire velocity", "greythorn", "mastech digital",
    "the judge group", "judge group", "yoh", "v soft consulting",
}

# Large IT-services / outsourcing shops - technically employers, but the role is
# billed out to a client, so it is not a direct internal hire.
SERVICES_FIRMS = {
    "infosys", "tata consultancy services", "tcs", "wipro", "cognizant",
    "hcl technologies", "hcltech", "tech mahindra", "ltimindtree", "mindtree",
    "mphasis", "genpact", "virtusa", "persistent systems", "zensar",
    "ust global", "syntel", "ntt data", "dxc technology", "atos", "unisys",
    "birlasoft", "coforge", "hexaware", "cybage", "happiest minds",
    "quest global", "sonata software", "cigniti", "globallogic",
    "epam systems", "luxoft", "endava", "softserve", "thoughtworks",
    "slalom", "perficient", "concentrix", "teleperformance",
    "infinite computer solutions",
}

# Softer keywords - a company whose name is built around these is almost always
# a services/consulting shop rather than a product company hiring internally.
SERVICES_KEYWORDS = (
    "outsourcing", "it services", "it consulting", "software consulting",
    "consultancy", "consultants", "managed services", "systems integrator",
)


def _env_set(var: str) -> set[str]:
    return {_norm(v) for v in os.getenv(var, "").split(",") if v.strip()}


def exclusion_reason(company_name: str) -> str | None:
    """Why this company should be skipped, or None if it passes.

    Checked in priority order: the allow-list wins over everything, then manual
    blocks, then the enterprise, staffing, and services rules."""
    name = _norm(company_name)
    if not name:
        return None

    # Force-allow escape hatch - always wins.
    for allowed in _env_set("ALLOWED_COMPANIES"):
        if allowed and _contains_phrase(name, allowed):
            return None

    for extra in _env_set("EXCLUDED_COMPANIES"):
        if extra and _contains_phrase(name, extra):
            return REASON_MANUAL

    for entry in ENTERPRISE_COMPANIES:
        if _contains_phrase(name, entry):
            return REASON_ENTERPRISE
    for pat in ENTERPRISE_PATTERNS:
        if _contains_phrase(name, pat):
            return REASON_ENTERPRISE

    for kw in STAFFING_KEYWORDS:
        if _contains_phrase(name, kw):
            return REASON_STAFFING
    for firm in STAFFING_FIRMS:
        if _contains_phrase(name, firm):
            return REASON_STAFFING

    for firm in SERVICES_FIRMS:
        if _contains_phrase(name, firm):
            return REASON_SERVICES
    for kw in SERVICES_KEYWORDS:
        if _contains_phrase(name, kw):
            return REASON_SERVICES

    return None


def is_excluded(company_name: str) -> bool:
    return exclusion_reason(company_name) is not None


def filter_companies(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split jobs into (kept, removed). Removed rows carry a `removed_reason`."""
    kept, removed = [], []
    for job in jobs:
        reason = exclusion_reason(job.get("company_name", ""))
        if reason:
            removed.append({**job, "removed_reason": reason})
        else:
            kept.append(job)
    return kept, removed
