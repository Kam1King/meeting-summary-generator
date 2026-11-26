# Smart Meeting Summary Generator

Paste raw meeting notes or a transcript and generate a structured summary with Google Gemini Flash. The app extracts main topics, confirmed decisions, action items, pending discussions, and a short overview. Every extracted item is checked against the original transcript so unsupported names, deadlines, and decisions are flagged instead of being treated as facts.

This is a production-quality MVP: a React dashboard, a FastAPI backend, SQLite storage, Pydantic validation, and pytest coverage with a mocked Gemini client.

## Features

- Paste a transcript and generate a structured meeting summary.
- Separate cards for overview, topics, decisions, action items, and pending discussions.
- Action items table with task, owner, and due date.
- Supporting evidence quotations for extracted items.
- Edit any section and save the updated summary.
- Regenerate a single section without changing the rest.
- Meeting history: reopen a previous meeting and view its transcript and summary.
- Hallucination safeguards: evidence must appear in the transcript; missing owners and dates stay `null`.
- Clear setup error when `GEMINI_API_KEY` is missing.

## Technology stack

**Frontend:** React.js, Vite, JavaScript (JSX), Axios, CSS, Lucide React.

**Backend:** Python, FastAPI, Pydantic, SQLAlchemy, SQLite, Uvicorn.

**AI:** Official `google-genai` Python SDK, `gemini-3.1-flash-lite` by default, temperature `0`, structured JSON output.

**Other:** python-dotenv, Pytest, Git.

The architecture stays modular but simple. There is no Kafka, Redis, Celery, Kubernetes, LangChain, or microservice split.

## Architecture

```
User paste transcript
        ↓
React dashboard (Axios)
        ↓
FastAPI meeting routes
        ↓
MeetingService.process_transcript()
        ↓
LLMService (Gemini Flash) → Pydantic parse
        ↓
ValidationService (evidence + suggestion checks)
        ↓
SQLite meetings table
        ↓
Structured summary in the UI
```

Meeting processing always starts from a **normalized transcript string**. That keeps a future audio path independent of Gemini and the database:

`Audio input → Transcription service → Normalized transcript → MeetingService → Gemini → Structured summary`

Audio transcription is not implemented in this MVP.

### Why Gemini Flash

Gemini 2.5 Flash is fast and inexpensive enough for interactive summarization, and the official SDK supports structured JSON with Pydantic schemas. Temperature is set to `0` so extraction stays consistent. The model ID is configurable through `GEMINI_MODEL` if a key does not have access to the default model.

## Hallucination prevention

Prompts tell the model to extract only transcript-supported facts, to treat suggestions as non-decisions, and to return `null` or empty lists instead of guessing.

The backend does not trust the model. After Gemini responds, `validation_service.py`:

1. Confirms each evidence quotation exists in the original transcript (whitespace-normalized, case-insensitive).
2. Flags items whose evidence is missing rather than silently accepting them.
3. Clears owners or due dates that do not appear in the transcript.
4. Flags decisions whose wording looks like a suggestion unless confirmation language is present.
5. Drops items that have no evidence.
6. Marks the summary as insufficient when nothing usable remains.

The UI shows a “Needs review” badge on flagged items and a warning when the transcript does not contain enough information.

Historical meetings are never mixed into the current extraction. Each request uses only the transcript for that meeting, which keeps the design RAG-ready without leaking old decisions into a new summary.

## Database design

SQLite table `meetings`:

| Column | Purpose |
|---|---|
| `id` | Primary key |
| `title` | Derived from the first transcript line, or a user-provided title |
| `transcript` | Original text |
| `summary_json` | Validated structured summary |
| `created_at` | Creation time |
| `updated_at` | Last edit or regeneration |

JSON storage keeps the schema easy to extend later without extra tables.

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/meetings` | Generate and save a summary |
| `GET` | `/api/meetings` | List saved meetings (`id`, `title`, `created_at`) |
| `GET` | `/api/meetings/{meeting_id}` | Transcript and full summary |
| `PUT` | `/api/meetings/{meeting_id}` | Save an edited summary |
| `POST` | `/api/meetings/{meeting_id}/regenerate` | Regenerate one section: `overview`, `topics`, `decisions`, `action_items`, `pending_discussions` |
| `GET` | `/health` | Backend health and whether Gemini is configured |

## Folder structure

```
SmartMeet/
  README.md
  .gitignore
  backend/
    app/
      main.py
      config.py
      api/meeting_routes.py
      models/meeting_schema.py
      models/database_models.py
      services/llm_service.py
      services/meeting_service.py
      services/prompt_service.py
      services/validation_service.py
      database/database.py
    tests/
      test_meeting_api.py
      test_validation.py
    requirements.txt
    .env.example
  frontend/
    src/App.jsx
    src/api.js
    package.json
```

## Installation

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

### 2. Gemini API key

1. Create a key in [Google AI Studio](https://aistudio.google.com/apikey).
2. Open `backend/.env` and set:

```
GEMINI_API_KEY=your_real_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
DATABASE_URL=sqlite:///./meetings.db
```

Never put the API key in frontend code. If the key is missing, the API returns HTTP 503 with a setup message instead of a fake summary.

If `gemini-3.1-flash-lite` is not available for your key, change `GEMINI_MODEL` to a Flash model your account can use. The app will not silently switch models.

### 3. Frontend

```powershell
cd frontend
npm install
```

Optional: copy `frontend/.env.example` to `frontend/.env` if the API is not at `http://localhost:8000`.

## Run the application

Terminal 1 — backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend:

```powershell
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Run tests

Tests mock Gemini. They do not call the live API.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

Coverage includes successful generation, empty/short transcripts, suggestion vs confirmed decision, missing owner/due date, evidence that is not in the transcript, invalid Gemini output, section regeneration, and retrieving a saved meeting.

## Screenshots

Add local screenshots here after you run the app:

- `docs/screenshot-dashboard.png` — transcript input and generate action
- `docs/screenshot-summary.png` — structured summary cards
- `docs/screenshot-history.png` — saved meeting history

## Future enhancements

- Audio upload and a transcription service that feeds `MeetingService.process_transcript()`.
- RAG with ChromaDB and embeddings for searching across meetings, without injecting old decisions into the current meeting.
- User accounts and sharing.
- Export to Markdown or PDF.

## Known limitations

- Live Gemini quality still depends on the transcript. Validation can flag bad evidence; it cannot recover facts that were never said.
- Evidence matching is substring-based after whitespace normalization. Heavily paraphrased quotations are flagged for review.
- Audio transcription is intentionally out of scope.
- The default model must be available on the configured API key.
