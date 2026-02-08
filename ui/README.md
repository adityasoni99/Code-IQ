# Codebase Knowledge Builder — UI (Streamlit)

Phase 1: **link** (GitHub URL) or **upload** (zip), view-only result (summary + download zip). Uses the **async API** (POST /v1/jobs or POST /v1/jobs/upload, poll GET /v1/jobs/{id}). Max upload **50 MB**.

## Prerequisites

1. **API running** — Start the FastAPI server first:
   ```bash
   uv run uvicorn api.app:app --reload
   ```
   Default: http://localhost:8000

2. **UI dependencies** — Install with optional `ui` extra:
   ```bash
   uv sync --extra ui
   ```

## Run the UI

```bash
uv run streamlit run ui/app.py
# or: streamlit run ui/app.py   (if venv active)
```

Browser opens at http://localhost:8501.

## Configuration

- **`API_BASE_URL`** (optional): API base URL. Default: `http://localhost:8000`.
  ```bash
  export API_BASE_URL=http://localhost:8000
  streamlit run ui/app.py
  ```

## Flow

1. Enter GitHub repo URL (required), optional project name and language.
2. Click **Generate tutorial** → creates async job (POST /v1/jobs).
3. UI polls GET /v1/jobs/{id} every 1 s until status is `completed` or `failed`.
4. On success: summary is shown; **Download tutorial (zip)** fetches GET /v1/jobs/{id}/result and offers the zip.
5. On failure: error message from the job is shown.
