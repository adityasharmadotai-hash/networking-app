"""
Company & Role Filter
---------------------
Screens discovered jobs before a human ever sees them. Every rule here exists
because a lead of that shape wasted review time:

  1. Very large / highly distributed global organisations - big centralised
     recruiting orgs, so a cold intro to one recruiter goes nowhere.
  2. Third-party staffing / recruiting firms - we want direct employers.
  3. IT services / outsourcing shops - the role is billed to a client.
  4. Companies with a mature in-house talent org - sophisticated hiring
     infrastructure and formal vendor processes mean an external recruiter has
     no route to the hiring manager.
  5. Stealth / confidential companies - no name, nothing to research.
  6. Very early-stage or unfunded work (co-founder searches, equity-only,
     founding-engineer-#1 roles) - no budget for an agency placement.
  7. Anything that is not a full-time role - internships, contract, part-time.

Every list is tunable without a code change:
    EXCLUDED_COMPANIES=Foo Inc,Bar Labs     # add extra blocks
    ALLOWED_COMPANIES=Stripe,Figma          # force-allow (wins over everything)
"""

import os
import re

# -- Reasons (constants so the UI can group/style them) -----------------------
REASON_ENTERPRISE   = "Large / global enterprise"
REASON_STAFFING     = "Staffing / recruiting firm"
REASON_SERVICES     = "IT services / outsourcing firm"
REASON_TALENT_ORG   = "Mature in-house talent org"
REASON_STEALTH      = "Stealth / confidential company"
REASON_EARLY_STAGE  = "Very early-stage / unfunded"
REASON_NOT_FULLTIME = "Not a full-time role"
REASON_MANUAL       = "Manually excluded"


def _norm(name: str) -> str:
    """Lowercase, punctuation -> spaces, collapse whitespace. Unlike
    dedup.normalize this keeps every word, because words like 'staffing',
    'consulting' and 'solutions' are exactly the signal we match on."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (name or "").lower())).strip()


def _contains_phrase(haystack_norm: str, phrase: str) -> bool:
    """Word-boundary phrase match, so 'co' never matches 'cognizant'."""
    return f" {phrase} " in f" {haystack_norm} "


# Some blocked names are ordinary English words ("linear", "ramp", "jack",
# "sigma"). Matching those anywhere in a name would drop unrelated employers
# like "Sigma Defense" or "Jack Henry", so they only ever match when they are
# the ENTIRE company name.
EXACT_ONLY_NAMES = {
    "jack", "alex", "atoms", "sigma", "linear", "ramp", "sierra", "cursor",
    "harvey", "carta", "elastic", "wiz", "gong", "toast", "faire", "glean",
}


def _name_matches(name_norm: str, entry: str) -> bool:
    """True if `entry` blocks `name_norm`. Generic one-word entries must match
    the whole name; everything else matches on a word boundary."""
    if entry in EXACT_ONLY_NAMES:
        return name_norm == entry
    return _contains_phrase(name_norm, entry)


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
    "unitedhealth", "optum", "cvs health",
    # large government / defence systems integrators, same centralised-TA shape
    "booz allen hamilton", "leidos", "saic", "caci", "general dynamics",
    "l3harris", "peraton", "mitre", "guidehouse", "parsons corporation",
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
    # called out by the team ("jack" / "alex" are exact-name matches only, so
    # "Jack Henry & Associates" is not caught by the recruiting platform "Jack")
    "alku", "life at alku", "alex", "alex ai", "hire alex", "jack",
    "search with jack", "metantz", "harrison clarke", "radley james", "xcede",
    # slipped through a live run - none of these carry an obvious keyword
    "skyrocket ventures", "crossing hurdles", "lumicity",
    # boutique tech/AI agencies in the same bracket
    "understanding recruitment", "trust in soda", "mission recruit",
    "third republic", "eteam workforce", "phaidon international",
    "selby jennings", "glocomms", "larson maddox", "dsj global",
    "ea first", "adroit people", "talentburst", "russell tobin",
    "pride global", "aditi consulting", "system soft technologies",
    "kellton tech", "photon interactive", "sapphire software solutions",
    "clovity", "smart it frame", "acceler8 talent", "premier group",
    "kanda tech", "spectrum staffing", "jefferson frank", "tenth revolution",
    "nigel frank international", "mason frank", "washington frank",
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


# LinkedIn tags every company with an industry, and that is a far better
# staffing signal than the name is: "Skyrocket Ventures", "Crossing Hurdles" and
# "Lumicity" all read like product companies but are classified as
# "Staffing and Recruiting". agent/job_discovery.py reads this off the posting.
STAFFING_INDUSTRIES = (
    "staffing", "recruiting", "recruitment", "executive search",
)


def industry_exclusion_reason(industries: str) -> str | None:
    """Screen on the company's LinkedIn industry, when we managed to read it."""
    val = _norm(industries)
    if not val:
        return None
    for kw in STAFFING_INDUSTRIES:
        if _contains_phrase(val, kw):
            return REASON_STAFFING
    return None


# -- 4. Mature in-house talent orgs ------------------------------------------
# Not mega-caps, but far enough along that they run a full internal recruiting
# function, an established candidate pipeline and a formal agency-vendor
# process. An external recruiter reaching a hiring manager cold is unlikely.
# Named by the team first, then peers at the same funding/headcount stage.
TALENT_ORG_COMPANIES = {
    # called out by the team
    "atoms", "spacex", "rivian", "volkswagen", "vw", "midi health", "figma",
    "rippling", "affirm", "sigma", "sigma computing",
    # late-stage product companies with well-known in-house recruiting orgs
    "notion", "notion labs", "canva", "discord", "plaid", "brex", "ramp",
    "gusto", "deel", "vanta", "retool", "linear", "vercel", "airtable",
    "asana", "miro", "zapier", "grammarly", "duolingo", "carta", "chime",
    "benchling", "samsara", "verkada", "gitlab", "hashicorp", "mongodb",
    "elastic", "confluent", "amplitude", "braze", "klaviyo", "toast",
    "flexport", "faire", "navan", "gong", "gong io", "drata", "wiz", "snyk",
    "1password", "okta", "crowdstrike", "sentinelone", "zscaler",
    "digitalocean", "sierra", "sierra ai", "glean", "harvey", "harvey ai",
    "anysphere", "cursor", "replit", "sigma computing",
    # capital-intensive hardware / autonomy programmes with huge internal TA
    "anduril", "anduril industries", "waymo", "cruise", "zoox", "nuro",
    "applied intuition", "relativity space", "rocket lab", "joby aviation",
    "lucid motors",
}


# -- 5. Stealth / confidential companies -------------------------------------
# LinkedIn's placeholder for an unnamed employer is literally "Stealth Startup".
# There is nothing to research and no one to contact, so drop them outright.
# The regex is anchored so a real company like "Stealth Monitoring" survives.
_STEALTH_RE = re.compile(
    r"^stealth(\s+(startup|startups|start\s?up|mode|co|company|companies|"
    r"venture|ventures|ai|ml|tech|inc|llc|ltd))*$"
)

STEALTH_PHRASES = (
    "stealth startup", "stealth mode", "stealth company", "stealth co",
    "confidential company", "company confidential", "undisclosed company",
    "undisclosed employer", "name withheld",
)

# Generic placeholders - only ever blocked when they are the WHOLE name.
STEALTH_EXACT = {
    "stealth", "confidential", "undisclosed", "unnamed", "anonymous",
    "private company", "n a", "na", "tbd", "unknown", "new startup",
}


# -- 6. Very early-stage / unfunded ------------------------------------------
# We want funded, growing startups. These signals mean the opposite: no raise
# yet, no headcount budget, and usually no money for an agency placement.
EARLY_STAGE_NAME_KEYWORDS = (
    "pre seed", "preseed", "seed stage", "early stage", "newco", "new co",
    "incubator", "venture studio", "startup studio", "accelerator",
)

# Role-title signals for the same thing.
EARLY_STAGE_TITLE_KEYWORDS = (
    "co founder", "cofounder", "founder", "founding engineer",
    "founding member", "founding team", "first engineer",
    "equity only", "equity based", "unpaid", "no salary", "profit share",
    "profit sharing", "sweat equity",
)


# -- 7. Full-time only --------------------------------------------------------
# Tokens that appear in a source-provided employment type.
_NOT_FULLTIME_TOKENS = (
    "part time", "parttime", "contractor", "contract", "temporary", "temp",
    "internship", "intern", "seasonal", "per diem", "volunteer", "freelance",
    "apprenticeship", "casual",
)
_FULLTIME_TOKENS = ("full time", "fulltime", "permanent", "regular")

# Fallback when the source gives us no employment type: read the job title.
NON_FULLTIME_TITLE_KEYWORDS = (
    "intern", "interns", "internship", "co op", "coop", "part time",
    "contract", "contractor", "contract to hire", "c2c", "corp to corp",
    "1099", "w2 contract", "freelance", "freelancer", "temporary",
    "seasonal", "apprentice", "apprenticeship", "volunteer", "fellowship",
    "trainee", "summer analyst", "working student", "student worker",
)

# "Smart Contract Engineer" is a full-time crypto role, not a contract role.
_TITLE_CONTRACT_EXCEPTIONS = ("smart contract", "smart contracts")


# -- Funding / growth signal (display only) -----------------------------------
# Update 4 also asks us to *prefer* funded, growing startups. We cannot verify
# funding from a job board, but a posting that mentions its own raise is a
# useful hint, so we surface it as a badge rather than filtering on it.
_FUNDING_PATTERNS = (
    (re.compile(r"\bseries\s+([a-h])\b", re.I), lambda m: f"Series {m.group(1).upper()}"),
    (re.compile(r"\braised\s+\$\s?([\d.]+)\s*(million|billion|mm|m|bn|b)\b", re.I),
     lambda m: f"Raised ${m.group(1)}{m.group(2)[0].upper()}"),
    (re.compile(r"\b(seed[- ]funded|seed round|series seed)\b", re.I), lambda m: "Seed-funded"),
    (re.compile(r"\b(y combinator|yc\s?[swf]\d{2})\b", re.I), lambda m: "Y Combinator"),
    (re.compile(r"\bbacked by\b", re.I), lambda m: "VC-backed"),
    (re.compile(r"\b(unicorn|decacorn)\b", re.I), lambda m: "Unicorn"),
    (re.compile(r"\b(publicly traded|nasdaq|nyse)\b", re.I), lambda m: "Public"),
)


def funding_signal(text: str) -> str:
    """Short funding/stage label found in a posting, or "" if there is none.

    Display-only: it never excludes anything, because a posting that omits the
    company's raise says nothing about whether the raise happened.
    """
    if not text:
        return ""
    for pattern, label in _FUNDING_PATTERNS:
        m = pattern.search(text)
        if m:
            return label(m)
    return ""


# -- Employment type ----------------------------------------------------------

def employment_verdict(raw: str) -> str:
    """Classify a source-provided employment type: full_time | other | unknown."""
    val = _norm(raw)
    if not val:
        return "unknown"
    for token in _NOT_FULLTIME_TOKENS:
        if _contains_phrase(val, token):
            return "other"
    for token in _FULLTIME_TOKENS:
        if _contains_phrase(val, token):
            return "full_time"
    return "unknown"


def _title_is_not_fulltime(title: str) -> bool:
    name = _norm(title)
    if not name:
        return False
    for exc in _TITLE_CONTRACT_EXCEPTIONS:
        if _contains_phrase(name, exc):
            # Drop the exception so "Smart Contract Engineer" cannot trip the
            # bare "contract" keyword below.
            name = re.sub(r"\s+", " ", name.replace(exc, " ")).strip()
    return any(_contains_phrase(name, kw) for kw in NON_FULLTIME_TITLE_KEYWORDS)


def _env_set(var: str) -> set[str]:
    return {_norm(v) for v in os.getenv(var, "").split(",") if v.strip()}


def _is_allowed(name_norm: str) -> bool:
    """ALLOWED_COMPANIES is an escape hatch that wins over every rule."""
    return any(a and _contains_phrase(name_norm, a) for a in _env_set("ALLOWED_COMPANIES"))


def exclusion_reason(company_name: str) -> str | None:
    """Why this company should be skipped, or None if it passes.

    Checked in priority order: the allow-list wins over everything, then manual
    blocks, then stealth, enterprise, talent-org, staffing, services and
    early-stage rules."""
    name = _norm(company_name)
    if not name:
        return None

    if _is_allowed(name):
        return None

    for extra in _env_set("EXCLUDED_COMPANIES"):
        if extra and _contains_phrase(name, extra):
            return REASON_MANUAL

    # Stealth first: a stealth listing tells us nothing else, so no later rule
    # could produce a more useful reason.
    if name in STEALTH_EXACT or _STEALTH_RE.match(name):
        return REASON_STEALTH
    for phrase in STEALTH_PHRASES:
        if _contains_phrase(name, phrase):
            return REASON_STEALTH

    for entry in ENTERPRISE_COMPANIES:
        if _name_matches(name, entry):
            return REASON_ENTERPRISE
    for pat in ENTERPRISE_PATTERNS:
        if _contains_phrase(name, pat):
            return REASON_ENTERPRISE

    for entry in TALENT_ORG_COMPANIES:
        if _name_matches(name, entry):
            return REASON_TALENT_ORG

    for kw in STAFFING_KEYWORDS:
        if _contains_phrase(name, kw):
            return REASON_STAFFING
    for firm in STAFFING_FIRMS:
        if _name_matches(name, firm):
            return REASON_STAFFING

    for firm in SERVICES_FIRMS:
        if _name_matches(name, firm):
            return REASON_SERVICES
    for kw in SERVICES_KEYWORDS:
        if _contains_phrase(name, kw):
            return REASON_SERVICES

    for kw in EARLY_STAGE_NAME_KEYWORDS:
        if _contains_phrase(name, kw):
            return REASON_EARLY_STAGE

    return None


def role_exclusion_reason(job: dict) -> str | None:
    """Why this *posting* should be skipped, independent of the company.

    Covers the full-time-only rule and the early-stage signals that live in the
    role rather than the company name (co-founder searches, equity-only work).
    """
    if _is_allowed(_norm(job.get("company_name", ""))):
        return None

    title = job.get("job_title_hiring_for", "")

    verdict = employment_verdict(job.get("employment_type", ""))
    if verdict == "other":
        return REASON_NOT_FULLTIME
    # Only fall back to the title when the source told us nothing. A source that
    # says "Full-time" outranks a title that happens to contain "contract".
    if verdict == "unknown" and _title_is_not_fulltime(title):
        return REASON_NOT_FULLTIME

    name = _norm(title)
    for kw in EARLY_STAGE_TITLE_KEYWORDS:
        if _contains_phrase(name, kw):
            return REASON_EARLY_STAGE

    return None


def job_exclusion_reason(job: dict) -> str | None:
    """Every rule, in order: company name, LinkedIn industry, then the role."""
    reason = exclusion_reason(job.get("company_name", ""))
    if reason:
        return reason

    # The allow-list has to win here too, or a force-allowed company could still
    # be dropped on its industry.
    if not _is_allowed(_norm(job.get("company_name", ""))):
        reason = industry_exclusion_reason(job.get("company_industries", ""))
        if reason:
            return reason

    return role_exclusion_reason(job)


def is_excluded(company_name: str) -> bool:
    return exclusion_reason(company_name) is not None


def filter_companies(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split jobs into (kept, removed). Removed rows carry a `removed_reason`."""
    kept, removed = [], []
    for job in jobs:
        reason = job_exclusion_reason(job)
        if reason:
            removed.append({**job, "removed_reason": reason})
        else:
            kept.append(job)
    return kept, removed
