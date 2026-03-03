# Monday.com BI Agent

A conversational AI agent that answers founder-level business intelligence queries through **live Monday.com API calls**. No data caching — every answer is fresh.

---

## Live Demo

> **App:** `[https://your-app.up.railway.app](https://mondayagent-production.up.railway.app/)`

---

## What It Does

Ask plain English business questions. The agent queries your Monday.com boards live, cleans the messy data, and returns a concise founder-level answer with full transparency into every API call it made.

**Example queries:**
- *"How's our pipeline looking?"*
- *"Top sectors by deal value"*
- *"Which deals are stuck in negotiation?"*
- *"Total receivables outstanding"*
- *"Show all open work orders in the Mining sector"*
- *"Which work orders haven't been invoiced yet?"*

---

## Architecture

```
User (Browser)
     │
     ▼
Frontend (HTML/JS)
  - Chat interface
  - Live tool-call trace panel
     │
     ▼
Flask Backend (Python)
  - /api/chat       ← agent entry point
  - /api/status     ← connection health check
  - /api/reset      ← clear conversation history
     │
     ├── agent.py          ← Groq LLM with tool-use loop
     │     └── monday_query tool (action: schema | aggregate | filter | chunk)
     │
     ├── tools.py          ← 4 surgical data tools
     │     ├── get_board_schema   → columns, unique values, row count
     │     ├── aggregate_board    → group-by totals (tiny response)
     │     ├── filter_board       → matching rows only
     │     └── get_board_chunk    → paginated raw rows
     │
     ├── api.py            ← Monday.com GraphQL client (paginated)
     └── cleaning.py       ← Pandas normalization pipeline
          │
          ▼
     Monday.com API (live, every query)
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| LLM | Groq — Llama 3.3 70B | Free tier, fast inference, supports tool use |
| Backend | Python + Flask | Pandas-friendly, minimal boilerplate |
| Data cleaning | Pandas | Robust handling of messy real-world data |
| Monday.com | GraphQL REST API | Stable, well-documented, paginated |
| Frontend | Vanilla HTML/CSS/JS | Zero build step, served directly by Flask |
| Hosting | Railway.app | One-command GitHub deploy |

---

## Project Structure

```
bi-agent/
├── backend/
│   ├── main.py            # Flask server — routes + session management
│   ├── agent.py           # Groq agent loop with tool use
│   ├── tools.py           # 4 data retrieval tools
│   ├── api.py             # Monday.com API client (cursor pagination)
│   ├── cleaning.py        # Data normalization pipeline
│   ├── index.html         # Frontend (served by Flask at /)
│   ├── requirements.txt
│   ├── Procfile           # Railway/Render deploy config
│   ├── railway.json
│   └── .env.example
└── README.md
```

---

## Local Setup

### Prerequisites
- Python 3.10+
- A Monday.com account with two boards (Deals + Work Orders)
- A free Groq API key from [console.groq.com](https://console.groq.com)

### 1. Install dependencies

```bash
cd bi-agent/backend
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
MONDAY_API_TOKEN=your_monday_api_token
GROQ_API_KEY=your_groq_api_key
DEALS_BOARD_ID=your_deals_board_id
WORK_ORDERS_BOARD_ID=your_work_orders_board_id
PORT=8000
```

**Getting your Monday.com API token:**
1. Log into monday.com
2. Click your profile picture (top right) → Developers
3. My Access Tokens → Show → Copy

**Getting your Board IDs:**
- Open each board in Monday.com
- The ID is the number in the URL: `monday.com/boards/1234567890`

**Getting your Groq API key:**
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up free (no credit card required)
3. API Keys → Create API Key → Copy

### 3. Run

```bash
python main.py
```

Open [http://localhost:8000](http://localhost:8000)

---

## Deploy to Railway

### 1. Push to GitHub

```bash
cd bi-agent
git init
git add .
git commit -m "Monday BI Agent"
git remote add origin https://github.com/YOUR_USERNAME/monday-bi-agent.git
git push -u origin main
```

### 2. Deploy

1. Go to [railway.app](https://railway.app) → Sign up with GitHub
2. **New Project** → **Deploy from GitHub repo** → select `monday-bi-agent`
3. In project settings → **Root Directory** → set to `backend`
4. **Variables** tab → add all four environment variables:

```
MONDAY_API_TOKEN
GROQ_API_KEY
DEALS_BOARD_ID
WORK_ORDERS_BOARD_ID
```

5. Railway auto-deploys and gives you a public URL

---

## How the Agent Works

### Tool-Use Loop

Every user query triggers a multi-step reasoning loop:

```
User: "Top sectors by deal value"

Step 1 → monday_query(action="schema", board="deals")
         ← columns, unique sector values, row count (~50 tokens)

Step 2 → monday_query(action="aggregate", board="deals",
                       group_by="Sector",
                       metrics=["sum:Deal Value"])
         ← grouped totals per sector (~150 tokens)

Step 3 → Agent reasons over results, formats answer

Answer: "Top sector is Powerline at Rs.81.29 Cr across X deals..."
```

### The 4 Tools

| Tool (action) | Use case | Response size |
|---------------|----------|---------------|
| `schema` | Learn columns + unique values before querying | ~50 tokens |
| `aggregate` | Grouped totals — by sector, stage, status | ~150 tokens |
| `filter` | Specific rows — "deals stuck in negotiation" | ~200–500 tokens |
| `chunk` | Paginate raw rows when no filter applies | ~300–600 tokens |

### Token Management

Groq's free tier has a 12,000 TPM limit. The agent handles this via:
- **Aggregation first** — most questions need totals, not raw rows
- **Column selection** — filter/chunk tools only return requested columns
- **Row caps** — filter and chunk are hard-capped at 30 rows per call
- **History trimming** — old tool results are compressed to stubs after the model consumes them

---

## Data Cleaning

All board data passes through a normalization pipeline before the agent sees it:

| Data type | Problem | Fix |
|-----------|---------|-----|
| Currency | `12,000` / `12K` / `1.2L` / plain number | Normalized to float |
| Sectors | `"MINING"` / `"mining "` / `"Mining"` | Lowercased, stripped, title-cased |
| Dates | `"March 2026"` / `"03-2026"` / datetime | `pd.to_datetime` auto-parse |
| Nulls | `None` / `""` / `"N/A"` / `"nan"` | Tracked and reported as caveats |
| Header leakage | Row where item name equals column header | Skipped on import |

Data quality caveats are always included in the agent's answer — e.g. *"177 of 336 deals had Rs.0 value and were excluded from totals."*

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Chat UI |
| GET | `/api/status` | Monday.com connection health |
| POST | `/api/chat` | Send a message to the agent |
| POST | `/api/reset` | Reset conversation history |

### POST `/api/chat`

**Request:**
```json
{
  "message": "How's our pipeline looking?",
  "session_id": "session_abc123"
}
```

**Response:**
```json
{
  "answer": "Your total open pipeline is Rs.14.2 Cr across 89 deals...",
  "trace": [
    { "type": "tool_call",    "message": "monday_query → action=schema, board=deals" },
    { "type": "api_call",     "message": "Calling Monday.com API → Deals board" },
    { "type": "api_response", "message": "344 rows fetched" },
    { "type": "processing",   "message": "Normalization complete — 3 caveats" }
  ],
  "session_id": "session_abc123"
}
```

---

## Known Limitations

- **Groq free tier** — 12,000 TPM limit. Complex multi-board queries may hit this; retry after 60 seconds.
- **In-memory sessions** — conversation history resets on server restart.
- **Llama tool reliability** — occasionally retries tool calls; agent gives up after 8 turns.
- **MCP not implemented** — uses REST API; MCP integration is a noted future improvement.
