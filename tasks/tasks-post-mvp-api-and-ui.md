# Task List: Post-MVP API and UI

Generated from [docs/post-mvp-plan.md](../docs/post-mvp-plan.md). Implements API (sync, async, webhooks) and UI (link, upload, view-only, optional edit).

## Relevant Files

- `api/` or `server/` — New API layer (e.g. FastAPI app). Contains routes, job runner, and integration with existing flow.
- `api/app.py` or `server/main.py` — API application entry point; mounts v1 routes.
- `api/routes/v1/build.py` — Sync `POST /v1/build` handler; builds shared store from request, runs flow, returns result or 202 + job_id.
- `api/routes/v1/jobs.py` — Async job routes: `POST /v1/jobs`, `GET /v1/jobs/{id}`, `GET /v1/jobs/{id}/result`.
- `api/job_store.py` — Job storage (in-memory or DB): create job, update status, get job, list (optional); job retention/cleanup.
- `api/schemas.py` — Pydantic or similar request/response models for build and job payloads.
- `api/runner.py` — Runs the existing flow in a thread or background task; updates job status; triggers webhook on completion/failure.
- `api/webhooks.py` — Webhook delivery: sign payload (e.g. HMAC), POST to callback URL, retry policy.
- `flow.py` — Existing flow; API runner invokes `create_flow().run(shared)`.
- `main.py` — Existing CLI; unchanged for post-MVP (API is a separate entry point).
- `shared_schema.py` — Existing shared store defaults; API builds shared dict from request using same schema.
- `ui/` — Frontend: either Streamlit (`ui/app.py` or `streamlit_app.py`) or NextJS app (`apps/web/` or separate repo). Tasks below are phrased so they apply to either; choose Streamlit vs NextJS before starting task 3.0.
- `tests/test_api_build.py` — Tests for sync build endpoint (success, timeout/202, validation).
- `tests/test_api_jobs.py` — Tests for async job creation, status, result.
- `tests/test_api_webhooks.py` — Tests for webhook payload and signature (mock HTTP outbound).
- `docs/post-mvp-plan.md` — Reference for API contract and UI scope.

### Notes

- Choose **Streamlit** (faster, same repo) or **NextJS + Tailwind** (product-grade, frontend-design skill) before task 3.0; see [docs/post-mvp-plan.md](../docs/post-mvp-plan.md) §3.
- API can be implemented with FastAPI or Flask; adjust file names (e.g. `api/main.py` for FastAPI) as needed.
- Unit tests for API should mock the flow and job store; integration tests can run a real flow with a tiny repo.

## Instructions for Completing Tasks

**IMPORTANT:** You must check off each task in this file by changing `- [ ]` to `- [x]` when done. Update after each sub-task, not only after the whole parent task.

Example:
- `- [ ] 1.1 Implement route` → `- [x] 1.1 Implement route` (after completing)

## Tasks

- [x] 0.0 Create feature branch
  - [x] 0.1 Create and checkout a new branch (e.g. `git checkout -b feature/post-mvp-api-and-ui`).

- [x] 1.0 Sync API — POST /v1/build
  - [x] 1.1 Add API layer: create FastAPI app (e.g. `api/app.py`), define Pydantic request model in `api/schemas.py` with `repo_url` (optional), `project_name`, `language`, `output_dir`, `github_token` (optional); mount v1 router and expose `POST /v1/build` that accepts JSON body.
  - [x] 1.2 Implement build handler: map request body to shared store using `shared_schema.default_shared_store()` and override with request fields; call `create_flow().run(shared)` from `flow.py`; on success return 200 with body e.g. `{ "final_output_dir": "...", "summary": "..." }` (or zip URL if you add it).
  - [x] 1.3 Enforce max duration (e.g. 5 min): run flow in a thread with a timeout or use async with `asyncio.wait_for`; if exceeded, either enqueue as async job and return 202 with `{ "job_id": "...", "message": "Run exceeded max duration; poll GET /v1/jobs/{id}" }` or return 413 with clear message; document choice in `docs/post-mvp-plan.md` or README.
  - [x] 1.4 Validate request: require exactly one of `repo_url` or (for later) upload; return 400 with `{ "detail": "Provide repo_url or upload" }` and validate `language`/`output_dir` if needed.
  - [x] 1.5 Add tests in `tests/test_api_build.py`: mock flow; test 200 with valid `repo_url`; test 400 when neither `repo_url` nor upload; test timeout/202 or 413 when flow runs too long (mock slow flow).

- [x] 2.0 Async API — jobs, status, result
  - [x] 2.1 Implement job store in `api/job_store.py`: `create_job(inputs) -> job_id`, `update_status(job_id, status, result=None, error=None)`, `get_job(job_id) -> dict|None`; store `created_at`, `updated_at`; use in-memory dict keyed by UUID for MVP (or SQLite/Redis later); add optional cleanup of jobs older than 24 h and document in README.
  - [x] 2.2 Implement `POST /v1/jobs` in `api/routes/v1/jobs.py`: accept same JSON body as sync build; create job via job_store, spawn background task (e.g. `threading.Thread` or `asyncio.create_task`) that runs `api/runner.py`; return 201 with `{ "job_id": "<uuid>", "status": "queued" }` and `Location: /v1/jobs/<id>` header.
  - [x] 2.3 Implement `api/runner.py`: accept job_id and job inputs; build shared store, set status `running`, call `create_flow().run(shared)`; on success call `job_store.update_status(job_id, "completed", result=...)`; on exception call `update_status(job_id, "failed", error=str(e))`; do not expose webhook yet (task 4).
  - [x] 2.4 Implement `GET /v1/jobs/{job_id}`: return JSON `{ "job_id", "status", "created_at", "updated_at", "result" (if completed), "error" (if failed) }`; return 404 if job not in store or expired.
  - [x] 2.5 Implement `GET /v1/jobs/{job_id}/result`: if status is `completed`, stream or return zip of `final_output_dir` with `Content-Type: application/zip` and `Content-Disposition: attachment`; if status is `queued` or `running` return 409 Conflict; if failed or missing return 404.
  - [x] 2.6 Add tests in `tests/test_api_jobs.py`: create job with mocked flow that completes; poll GET until status `completed` and assert result; create job with failing flow and assert status `failed` and error; GET unknown job_id and assert 404.

- [x] 3.0 UI Phase 1 — link input, view-only, download
  - [x] 3.1 Choose frontend stack (Streamlit or NextJS + Tailwind) per [docs/post-mvp-plan.md](../docs/post-mvp-plan.md) §3; create `ui/` (or `apps/web/` for NextJS); add `ui/app.py` and `streamlit run ui/app.py` for Streamlit, or `npx create-next-app` with Tailwind for NextJS; add env or config for API base URL (e.g. `http://localhost:8000`).
  - [x] 3.2 Implement input form: field for GitHub repo URL (required), optional project name and language dropdown; Submit button calls `POST /v1/build` (sync) or `POST /v1/jobs` (async)—pick one and document in UI README (async recommended for larger repos).
  - [x] 3.3 If using async: after 201 from POST, redirect or show job page with job_id; poll `GET /v1/jobs/{id}` every 2–5 s; show status badge (Queued / Running / Completed / Failed) and spinner while running; on failed show `error` from response.
  - [x] 3.4 On success: if sync, use response body; if async, fetch zip from `GET /v1/jobs/{id}/result` or a new endpoint that returns index + chapters as JSON. Render index (summary, Mermaid diagram, chapter links) and chapters (tabs or sidebar); use a Markdown renderer for chapter body.
  - [x] 3.5 Add download button: for sync response with `final_output_dir` or zip URL, link to it; for async, link to `GET /v1/jobs/{id}/result` with `Content-Disposition: attachment` so browser downloads zip.
  - [x] 3.6 Add `ui/README.md` (or section in main README): how to run UI (`streamlit run ui/app.py` or `npm run dev`), set API base URL, and run API locally (e.g. `uvicorn api.app:app --reload`).

- [x] 4.0 Webhooks — optional callback on job completion/failure
  - [x] 4.1 Add optional `webhook_url` to `POST /v1/jobs` request body and to job store schema; persist on job record; do not include in `GET /v1/jobs/{id}` response; document in API docs.
  - [x] 4.2 Implement `api/webhooks.py`: `deliver_webhook(job_id, status, result, error, completed_at)` builds JSON payload, computes HMAC-SHA256 of body using `WEBHOOK_SECRET` env, POSTs to stored `webhook_url` with header `X-Webhook-Signature: <hex>`; call from runner after `update_status(..., "completed"|"failed")`.
  - [x] 4.3 Add retry in webhook delivery: on non-2xx or timeout, retry up to 3 times with exponential backoff (e.g. 1s, 2s, 4s); set `Delivery-Attempt: 1..3` header; document in README.
  - [x] 4.4 Add `tests/test_api_webhooks.py`: mock `requests.post` or httpx; create job with `webhook_url` and mock flow; assert POST to that URL with correct JSON and valid signature; assert retry on 500/timeout.

- [x] 5.0 UI — Upload (zip)
  - [x] 5.1 Add upload input to UI: file picker or drag-drop for zip; client-side check max size (e.g. 50 MB) and show error; optional toggle or tab "Link" vs "Upload" so user picks one.
  - [x] 5.2 Add API support: new route or same `POST /v1/build`/`POST /v1/jobs` accepting `multipart/form-data` with file field (e.g. `file`); extract zip with `zipfile` to temp dir (e.g. `tempfile.mkdtemp()`); build shared with `local_dir=temp_path`; run flow; in `finally` block remove temp dir; enforce max upload size (e.g. 50 MB) and return 413 if exceeded.
  - [x] 5.3 Wire UI: on upload submit send file in form; if async, pass job_id and poll as in 3.3; on completion show same result view and download button as link-based flow.
  - [x] 5.4 Document in README: max zip size, server-side extraction, and retention; add test in `tests/test_api_build.py` or new file: upload small zip (e.g. 2–3 files), assert 200 and output dir contains `index.md` and chapter files.

- [x] 6.0 UI Phase 2 — Edit (optional)
  - [x] 6.1 Define edit scope in a short design note: editable fields (summary, chapter title, chapter body), reorder chapters (drag-and-drop), actions (save, regenerate one chapter, regenerate full). Decide API: e.g. `PATCH /v1/projects/{id}` for persisted project with result JSON, or `POST /v1/regenerate` with job_id + scope (one chapter vs full); document choice.
  - [x] 6.2 Implement API: e.g. project resource with stored result (summary, chapters array); `PATCH` to update fields; `POST /v1/projects/{id}/regenerate` with `{ "scope": "chapter"|"full", "chapter_index"?: number }` that enqueues a job and returns job_id; persist project id in job result or link job to project.
  - [x] 6.3 Add edit screen in UI: load project/result; form fields for summary and each chapter (title + body); reorder list (drag-and-drop); Save calls PATCH; Regenerate chapter/full calls regenerate endpoint and shows job status until done, then refreshes result.
  - [x] 6.4 Add tests for PATCH project and regenerate endpoint; optional E2E or UI test for edit flow; document in README how to use edit.
