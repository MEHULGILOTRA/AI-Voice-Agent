# Agentic AI Bot

A production-ready multi-agent automation system for education centres built with **LangGraph**, **FastAPI**, and **Google Sheets**. It handles parent outreach calls and student Telegram messaging — with human-in-the-loop review, retry logic, opt-out enforcement, and full audit trails.

## What This Does

- **Outreach agent** — simulates or handles live parent phone calls, extracts contact details from transcripts using regex, scores data confidence, and writes to Google Sheets.
- **Telegram agent** — sends contextual messages to students (homework reminders, missed-class alerts, satisfaction surveys) using only data from the student record — zero hallucination by design.
- **Human-in-the-loop** — when confidence is too low, the graph pauses and queues a review item. An operator corrects the data via REST API and the graph resumes exactly where it stopped.

**Zero LLM calls** anywhere in the system — both agents are 100% rule-based. No OpenAI key required. No per-call costs.

## Quick Start

```bash
# 1. Install dependencies (requires Python 3.11)
export PATH="$HOME/.local/bin:$PATH"
poetry install

# 2. Configure environment
cp .env.example .env
# Edit .env — no keys required for mock mode

# 3. Start the server
poetry run uvicorn app.main:app --reload

# 4. Health check
curl http://localhost:8000/health

# 5. Run a demo scenario
curl -X POST http://localhost:8000/api/v1/outreach/scenario/S001/run

# 6. Run all tests
poetry run pytest --cov=app tests/ -q
```

See [`demo.txt`](demo.txt) for a full copy-paste walkthrough of all scenarios.

## Architecture

See [`ARCHITECTURE.txt`](ARCHITECTURE.txt) for the full ASCII diagram and layer-by-layer explanation.

```
HTTP Request
    │
    ▼
FastAPI  (app/main.py)
    │
    ├── Outreach LangGraph  ── 0 LLM calls (rule-based)
    └── Telegram LangGraph  ── 0 LLM calls (rule-based)
            │
        MemorySaver (session state, interrupt/resume)
            │
        Google Sheets  (sole data layer — no database)
```

## Configuration

All settings are environment variables loaded from `.env`. Defaults work out of the box with mock mode.

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_SHEETS_URL` | *(empty)* | Spreadsheet URL — leave empty for mock mode |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | `./credentials.json` | Service account key file path |
| `VAPI_MOCK_MODE` | `true` | `false` → real Vapi voice calls |
| `VAPI_API_KEY` | *(empty)* | Required when `VAPI_MOCK_MODE=false` |
| `WHATSAPP_MOCK_MODE` | `true` | `false` → real Twilio WhatsApp messages |
| `WHATSAPP_API_KEY` | *(empty)* | Twilio account SID |
| `WHATSAPP_FROM_NUMBER` | `whatsapp:+14155238886` | Twilio sandbox number |
| `TELEGRAM_MOCK_MODE` | `true` | `false` → real Telegram Bot API calls |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Required when `TELEGRAM_MOCK_MODE=false` |
| `CONFIDENCE_THRESHOLD` | `0.75` | Score below this triggers human review |
| `QUIET_HOURS_START` | `21` | Hour (24h) after which no outreach is sent |
| `QUIET_HOURS_END` | `8` | Hour (24h) after which outreach resumes |
| `SESSION_TTL_SECONDS` | `3600` | How long to keep inactive sessions in memory |

## API Endpoints

### Outreach
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/outreach/scenario/{id}/run` | Run a demo scenario (S001–S005) |
| `POST` | `/api/v1/outreach/start` | Production entry point |

### Telegram
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/telegram/send` | Send a message to a student |
| `GET` | `/api/v1/telegram/students` | List all student records |
| `GET` | `/api/v1/telegram/session/{id}` | Inspect a session's LangGraph state |

### Review & Audit
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/review/pending` | Get all unresolved human review items |
| `POST` | `/api/v1/review/{id}/resolve` | Resume a paused session with operator edits |
| `GET` | `/api/v1/audit/logs` | Full audit trail (filter by `?session_id=`) |

### Health
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe (checks Sheets connection) |

## Adapting the System

### Add a new Telegram use case

Edit **one file**: `app/agents/telegram/templates.py`

```python
# 1. Add the template
TEMPLATES["progress_update"] = (
    "Hi {student_name}, great progress in {course_name}! "
    "Your streak is {attendance_streak} sessions. Keep it up!"
)

# 2. Add required variables
REQUIRED_VARS["progress_update"] = ["student_name", "course_name", "attendance_streak"]
```

No routing changes, no new nodes, no new API endpoints needed.

### Add a new outreach data field

1. Add the field to `app/agents/outreach/nodes.py` → `extract_data` (regex extraction)
2. Add field weight to `app/core/confidence.py`
3. Add column to `PARENT_HEADERS` in `app/services/sheets.py`
4. Add field to `app/schemas/parent.py` → `ParentRecord`

### Connect real Google Sheets

1. Create a Google Service Account and download `credentials.json`
2. Share the spreadsheet with the service account email (Editor role)
3. Set in `.env`:
   ```
   GOOGLE_SHEETS_URL=https://docs.google.com/spreadsheets/d/YOUR_ID/edit
   GOOGLE_SHEETS_CREDENTIALS_JSON=./credentials.json
   ```
4. Restart the server. All four tabs are created automatically on first write.

### Switch to real APIs

```bash
# Real voice calls via Vapi
VAPI_MOCK_MODE=false
VAPI_API_KEY=your_vapi_key

# Real WhatsApp via Twilio
WHATSAPP_MOCK_MODE=false
WHATSAPP_API_KEY=your_twilio_account_sid

# Real Telegram Bot
TELEGRAM_MOCK_MODE=false
TELEGRAM_BOT_TOKEN=your_bot_token
```

## Running Tests

```bash
export PATH="$HOME/.local/bin:$PATH"

# All tests with coverage report
poetry run pytest --cov=app tests/ -q

# Unit tests only
poetry run pytest tests/unit/ -q

# Integration tests only
poetry run pytest tests/integration/ -q

# Verbose output for a single test
poetry run pytest tests/integration/test_telegram_graph.py -v
```

57 tests total. All run fully offline — no real API calls, no LLM calls.

## Project Structure

```
app/
├── main.py                    # FastAPI app + lifespan startup
├── config.py                  # Pydantic settings (all env vars)
│
├── api/v1/
│   ├── outreach.py            # Outreach endpoints
│   ├── telegram.py            # Telegram endpoints
│   ├── review.py              # Human review queue endpoints
│   └── audit.py               # Audit log endpoint
│
├── agents/
│   ├── outreach/
│   │   ├── graph.py           # LangGraph graph builder
│   │   ├── nodes.py           # Graph nodes (rule-based, zero LLM)
│   │   └── state.py           # OutreachState TypedDict
│   ├── telegram/
│   │   ├── graph.py           # LangGraph graph builder
│   │   ├── nodes.py           # Graph nodes (zero LLM calls)
│   │   ├── state.py           # TelegramState TypedDict
│   │   └── templates.py       # All message copy — edit this to add use cases
│   └── shared/
│       ├── review_queue.py    # In-memory human review queue
│       └── utils.py           # Shared helpers (append_trail, etc.)
│
├── core/
│   ├── confidence.py          # Field-weight confidence scoring
│   ├── idempotency.py         # SHA256 duplicate-write prevention
│   ├── memory.py              # MemorySaver + session TTL pruning
│   ├── opt_out.py             # In-memory opt-out cache
│   ├── quiet_hours.py         # Time-of-day send restrictions
│   └── retry.py               # @with_retry decorator (tenacity)
│
├── schemas/
│   ├── common.py              # AuditLogEntry, shared types
│   ├── parent.py              # ParentRecord, OutreachStatus
│   ├── student.py             # StudentRecord, TelegramMessageRequest
│   └── review.py              # HumanReviewItem
│
└── services/
    ├── sheets.py              # Google Sheets client (gspread)
    ├── vapi.py                # Voice call service
    ├── whatsapp.py            # WhatsApp service
    ├── telegram_client.py     # Telegram Bot client
    └── audit.py               # Audit log writer

tests/
├── conftest.py                # Pytest fixtures (mock_sheets, graphs, etc.)
├── unit/                      # Pure logic tests (no I/O)
│   ├── test_confidence.py
│   ├── test_quiet_hours.py
│   ├── test_opt_out.py
│   ├── test_idempotency.py
│   └── test_templates.py
├── integration/               # Full graph execution tests
│   ├── test_outreach_graph.py
│   └── test_telegram_graph.py
└── test_data/
    ├── parents.json           # 10 synthetic parent records (P001–P010)
    ├── students.json          # 10 synthetic student records (ST001–ST010)
    ├── scenarios.json         # 5 scenario configs
    └── transcripts/           # Call transcript fixtures (S001–S005, default)
```
