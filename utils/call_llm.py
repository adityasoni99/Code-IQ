"""
Call LLM with a prompt and return response text.

Backend is selected via LLM_PROVIDER: gemini (default), gemini_aiplatform, or cursor.
- gemini: google-genai client; GEMINI_API_KEY, GEMINI_MODEL.
- gemini_aiplatform: REST to aiplatform.googleapis.com (API key in URL); same env vars.
- cursor: Cursor CLI via subprocess; CURSOR_MODEL, CURSOR_TIMEOUT, CURSOR_API_KEY.
Used by IdentifyAbstractions, AnalyzeRelationships, OrderChapters, WriteChapters.

On Gemini 429 (RESOURCE_EXHAUSTED / quota), we retry with backoff using the API's
retryDelay (RetryInfo) or 'Please retry in Xs', up to LLM_RATE_LIMIT_MAX_RETRIES (default 3).
We distinguish RPM (requests-per-minute) vs RPD (requests-per-day) for clearer logging.
"""

import json
import logging
import os
import re
import subprocess
import time
from typing import Optional

import requests

logger = logging.getLogger("codebase_knowledge_builder")


def call_llm(prompt: str, use_cache: bool = True) -> str:
    """
    Send prompt to the configured LLM and return response text.

    Args:
        prompt: User prompt string.
        use_cache: If True, caller may use cached result (not implemented here; for API compatibility).

    Returns:
        Response text from the model.

    Environment:
        LLM_PROVIDER: "gemini" (default), "gemini_aiplatform", or "cursor".
        Gemini: GEMINI_API_KEY (required), GEMINI_MODEL (optional, default gemini-2.0-flash).
        gemini_aiplatform: same env; calls aiplatform.googleapis.com with key in URL.
        Cursor: CURSOR_MODEL, CURSOR_TIMEOUT (seconds), CURSOR_API_KEY (for headless).
    """
    provider = (os.environ.get("LLM_PROVIDER", "gemini") or "gemini").strip().lower()
    if provider == "cursor":
        return _call_llm_cursor(prompt)
    if provider == "gemini_aiplatform":
        return _call_llm_gemini_aiplatform(prompt)
    return _call_llm_gemini(prompt)


def _parse_retry_delay_from_exception(exc: BaseException) -> Optional[int]:
    """
    Extract retry delay from Gemini error structure (RetryInfo in details).
    Returns seconds or None if not found.
    """
    try:
        # ClientError may have response_json (dict with 'error' -> 'details')
        data = None
        if hasattr(exc, "response_json") and isinstance(getattr(exc, "response_json"), dict):
            data = getattr(exc, "response_json")
        if not data and hasattr(exc, "__dict__"):
            data = getattr(exc, "__dict__", {})
        if not isinstance(data, dict):
            return None
        if "error" in data:
            data = data["error"]
        details = data.get("details", []) if isinstance(data, dict) else []
        for detail in details:
            if isinstance(detail, dict) and detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                retry_delay_str = detail.get("retryDelay", "")
                if retry_delay_str:
                    match = re.search(r"([\d.]+)\s*s?", str(retry_delay_str))
                    if match:
                        return max(1, int(float(match.group(1))))
        return None
    except Exception:
        return None


def _parse_retry_delay_seconds(exc: Optional[BaseException], error_message: str) -> int:
    """
    Parse retry delay from Gemini 429 error.
    Prefer exception structure (RetryInfo.retryDelay); else regex on message; else 60.
    """
    if exc is not None:
        sec = _parse_retry_delay_from_exception(exc)
        if sec is not None:
            return sec
    # API RetryInfo in str: 'retryDelay': '57s' or "retryDelay": "57s"
    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s", error_message, re.IGNORECASE)
    if match:
        return max(1, int(match.group(1)))
    # Fallback: "Please retry in 57.282934807s"
    match = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", error_message, re.IGNORECASE)
    if match:
        return max(1, int(float(match.group(1))) + 1)
    return 60


def _quota_type(error_message: str) -> str:
    """Return 'RPM', 'RPD', or '' for 429 quota type (for logging)."""
    if "PerDay" in error_message or "GenerateRequestsPerDay" in error_message:
        return "RPD"
    if "PerMinute" in error_message or "GenerateRequestsPerMinutePerProjectPerModel" in error_message:
        return "RPM"
    return ""


def _is_rpm_quota_exhausted(error_message: str) -> bool:
    """True if the 429 is due to requests-per-minute (RPM) quota."""
    return _quota_type(error_message) == "RPM"


def _call_llm_gemini(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    max_retries = int(os.environ.get("LLM_RATE_LIMIT_MAX_RETRIES", "3") or "3")
    max_retries = max(1, min(max_retries, 10))

    from google import genai

    client = genai.Client(api_key=api_key)
    last_exc = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=model, contents=[prompt])
            if not response or not response.text:
                raise ValueError("Empty response from LLM")
            return response.text
        except Exception as e:
            last_exc = e
            msg = str(e)
            is_429 = "429" in msg or "RESOURCE_EXHAUSTED" in msg or getattr(e, "status_code", None) == 429
            if is_429 and attempt < max_retries - 1:
                delay = _parse_retry_delay_seconds(e, msg)
                qtype = _quota_type(msg)
                if qtype == "RPM":
                    quota_note = " (RPM quota exhausted; wait for next minute)"
                elif qtype == "RPD":
                    quota_note = " (RPD daily quota exhausted)"
                else:
                    quota_note = ""
                logger.warning(
                    "Gemini 429 (quota/rate limit)%s; retrying in %ds (attempt %d/%d): %s",
                    quota_note,
                    delay,
                    attempt + 1,
                    max_retries,
                    msg[:200],
                )
                time.sleep(delay)
            else:
                raise
    if last_exc is not None:
        raise last_exc
    raise ValueError("Empty response from LLM")


def _parse_one_json_object(s: str) -> tuple[Optional[dict], int]:
    """
    Parse a single JSON object from the start of s. Returns (dict, chars_consumed) or (None, 0).
    Handles nested braces; does not enter string literals.
    """
    s = s.lstrip()
    if not s or s[0] != "{":
        return None, 0
    depth = 0
    in_string = False
    escape = False
    i = 0
    while i < len(s):
        c = s[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[: i + 1])
                    return (obj, i + 1) if isinstance(obj, dict) else (None, 0)
                except json.JSONDecodeError:
                    return None, 0
        i += 1
    return None, 0


def _parse_aiplatform_body(body: str) -> list:
    """
    Parse streamGenerateContent response: one JSON object, JSON array, or concatenated objects.
    Returns a list of dicts (one per top-level object).
    """
    body = (body or "").strip()
    if not body:
        return []
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        pass
    else:
        return parsed if isinstance(parsed, list) else [parsed]
    # Concatenated stream chunks: parse object by object
    items = []
    rest = body
    while rest:
        obj, consumed = _parse_one_json_object(rest)
        if consumed == 0:
            break
        if obj is not None:
            items.append(obj)
        rest = rest[consumed:].lstrip()
    if items:
        return items
    try:
        wrapped = "[" + body.replace("}{", "},{") + "]"
        parsed = json.loads(wrapped)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError as e:
        logger.error("Gemini AI Platform invalid JSON (len=%s): %s ...", len(body), body[:300])
        raise ValueError("Empty response from LLM (invalid JSON)") from e


def _extract_aiplatform_text(items: list) -> tuple[str, dict]:
    """
    Extract text from AI Platform response items. Returns (text, info).
    info includes finishReasons and promptFeedback when present.
    """
    chunks: list[str] = []
    info: dict = {
        "candidates": 0,
        "finishReasons": [],
        "promptFeedback": None,
        "blocked": False,
    }
    for data in items:
        if not isinstance(data, dict):
            continue
        if "promptFeedback" in data:
            info["promptFeedback"] = data.get("promptFeedback")
            if isinstance(info["promptFeedback"], dict):
                if info["promptFeedback"].get("blockReason"):
                    info["blocked"] = True
        candidates = data.get("candidates") or []
        if isinstance(candidates, list):
            info["candidates"] += len(candidates)
        for c in candidates:
            if not isinstance(c, dict):
                continue
            finish_reason = c.get("finishReason")
            if isinstance(finish_reason, str) and finish_reason:
                info["finishReasons"].append(finish_reason)
                if finish_reason.upper() in {"SAFETY", "BLOCKLIST", "RECITATION"}:
                    info["blocked"] = True
            content = c.get("content")
            if isinstance(content, dict):
                parts = content.get("parts") or []
                for part in parts:
                    if isinstance(part, str):
                        if part:
                            chunks.append(part)
                        continue
                    if isinstance(part, dict):
                        text = part.get("text")
                        if isinstance(text, str) and text:
                            chunks.append(text)
            elif isinstance(content, str) and content:
                chunks.append(content)
            alt_text = c.get("text")
            if isinstance(alt_text, str) and alt_text:
                chunks.append(alt_text)
    return "".join(chunks).strip(), info


def _call_llm_gemini_aiplatform(prompt: str) -> str:
    """
    Call Gemini via AI Platform REST (express mode). Uses streamGenerateContent:
    POST https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:streamGenerateContent?key={key}
    with body {"contents": [{"role": "user", "parts": [{"text": prompt}}]}.
    Consumes the NDJSON stream and concatenates candidate text.
    Uses GEMINI_API_KEY, GEMINI_MODEL; optional GEMINI_AIPLATFORM_BASE_URL.
    If you get 400 INVALID_ARGUMENT, try GEMINI_MODEL=gemini-2.5-flash or gemini-2.0-flash
    (express mode model list may differ). Large prompts are truncated per LLM_MAX_INPUT_CHARS.
    For manual curl, use -d @body.json with a file to avoid "Invalid JSON payload" from shell quoting.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    base = (os.environ.get("GEMINI_AIPLATFORM_BASE_URL", "https://aiplatform.googleapis.com") or "https://aiplatform.googleapis.com").rstrip("/")
    # Ensure prompt is a clean string (APIs can reject null bytes or non-UTF-8)
    text = str(prompt) if prompt is not None else ""
    if "\x00" in text:
        text = text.replace("\x00", "")
    # Truncate if over model limit (default 1M chars ~ 250k tokens; avoids 400 on large codebases)
    max_chars_raw = os.environ.get("LLM_MAX_INPUT_CHARS", "1000000") or "1000000"
    max_chars = max(0, min(int(max_chars_raw), 2_000_000))
    if max_chars > 0 and len(text) > max_chars:
        logger.warning(
            "Truncating prompt from %s to %s chars (set LLM_MAX_INPUT_CHARS=0 to disable)",
            len(text),
            max_chars,
        )
        text = text[:max_chars]
    url = f"{base}/v1/publishers/google/models/{model}:streamGenerateContent?key={api_key}"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": text}]}
        ],
        # Disable function/tool calling to avoid MALFORMED_FUNCTION_CALL with long prompts.
        "toolConfig": {"functionCallingConfig": {"mode": "NONE"}},
    }
    max_retries = int(os.environ.get("LLM_RATE_LIMIT_MAX_RETRIES", "3") or "3")
    max_retries = max(1, min(max_retries, 10))
    last_exc = None
    for attempt in range(max_retries):
        try:
            r = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120,
                stream=True,
            )
            if r.status_code == 429:
                msg = r.text
                try:
                    err = r.json()
                    msg = json.dumps(err) if isinstance(err, dict) else r.text
                except Exception:
                    pass
                if attempt < max_retries - 1:
                    delay = _parse_retry_delay_seconds(None, msg)
                    qtype = _quota_type(msg)
                    quota_note = " (RPM quota exhausted; wait for next minute)" if qtype == "RPM" else (" (RPD daily quota exhausted)" if qtype == "RPD" else "")
                    logger.warning(
                        "Gemini 429 (quota/rate limit)%s; retrying in %ds (attempt %d/%d): %s",
                        quota_note, delay, attempt + 1, max_retries, msg[:200],
                    )
                    time.sleep(delay)
                    continue
                r.raise_for_status()
            if r.status_code != 200:
                err_body = r.text
                try:
                    parsed = r.json()
                    err_body = json.dumps(parsed) if isinstance(parsed, (dict, list)) else r.text
                except Exception:
                    pass
                logger.error(
                    "Gemini AI Platform %s: %s (model=%s, prompt_len=%s)",
                    r.status_code,
                    err_body[:500],
                    model,
                    len(text),
                )
                r.raise_for_status()
            # streamGenerateContent returns a stream of JSON objects; consume all chunks.
            buf = b""
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    buf += chunk
            body = buf.decode("utf-8", errors="replace")
            items = _parse_aiplatform_body(body)
            result, info = _extract_aiplatform_text(items)
            if not result:
                summary = []
                for i, data in enumerate(items):
                    if isinstance(data, dict):
                        keys = list(data.keys())[:10]
                        cands = data.get("candidates") or []
                        summary.append(f"item{i}=keys{keys} candidates={len(cands)}")
                logger.warning(
                    "Gemini AI Platform empty text from stream (body_len=%s, candidates=%s, finishReasons=%s, blocked=%s): %s",
                    len(body),
                    info.get("candidates"),
                    info.get("finishReasons"),
                    info.get("blocked"),
                    "; ".join(summary) if summary else body[:400],
                )
                # Fallback to non-stream endpoint to handle responses that only finalize on generateContent.
                fallback_url = f"{base}/v1/publishers/google/models/{model}:generateContent?key={api_key}"
                r2 = requests.post(
                    fallback_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=120,
                )
                if r2.status_code != 200:
                    err_body = r2.text
                    try:
                        parsed = r2.json()
                        err_body = json.dumps(parsed) if isinstance(parsed, (dict, list)) else r2.text
                    except Exception:
                        pass
                    logger.error(
                        "Gemini AI Platform generateContent %s: %s (model=%s, prompt_len=%s)",
                        r2.status_code,
                        err_body[:500],
                        model,
                        len(text),
                    )
                    r2.raise_for_status()
                body2 = (r2.text or "").strip()
                items2 = _parse_aiplatform_body(body2)
                result2, info2 = _extract_aiplatform_text(items2)
                if result2:
                    return result2
                logger.error(
                    "Gemini AI Platform empty text after generateContent fallback (body_len=%s, candidates=%s, finishReasons=%s, blocked=%s)",
                    len(body2),
                    info2.get("candidates"),
                    info2.get("finishReasons"),
                    info2.get("blocked"),
                )
                raise ValueError("Empty response from LLM (no text in stream)")
            return result
        except requests.RequestException as e:
            last_exc = e
            msg = str(e)
            is_429 = getattr(e, "response", None) and getattr(e.response, "status_code", None) == 429
            if is_429 and attempt < max_retries - 1:
                resp = getattr(e, "response", None)
                err_text = getattr(resp, "text", "") if resp else msg
                try:
                    err_body = resp.json() if resp else {}
                    err_text = json.dumps(err_body) if isinstance(err_body, dict) else (resp.text if resp else msg)
                except Exception:
                    pass
                delay = _parse_retry_delay_seconds(last_exc, err_text)
                qtype = _quota_type(err_text)
                quota_note = " (RPM quota exhausted; wait for next minute)" if qtype == "RPM" else (" (RPD daily quota exhausted)" if qtype == "RPD" else "")
                logger.warning(
                    "Gemini 429 (quota/rate limit)%s; retrying in %ds (attempt %d/%d): %s",
                    quota_note, delay, attempt + 1, max_retries, msg[:200],
                )
                time.sleep(delay)
            else:
                raise
    if last_exc is not None:
        raise last_exc
    raise ValueError("Empty response from LLM")


def _call_llm_cursor(prompt: str) -> str:
    """Invoke Cursor CLI agent via subprocess; prompt via stdin, --output-format text."""
    timeout_sec = int(os.environ.get("CURSOR_TIMEOUT", "120") or "120")
    env = dict(os.environ)
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if api_key:
        env["CURSOR_API_KEY"] = api_key
    model = (os.environ.get("CURSOR_MODEL", "") or "").strip()
    cmd = ["cursor", "agent", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Cursor agent exited with code {result.returncode}: {result.stderr or result.stdout or 'no output'}"
        )
    out = (result.stdout or "").strip()
    if not out:
        raise ValueError("Empty response from Cursor LLM")
    return out
