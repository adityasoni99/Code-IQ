# Post-MVP Plan: API, UI Scope, and Frontend Tech

This document plans post-MVP work for the Codebase Knowledge Builder: **API contract** (sync vs async, webhooks), **UI scope** (upload vs link, view-only vs edit), and **frontend technology** (Streamlit vs NextJS + Tailwind CSS), aligned with [docs/design.md](design.md), the PRD, and [.cursor/skills/frontend-design/SKILL.md](../.cursor/skills/frontend-design/SKILL.md).

---

## 1. API Contract

### 1.1 Sync vs Async

The pipeline (FetchRepo → IdentifyAbstractions → AnalyzeRelationships → OrderChapters → WriteChapters → CombineTutorial) can take minutes for larger repos. Exposing it via API implies a choice:

| Aspect | Sync API | Async API |
|--------|----------|-----------|
| **Contract** | `POST /build` (or `/generate`); request body = inputs; response = full result when done. | `POST /jobs` (or `/build?async=true`); response = `job_id`; client polls `GET /jobs/{job_id}` for status and optionally `GET /jobs/{job_id}/result` for output. |
| **Use case** | Small repos, quick demos, scripts that block. | Large repos, UI, integrations; client can show progress or leave. |
| **Risks** | Timeouts (HTTP/gateway), poor UX for long runs. | Need job storage, cleanup, and clear status/error semantics. |

**Recommendation:** Provide **both**.

- **Sync:** `POST /v1/build` — same inputs as CLI (`repo_url` or `local_dir` simulation via upload, `project_name`, `language`, etc.). Return 200 + result (e.g. `final_output_dir` path or zip URL, plus summary) when complete. Enforce a **max duration** (e.g. 5 min); beyond that return 202 + `job_id` and treat as async, or reject with 413. *Implemented: sync returns 413 when run exceeds `BUILD_TIMEOUT_SECONDS`; 202 + job_id will be available when async API (task 2.0) is in place.*
- **Async:** `POST /v1/jobs` — same body; response `201 Created` + `{ "job_id": "...", "status": "queued" }`. `GET /v1/jobs/{job_id}` returns `{ "status": "queued"|"running"|"completed"|"failed", "created_at", "updated_at", "result" (if completed), "error" (if failed) }`. Optional `GET /v1/jobs/{job_id}/result` for artifact (e.g. zip of output) when status is `completed`.

### 1.2 Webhooks

For async jobs, allow a **callback URL** in the request (e.g. `webhook_url` or `callback_url`). When the job reaches a terminal state (`completed` or `failed`), the server sends a **POST** to that URL with a signed or verifiable payload (e.g. `job_id`, `status`, `result` or `error`, `completed_at`). This avoids polling and fits CI/integrations.

- **Payload:** Include `job_id`, `status`, `result` (link or inline summary), `error` (if failed), and a **signature** (e.g. HMAC of body with shared secret) so the client can verify authenticity.
- **Retries:** Define a small retry policy (e.g. 3 attempts with backoff) and document it; optional `Delivery-Attempt` header in webhook request.

**Recommendation:** Implement webhooks as an **optional** field on `POST /v1/jobs`. Sync API does not need webhooks.

### 1.3 Summary Table

| Feature | Sync API | Async API | Webhooks |
|---------|----------|-----------|----------|
| **Endpoint** | `POST /v1/build` | `POST /v1/jobs`, `GET /v1/jobs/{id}`, `GET /v1/jobs/{id}/result` | Optional on `POST /v1/jobs` |
| **When** | Small runs, scripts | All runs in UI / integrations | When client wants no polling |
| **Priority** | P1 (ship with first API) | P1 | P2 |

---

## 2. UI Scope

### 2.1 Input: Upload vs Link

MVP already supports **GitHub URL** and **local directory** at the CLI. For the UI:

| Input type | Description | Complexity |
|------------|--------------|------------|
| **Link** | User pastes a GitHub repo URL (and optional project name, language). Backend uses same `repo_url` path as CLI. | Low; single text field + options. |
| **Upload** | User uploads a **zip** of their project (or multi-file picker). Backend extracts to a temp dir and runs the same pipeline with `local_dir`. | Medium; file upload, size limits, temp cleanup. |

**Recommendation:** Support **both** in post-MVP UI.

- **Phase 1 (first UI):** Link (GitHub URL) + optional project name and language. Easiest and matches MVP.
- **Phase 2:** Add upload (zip) for private or local-first workflows; enforce max size (e.g. 50 MB) and clear messaging.

### 2.2 Interaction: View-Only vs Edit

| Mode | Description | Scope |
|------|-------------|--------|
| **View-only** | User submits input (link or upload), waits (or gets webhook). UI displays the generated tutorial: index (summary, Mermaid diagram, chapter list) and chapter content. Option to **download** as zip or view in browser. No modification of content. | Smaller; read + download. |
| **Edit** | User can edit summary, chapter titles, or chapter body; reorder chapters; trigger **regenerate** for a single chapter or full run. Requires persisting state, possibly versioning, and more UI surface. | Larger; full CRUD-like experience. |

**Recommendation:** Phase UI by scope.

- **Post-MVP Phase 1 – View-only:** Submit job (link or upload) → progress/status → view result (index + chapters) + download. No edit.
- **Post-MVP Phase 2 – Edit (optional):** Add edit screen: edit summary/chapters, reorder, regenerate one chapter or full tutorial. Depends on product need and API support (e.g. PATCH job result or separate “project” resource).

### 2.3 UI Scope Summary

| Dimension | Phase 1 (first UI) | Phase 2 |
|-----------|--------------------|--------|
| **Input** | Link (GitHub URL) | + Upload (zip) |
| **Interaction** | View-only + download | + Edit (summary/chapters, reorder, regenerate) |

---

## 3. Frontend Technology: Streamlit vs NextJS + Tailwind

### 3.1 Options

| Criteria | Streamlit | NextJS + Tailwind CSS |
|----------|-----------|------------------------|
| **Stack** | Python; same process as backend/flow. | JS/TS frontend; backend = API (e.g. FastAPI/Flask) that runs the existing flow. |
| **Speed to ship** | Fast: minimal frontend code, Python-only. | Slower: separate app, API design, deployment. |
| **Look & control** | Template-like; limited layout/motion. Tends to look generic. | Full control: components, layout, typography, motion, accessibility. |
| **Frontend-design skill fit** | Hard to achieve “distinctive, production-grade” and “bold, intentional aesthetic” — Streamlit’s defaults are uniform. | Aligns with [frontend-design SKILL](.cursor/skills/frontend-design/SKILL.md): intentional aesthetic, typography, color, motion, spatial composition, “purpose-built” feel. |
| **Audience** | Internal tools, demos, data apps. | Product-grade UI, external users, brand. |
| **Auth / scale** | Add via extensions or reverse proxy. | Standard: NextAuth, API routes, serverless. |

### 3.2 Recommendation

- **Choose Streamlit** if the goal is to **ship a working UI quickly** for internal or demo use, and “good enough” UX is acceptable. Same repo, same language as the flow; minimal API surface (e.g. sync only or simple polling).
- **Choose NextJS + Tailwind** if the goal is a **product-grade, memorable UI** and you want to apply the frontend-design skill: intentional aesthetic, distinctive typography and motion, and a non-generic layout. Requires an API (sync + async + optional webhooks) and more upfront work.

**Suggested decision rule:**

- **Internal / demo first** → Streamlit (Phase 1 UI with link + view-only).
- **External / product / “make it memorable”** → NextJS + Tailwind; invest in API (sync + async + webhooks) and view-only UI first, then add upload and edit in a later phase.

### 3.3 If Using NextJS + Tailwind (per frontend-design skill)

- **Design first:** Decide purpose, audience, and one strong aesthetic direction (e.g. editorial, minimal, or utilitarian) before coding.
- **Implementation:** Production-grade components, distinctive typography (avoid Inter/Roboto/Arial), cohesive color system (e.g. CSS variables), intentional motion (page load, section reveal).
- **Complexity:** Match implementation to the chosen direction (e.g. minimal = restraint and spacing; maximal = richer visuals and animation).

---

## 4. Implementation Order (Post-MVP)

1. **API (sync):** Implement `POST /v1/build` with same inputs as CLI; return result or 202 + job_id when over max duration.  
2. **API (async):** Implement `POST /v1/jobs`, `GET /v1/jobs/{id}`, `GET /v1/jobs/{id}/result`; job store and status.  
3. **UI (Phase 1):** Choose Streamlit **or** NextJS + Tailwind; implement link-only, view-only, and download (call sync or async + poll).  
4. **Webhooks:** Add optional `webhook_url` to async job creation; POST on completion/failure with signed payload.  
5. **UI – Upload:** Add zip upload path; backend runs pipeline with temp `local_dir`.  
6. **UI – Edit (Phase 2):** If needed, add edit flow (summary/chapters, reorder, regenerate) and supporting API.

---

## 5. Open Points

- Exact **max duration** for sync and **job retention** for async (e.g. 24 h then delete).
- **Auth:** API keys, OAuth, or SSO for API and UI (out of scope for this plan; define when implementing).
- **Rate limits** per API key or IP for `POST /v1/build` and `POST /v1/jobs`.

---

## 6. References

- [docs/design.md](design.md) — Flow, nodes, shared store.
- [.cursor/plans/prd_codebase_knowledge_builder_2dfde023.plan.md](../.cursor/plans/prd_codebase_knowledge_builder_2dfde023.plan.md) — PRD; post-MVP called out as API/UI.
- [.cursor/skills/frontend-design/SKILL.md](../.cursor/skills/frontend-design/SKILL.md) — Frontend design principles (aesthetic, typography, motion, differentiation).
