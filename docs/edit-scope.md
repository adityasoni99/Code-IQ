# Edit scope (UI Phase 2, optional)

## Editable fields

- **Summary** — Project summary text (from index).
- **Chapter title** — Per-chapter title (from abstraction name).
- **Chapter body** — Markdown content of each chapter.

## Actions

- **Save** — Persist edits via `PATCH /v1/projects/{id}`.
- **Reorder chapters** — Drag-and-drop order; save updates project.
- **Regenerate** — `POST /v1/projects/{id}/regenerate` with `scope: "full"` (or later `"chapter"` + `chapter_index`). Enqueues a new job with the project’s source inputs; returns `job_id`. When the job completes, the UI can refresh or replace the project result.

## API choice

- **Project resource** — Stored result (summary, chapters array). Created from a completed job via `POST /v1/projects/from-job/{job_id}`.
- **PATCH /v1/projects/{id}** — Update summary and/or chapters.
- **POST /v1/projects/{id}/regenerate** — Body `{ "scope": "full" }` (and later `"chapter", "chapter_index"`). Uses stored source inputs to create a new job; returns `job_id`. No persistence of new result into project in this minimal version (UI polls job and shows result).

## Out of scope for minimal 6.0

- Regenerate single chapter (pipeline runs full flow; could replace one chapter in project after run).
- Version history of edits.
