"""
Streamlit UI for Code-IQ (post-MVP Phase 1).

Uses async API: POST /v1/jobs (link) or POST /v1/jobs/upload (zip), poll GET /v1/jobs/{id}, download via GET /v1/jobs/{id}/result.
Run API first: uvicorn api.app:app --reload
Then: streamlit run ui/app.py
"""

import os
import time

import requests
import streamlit as st

# API base URL (e.g. http://localhost:8000)
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
MAX_UPLOAD_MB = 50


def _render_edit_screen() -> None:
    """Edit project: summary, chapters; Save (PATCH); Regenerate (POST regenerate)."""
    project_id = st.session_state["edit_project_id"]
    st.subheader("Edit project")
    st.write(f"Project ID: `{project_id}`")
    summary = st.text_area("Summary", value=st.session_state.get("edit_summary", ""), height=120, key="edit_summary")
    chapters = st.session_state.get("edit_chapters", [])
    for i, ch in enumerate(chapters):
        with st.expander(ch.get("name", f"Chapter {i+1}"), expanded=(i == 0)):
            st.text_area("Content", value=ch.get("content", ""), height=150, key=f"ch_{i}")
    if st.button("Save", key="save_edit"):
        # Build chapters from current widget values
        chapters_to_save = []
        for i, ch in enumerate(chapters):
            content = st.session_state.get(f"ch_{i}", ch.get("content", ""))
            chapters_to_save.append({**ch, "content": content})
        try:
            r = requests.patch(
                f"{API_BASE}/v1/projects/{project_id}",
                json={"summary": summary, "chapters": chapters_to_save},
                timeout=10,
            )
            r.raise_for_status()
            st.success("Saved.")
            st.session_state["edit_summary"] = summary
            st.session_state["edit_chapters"] = chapters_to_save
        except requests.RequestException as e:
            st.error(f"Save failed: {e}")
    if st.button("Regenerate (full)", key="regen"):
        try:
            r = requests.post(f"{API_BASE}/v1/projects/{project_id}/regenerate", json={"scope": "full"}, timeout=10)
            r.raise_for_status()
            data = r.json()
            st.success(f"Job {data['job_id']} queued. Polling…")
            st.session_state.pop("edit_project_id", None)
            st.session_state.pop("edit_summary", None)
            st.session_state.pop("edit_chapters", None)
            _poll_and_show_result(data["job_id"])
        except requests.RequestException as e:
            st.error(f"Regenerate failed: {e}")
    if st.button("Back to home", key="back_home"):
        st.session_state.pop("edit_project_id", None)
        st.session_state.pop("edit_summary", None)
        st.session_state.pop("edit_chapters", None)
        st.rerun()


def _poll_and_show_result(job_id: str) -> None:
    """Poll job until completed/failed; show result and download button."""
    status_placeholder = st.empty()
    progress_placeholder = st.empty()
    max_polls = 600
    for i in range(max_polls):
        try:
            r2 = requests.get(f"{API_BASE}/v1/jobs/{job_id}", timeout=5)
            r2.raise_for_status()
        except requests.RequestException as e:
            status_placeholder.error(f"Poll failed: {e}")
            return
        job = r2.json()
        status = job.get("status", "unknown")
        status_placeholder.status(f"Status: **{status}**")
        progress_placeholder.progress(min((i + 1) / max_polls, 1.0), text=f"Poll {i + 1}")

        if status == "completed":
            status_placeholder.success("Completed!")
            progress_placeholder.empty()
            result = job.get("result") or {}
            summary = result.get("summary") or "(no summary)"
            final_dir = result.get("final_output_dir") or ""
            st.subheader("Result")
            st.markdown("**Summary**")
            st.markdown(summary)
            st.markdown("**Output directory** (server path): " + (final_dir or "—"))
            download_url = f"{API_BASE}/v1/jobs/{job_id}/result"
            st.download_button(
                "Download tutorial (zip)",
                data=requests.get(download_url, timeout=60).content,
                file_name="tutorial.zip",
                mime="application/zip",
                key=f"download_zip_{job_id}",
            )
            if st.button("Edit (create project)", key=f"edit_{job_id}"):
                try:
                    rp = requests.post(f"{API_BASE}/v1/projects/from-job/{job_id}", timeout=10)
                    rp.raise_for_status()
                    proj = rp.json()
                    st.session_state["edit_project_id"] = proj["project_id"]
                    st.session_state["edit_summary"] = proj.get("summary", "")
                    st.session_state["edit_chapters"] = proj.get("chapters", [])
                    st.rerun()
                except requests.RequestException as e:
                    st.error(f"Failed to create project: {e}")
            return
        if status == "failed":
            status_placeholder.error("Job failed")
            progress_placeholder.empty()
            st.error("Error: " + (job.get("error") or "Unknown"))
            return
        time.sleep(1)
    status_placeholder.warning("Timed out waiting for job. Check the API or try again.")


def main():
    st.set_page_config(page_title="Code-IQ", page_icon="📚", layout="wide")
    st.title("Code-IQ")
    st.caption("Generate a structured tutorial from a GitHub repo (link) or upload a zip. Uses async API.")

    # Edit screen (if project loaded)
    if st.session_state.get("edit_project_id"):
        _render_edit_screen()
        return

    mode = st.radio("Input", ["Link (GitHub URL)", "Upload (zip)"], horizontal=True, key="mode")

    if mode == "Link (GitHub URL)":
        repo_url = st.text_input(
            "GitHub repo URL (required)",
            placeholder="https://github.com/owner/repo",
            key="repo_url",
        )
        project_name = st.text_input("Project name (optional)", placeholder="my-project", key="project_name")
        language = st.selectbox(
            "Language",
            ["english", "spanish", "french", "german"],
            index=0,
            key="language",
        )
        if st.button("Generate tutorial", type="primary", key="btn_link"):
            if not repo_url or not repo_url.strip():
                st.error("Please enter a GitHub repo URL.")
                return
            payload = {
                "repo_url": repo_url.strip(),
                "project_name": project_name.strip() or None,
                "language": language,
            }
            try:
                r = requests.post(f"{API_BASE}/v1/jobs", json=payload, timeout=10)
                r.raise_for_status()
            except requests.RequestException as e:
                st.error(f"Failed to create job: {e}")
                if hasattr(e, "response") and e.response is not None and hasattr(e.response, "text"):
                    st.code(e.response.text[:500])
                return
            data = r.json()
            job_id = data["job_id"]
            st.success(f"Job created: `{job_id}`. Polling for completion…")
            _poll_and_show_result(job_id)

    else:
        st.markdown(f"Upload a **zip** of your project (max **{MAX_UPLOAD_MB} MB**).")
        uploaded = st.file_uploader("Zip file", type=["zip"], key="upload_zip")
        project_name = st.text_input("Project name (optional)", placeholder="my-project", key="project_name_upload")
        language = st.selectbox(
            "Language",
            ["english", "spanish", "french", "german"],
            index=0,
            key="language_upload",
        )
        if st.button("Generate tutorial", type="primary", key="btn_upload"):
            if not uploaded:
                st.error("Please upload a zip file.")
                return
            if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"File too large. Max size is {MAX_UPLOAD_MB} MB.")
                return
            try:
                r = requests.post(
                    f"{API_BASE}/v1/jobs/upload",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/zip")},
                    data={
                        "project_name": project_name.strip() if project_name else "",
                        "language": language,
                    },
                    timeout=30,
                )
                r.raise_for_status()
            except requests.RequestException as e:
                st.error(f"Failed to create job: {e}")
                if hasattr(e, "response") and e.response is not None and hasattr(e.response, "text"):
                    st.code(e.response.text[:500])
                return
            data = r.json()
            job_id = data["job_id"]
            st.success(f"Job created: `{job_id}`. Polling for completion…")
            _poll_and_show_result(job_id)


if __name__ == "__main__":
    main()
