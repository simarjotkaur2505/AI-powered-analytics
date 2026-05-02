# AI-Powered SQL Analytics Dashboard

Ask a business question in plain English → get auto-generated SQL → see results, a chart, and AI-written insights — all in one screen.

---

## Tech Stack

| Layer | Tool |
|---|---|
| UI | Streamlit |
| LLM | OpenAI `gpt-4.1-mini` |
| Database | SQLite (via `sqlite3`) |
| Data wrangling | pandas |
| Charts | Plotly Express |
| Data seeding | Faker |

---

## Project Structure

```
AI-powered-analytics/
├── app.py              # Streamlit entry point
├── data/
│   ├── seed.py         # generates analytics.db
│   └── analytics.db    # SQLite DB (auto-generated, git-ignored)
├── src/
│   ├── db.py           # DB connection + query execution
│   ├── ai.py           # text_to_sql + generate_insight
│   ├── prompts.py      # all LLM prompt templates
│   └── charts.py       # chart selection + Plotly renderers
├── logs/
│   └── app.log         # runtime logs (git-ignored)
├── requirements.txt
├── .env.example
└── DESIGN.md           # full design document
```

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/<you>/AI-powered-analytics.git
cd AI-powered-analytics
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Add your OpenAI API key

```bash
cp .env.example .env
# Open .env and set:
# OPENAI_API_KEY=sk-...
```

Get a key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

### 3. Seed the database

```bash
python data/seed.py
```

Output:
```
Seeding database → data/analytics.db
  customers:   1,000
  products:    80
  orders:      5,000
  order_items: 15,033
Done. analytics.db is ready.
```

### 4. Run the dashboard

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## How It Works

```
User question
    ↓
OpenAI gpt-4.1-mini  →  SQL query
    ↓
sqlite3              →  pandas DataFrame
    ↓
Plotly               →  chart
    ↓
OpenAI gpt-4.1-mini  →  bullet-point insights
    ↓
Streamlit dashboard
```

1. You type a question (or click an example).
2. The LLM converts it to a valid SQLite `SELECT` query using the database schema as context.
3. The query runs against `analytics.db` and returns a DataFrame.
4. A chart is picked automatically (line for trends, bar for categories, scatter for two numerics).
5. The LLM reads the results and writes 3–5 business insights.

All LLM calls and query results are logged to `logs/app.log`.

---

## Example Questions

| Question | What you see |
|---|---|
| Top 5 customers by revenue | Bar chart + revenue table |
| Monthly revenue trend last 12 months | Line chart |
| Revenue by product category | Bar chart |
| Return rate by country | Horizontal bar |
| New customers per month | Line chart |
| Average order value by segment | Bar chart |

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI secret key |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Switch to `gpt-4.1` for higher SQL quality |
| `DB_PATH` | `data/analytics.db` | Path to the SQLite database |
| `LOG_PATH` | `logs/app.log` | Path for runtime logs |
| `MAX_ROWS_FOR_INSIGHT` | `50` | Max rows sent to LLM for insight generation |

---

## Re-seeding

To start fresh with a new dataset:

```bash
python data/seed.py   # drops and recreates all tables
```

---

## Safety

Only `SELECT` statements are allowed to run. Any LLM response that starts with `INSERT`, `UPDATE`, `DELETE`, `DROP`, etc. is blocked and shown as an error.
