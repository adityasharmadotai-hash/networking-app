# 🤝 Networking Contacts App

> **Never lose a contact again.** A smart, AI-powered contact book built for people who meet dozens of people at events and never want to lose track of them.

---

## 🌟 Support & Connect

If this project helped you, please consider:

| | |
|---|---|
| ⭐ **Star the repo** | [github.com/adityasharmadotai-hash](https://github.com/adityasharmadotai-hash) |
| 💼 **Follow on LinkedIn** | [linkedin.com/in/aditya-hicounselor](https://www.linkedin.com/in/aditya-hicounselor/) |
| 📺 **Subscribe on YouTube** | [YouTube Channel](https://www.youtube.com/channel/UCPjQtVNUrf7EKrm8ZoqrCAQ) |
| 🚀 **AI Jobs in the USA** | [Join the Waitlist](https://docs.google.com/forms/d/e/1FAIpQLSc3gJssBV3B25EZ3sYA7Qcen9NbtOB_wgQaturfB7lTXuAdLQ/viewform) |

---

## 📖 Overview

Every networking event ends the same way — you meet 10 interesting people, collect business cards or swap numbers, and then three weeks later you can't remember who was who or where you met them.

This app solves that. Open it on your phone right after meeting someone, fill in their details and a quick note about the context, and it's saved forever. Later, ask the AI *"who did I meet at the AI Summit?"* or *"find everyone who works in product"* — and it pulls them up instantly.

No spreadsheets. No apps to install. Just a URL you open on your phone.

---

## ✨ Features

- **📇 Quick Contact Entry** — Name, email, phone, LinkedIn URL, and a free-form notes field
- **☁️ Cloud Database** — Every contact is saved to Supabase (PostgreSQL) in real time
- **🔍 Instant Search** — Filter across all fields with a single search box
- **🤖 AI-Powered Queries** — Ask questions in plain English: *"Who works in fintech?"*, *"Show me people I met in New York"*
- **📊 Contact Stats** — See total contacts, how many have emails, how many are on LinkedIn
- **📱 Mobile-First** — Works great on a phone browser, no app install needed
- **🎨 Beautiful UI** — Gradient hero, card layout, clean typography

---

## 🔄 How It Works

```
┌─────────────────────────────────────────────────────────┐
│                   USER ON PHONE/BROWSER                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   STREAMLIT APP (app.py)                │
│                                                         │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────┐   │
│   │  ➕ Add      │  │  📋 View All  │  │  🤖 Ask AI  │   │
│   │  Contact    │  │  Contacts    │  │             │   │
│   └──────┬──────┘  └──────┬───────┘  └──────┬──────┘   │
└──────────┼────────────────┼─────────────────┼──────────┘
           │                │                 │
           ▼                ▼                 ▼
┌──────────────────┐  ┌──────────────┐  ┌────────────────┐
│  SUPABASE DB     │  │  SUPABASE DB │  │  OPENAI GPT-4o │
│  INSERT row      │  │  SELECT all  │  │  Read contacts │
│                  │  │  rows        │  │  Answer query  │
└──────────────────┘  └──────────────┘  └────────────────┘
```

**Flow:**
1. User opens the app on their phone
2. Fills in contact details → saved instantly to Supabase
3. Can view all contacts with live search filtering
4. Types a natural language question → OpenAI reads all contacts and returns a smart answer

<img width="1292" height="1768" alt="image" src="https://github.com/user-attachments/assets/e611d5ae-089d-44fa-bb00-fc34aba93f54" />

<img width="1488" height="1746" alt="image" src="https://github.com/user-attachments/assets/56947695-dd42-44b2-865f-dd4b58d4a8d3" />


---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | [Streamlit](https://streamlit.io) | Python-based web UI, runs in the browser |
| **Database** | [Supabase](https://supabase.com) | Free PostgreSQL cloud database |
| **AI** | [OpenAI GPT-4o](https://openai.com) | Natural language search over contacts |
| **Language** | Python 3.9+ | Everything runs in Python |
| **Hosting** | [Streamlit Community Cloud](https://share.streamlit.io) | Free deployment, public URL |

---

## 📁 File Structure

```
networking-app/
│
├── app.py              # The entire application (UI + database + AI logic)
├── requirements.txt    # Python dependencies
├── .gitignore          # Keeps secrets out of GitHub
└── README.md           # This file
```
<img width="3024" height="1964" alt="image" src="https://github.com/user-attachments/assets/5a7544b2-402e-495f-9564-6c1e54dca851" />


That's it — the whole app is a single Python file.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- A free [Supabase](https://supabase.com) account
- An [OpenAI](https://platform.openai.com) API key

### 1. Clone the repo

```bash
git clone https://github.com/adityasharmadotai-hash/networking-app.git
cd networking-app
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up Supabase

Go to your Supabase project → **SQL Editor** → run this:

```sql
create table contacts (
  id bigint generated always as identity primary key,
  name text,
  email text,
  phone text,
  linkedin text,
  notes text,
  created_at timestamp with time zone default now()
);

alter table contacts disable row level security;
```

### 4. Add your secrets

On Streamlit Cloud, go to your app → **⋮ → Settings → Secrets** and paste:

```toml
OPENAI_API_KEY = "sk-..."
SUPABASE_URL   = "https://xxxx.supabase.co"
SUPABASE_KEY   = "your-publishable-key"
```

### 5. Run locally

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ☁️ Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo and set the main file to `app.py`
4. Click **Advanced settings → Secrets** and paste your three keys
5. Click **Deploy** — you get a public URL you can open on any phone

---

## 📚 Full Tutorial

Want a detailed, beginner-friendly walkthrough of how this entire app was built from scratch — every line of code explained in plain English?

👉 **[Read the full tutorial → TUTORIAL.md](TUTORIAL.md)**

Also check out the tutorial for the companion project:
👉 **[Docs Reader RAG Agent Tutorial](https://github.com/adityasharmadotai-hash/docs-reader-rag-agent/blob/main/TUTORIAL.md)**

---

## 🤝 Contributing

Contributions are welcome! If you have ideas for improvements:

1. Fork the repo
2. Create a new branch: `git checkout -b feature/your-feature`
3. Make your changes and commit: `git commit -m "Add your feature"`
4. Push to your branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — feel free to use it, modify it, and build on top of it.

---

## 👨‍💻 Built By

Made with ❤️ by **Aditya Sharma**

| | |
|---|---|
| 💼 **LinkedIn** | [linkedin.com/in/aditya-hicounselor](https://www.linkedin.com/in/aditya-hicounselor/) |
| 📺 **YouTube** | [YouTube Channel](https://www.youtube.com/channel/UCPjQtVNUrf7EKrm8ZoqrCAQ) |
| 🐙 **GitHub** | [github.com/adityasharmadotai-hash](https://github.com/adityasharmadotai-hash) |
| 🚀 **AI Jobs** | [AI Jobs in the USA](https://docs.google.com/forms/d/e/1FAIpQLSc3gJssBV3B25EZ3sYA7Qcen9NbtOB_wgQaturfB7lTXuAdLQ/viewform) |

If this helped you, a ⭐ on the repo goes a long way!
