import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import pandas as pd

st.set_page_config(
    page_title="Never Lose a Contact",
    page_icon="🤝",
    layout="centered"
)

# ── Global styles ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ---- fonts & base ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ---- hide default header decoration ---- */
#MainMenu, footer { visibility: hidden; }

/* ---- hero section ---- */
.hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 20px;
    padding: 2.5rem 2rem 2rem 2rem;
    text-align: center;
    margin-bottom: 1.8rem;
    box-shadow: 0 8px 32px rgba(102,126,234,0.25);
}
.hero h1 {
    color: #ffffff;
    font-size: 2rem;
    font-weight: 800;
    margin: 0 0 0.4rem 0;
    line-height: 1.2;
}
.hero p {
    color: rgba(255,255,255,0.85);
    font-size: 1rem;
    margin: 0;
}
.hero .badge-row {
    display: flex;
    justify-content: center;
    gap: 0.6rem;
    margin-top: 1.1rem;
    flex-wrap: wrap;
}
.badge {
    background: rgba(255,255,255,0.18);
    color: #fff;
    border-radius: 20px;
    padding: 0.3rem 0.85rem;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}

/* ---- stat cards ---- */
.stat-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.stat-card {
    flex: 1;
    background: #f8f7ff;
    border: 1px solid #ede9fe;
    border-radius: 14px;
    padding: 1rem 0.8rem;
    text-align: center;
}
.stat-card .icon { font-size: 1.6rem; }
.stat-card .label {
    font-size: 0.72rem;
    color: #6b7280;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.25rem;
}

/* ---- tab styling ---- */
div[data-testid="stTabs"] button {
    font-weight: 600;
    font-size: 0.9rem;
}

/* ---- form card ---- */
.form-card {
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 1.5rem 1.5rem 0.5rem 1.5rem;
    margin-bottom: 1rem;
}

/* ---- section label ---- */
.section-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #667eea;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.2rem;
}

/* ---- AI answer box ---- */
.ai-answer {
    background: linear-gradient(135deg, #f0f4ff 0%, #faf5ff 100%);
    border-left: 4px solid #667eea;
    border-radius: 0 12px 12px 0;
    padding: 1.2rem 1.4rem;
    margin-top: 1rem;
    font-size: 0.95rem;
    line-height: 1.6;
}

/* ---- example chips ---- */
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0.6rem 0 1.2rem 0;
}
.chip {
    background: #ede9fe;
    color: #5b21b6;
    border-radius: 20px;
    padding: 0.3rem 0.8rem;
    font-size: 0.78rem;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
    <div style="font-size:2.4rem; margin-bottom:0.5rem;">🤝</div>
    <h1>Save Contacts,<br>Never Lose a Connection</h1>
    <p>Capture people you meet at events — instantly searchable with AI</p>
    <div class="badge-row">
        <span class="badge">📇 Smart Contact Book</span>
        <span class="badge">☁️ Saved to Google Sheets</span>
        <span class="badge">🤖 AI-Powered Search</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Google Sheets connection ──────────────────────────────────────────────────

@st.cache_resource
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scope
    )
    client = gspread.authorize(creds)
    return client.open(st.secrets["SHEET_NAME"]).sheet1


def ensure_headers(sheet):
    first_row = sheet.row_values(1)
    if not first_row:
        sheet.append_row(["Name", "Email", "Phone", "LinkedIn", "Notes"])


def load_contacts() -> pd.DataFrame:
    sheet = get_sheet()
    records = sheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Name", "Email", "Phone", "LinkedIn", "Notes"])
    return pd.DataFrame(records)


def save_contact(name, email, phone, linkedin, notes):
    sheet = get_sheet()
    ensure_headers(sheet)
    sheet.append_row([name, email, phone, linkedin, notes])


# ── AI query ──────────────────────────────────────────────────────────────────

def ask_ai(question: str, df: pd.DataFrame) -> str:
    if df.empty:
        return "You don't have any contacts saved yet. Add some first!"

    contacts_text = df.to_json(orient="records", indent=2)

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that searches through the user's networking contacts. "
                    "When the user asks a question, look through the contact data and return the relevant people "
                    "with their details formatted clearly. Be concise and friendly."
                ),
            },
            {
                "role": "user",
                "content": f"Here are my contacts:\n\n{contacts_text}\n\nMy question: {question}",
            },
        ],
    )
    return response.choices[0].message.content


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_add, tab_view, tab_ai = st.tabs(["➕  Add Contact", "📋  All Contacts", "🤖  Ask AI"])

# ── Tab 1: Add Contact ────────────────────────────────────────────────────────

with tab_add:
    st.markdown("#### Who did you just meet?")
    st.caption("Fill in what you remember — everything except the name is optional.")

    with st.form("add_contact_form", clear_on_submit=True):
        st.markdown('<div class="section-label">👤 Identity</div>', unsafe_allow_html=True)
        name  = st.text_input("Full Name *", placeholder="e.g. Sarah Chen")
        email = st.text_input("Email Address", placeholder="sarah@example.com")

        st.markdown('<div class="section-label" style="margin-top:0.8rem">📞 Contact</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            phone = st.text_input("Phone Number", placeholder="+1 555 000 0000")
        with col2:
            linkedin = st.text_input("LinkedIn URL", placeholder="linkedin.com/in/sarah")

        st.markdown('<div class="section-label" style="margin-top:0.8rem">📝 Notes</div>', unsafe_allow_html=True)
        notes = st.text_area(
            "Notes",
            height=130,
            placeholder="Where did you meet? What do they do? What did you talk about?\ne.g. Met at AI Summit 2025 in SF. Works at Google DeepMind. Wants to chat about LLM evals.",
            label_visibility="collapsed",
        )

        submitted = st.form_submit_button("💾  Save Contact", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("Name is required — everything else is optional.")
        else:
            try:
                save_contact(name.strip(), email.strip(), phone.strip(),
                             linkedin.strip(), notes.strip())
                st.success(f"✅ **{name}** has been saved to your contacts!")
                get_sheet.clear()
            except Exception as e:
                st.error(f"Could not save: {e}")

# ── Tab 2: View All Contacts ──────────────────────────────────────────────────

with tab_view:
    col_h, col_btn = st.columns([4, 1])
    with col_h:
        st.markdown("#### Your Contact Book")
    with col_btn:
        if st.button("🔄 Refresh", use_container_width=True):
            get_sheet.clear()

    try:
        df = load_contacts()
        if df.empty:
            st.markdown("""
            <div style="text-align:center; padding:3rem 1rem; color:#9ca3af;">
                <div style="font-size:3rem">📭</div>
                <div style="font-size:1.1rem; font-weight:600; margin-top:0.5rem">No contacts yet</div>
                <div style="font-size:0.9rem; margin-top:0.3rem">Head to the ➕ tab and add your first one!</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="stat-row">
                <div class="stat-card">
                    <div class="icon">👥</div>
                    <div style="font-size:1.6rem; font-weight:800; color:#667eea">{len(df)}</div>
                    <div class="label">Total Contacts</div>
                </div>
                <div class="stat-card">
                    <div class="icon">📧</div>
                    <div style="font-size:1.6rem; font-weight:800; color:#667eea">{df['Email'].astype(bool).sum()}</div>
                    <div class="label">With Email</div>
                </div>
                <div class="stat-card">
                    <div class="icon">💼</div>
                    <div style="font-size:1.6rem; font-weight:800; color:#667eea">{df['LinkedIn'].astype(bool).sum()}</div>
                    <div class="label">On LinkedIn</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            search = st.text_input("🔍  Search contacts", placeholder="Filter by any field…")
            if search:
                mask = df.apply(
                    lambda row: row.astype(str).str.contains(search, case=False).any(),
                    axis=1,
                )
                df = df[mask]
                st.caption(f"{len(df)} result(s) for "{search}"")

            st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Could not load contacts: {e}")

# ── Tab 3: Ask AI ─────────────────────────────────────────────────────────────

with tab_ai:
    st.markdown("#### Ask anything about your contacts")

    st.markdown("""
    <div class="chip-row">
        <span class="chip">🎯 "Who did I meet at an AI conference?"</span>
        <span class="chip">🔍 "Show me everyone named Sam"</span>
        <span class="chip">💡 "Who works in product management?"</span>
        <span class="chip">📍 "People I met in New York"</span>
    </div>
    """, unsafe_allow_html=True)

    question = st.text_input("Your question", placeholder="Ask in plain English…")
    if st.button("✨  Ask AI", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Please type a question first.")
        else:
            with st.spinner("Searching your contacts…"):
                try:
                    df = load_contacts()
                    answer = ask_ai(question.strip(), df)
                    st.markdown(
                        f'<div class="ai-answer">{answer}</div>',
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    st.error(f"AI error: {e}")
