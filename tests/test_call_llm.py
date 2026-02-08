"""Unit tests for call_llm."""

import os
from unittest.mock import MagicMock, patch

import pytest

from utils.call_llm import call_llm


def test_call_llm_returns_str():
    """call_llm returns a non-empty string when API is mocked."""
    mock_response = MagicMock()
    mock_response.text = "Hello from model"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
        with patch("google.genai.Client", return_value=mock_client):
            result = call_llm("Hi")
    assert result == "Hello from model"
    assert isinstance(result, str)


def test_call_llm_calls_provider_with_prompt():
    """call_llm passes prompt to the model."""
    mock_response = MagicMock()
    mock_response.text = "ok"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch.dict(os.environ, {"GEMINI_API_KEY": "key"}, clear=False):
        with patch("google.genai.Client", return_value=mock_client):
            call_llm("What is 2+2?")
    mock_client.models.generate_content.assert_called_once()
    call_args = mock_client.models.generate_content.call_args
    # generate_content(model=..., contents=[prompt])
    assert call_args[1]["contents"] == ["What is 2+2?"]


def test_call_llm_uses_env_api_key():
    """call_llm uses GEMINI_API_KEY from environment."""
    mock_response = MagicMock()
    mock_response.text = "x"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch.dict(os.environ, {"GEMINI_API_KEY": "my-secret-key"}, clear=False):
        with patch("google.genai.Client", return_value=mock_client) as mock_client_cls:
            call_llm("Hi")
    mock_client_cls.assert_called_once_with(api_key="my-secret-key")


def test_call_llm_raises_when_api_key_missing():
    """call_llm raises ValueError when GEMINI_API_KEY is not set."""
    env_backup = os.environ.get("GEMINI_API_KEY")
    try:
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            call_llm("Hi")
    finally:
        if env_backup is not None:
            os.environ["GEMINI_API_KEY"] = env_backup


def test_call_llm_raises_on_empty_response():
    """call_llm raises when model returns empty response."""
    mock_response = MagicMock()
    mock_response.text = None
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}, clear=False):
        with patch("google.genai.Client", return_value=mock_client):
            with pytest.raises(ValueError, match="Empty response"):
                call_llm("Hi")


def test_call_llm_gemini_retries_on_429():
    """On 429 RESOURCE_EXHAUSTED, call_llm retries after delay and succeeds on second attempt."""
    mock_response = MagicMock()
    mock_response.text = "Success after retry"
    mock_client = MagicMock()
    # First call: 429-like exception; second: success
    error_429 = Exception("429 RESOURCE_EXHAUSTED. ... Please retry in 1s.")
    mock_client.models.generate_content.side_effect = [error_429, mock_response]
    with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "LLM_RATE_LIMIT_MAX_RETRIES": "3"}, clear=False):
        with patch("google.genai.Client", return_value=mock_client):
            with patch("utils.call_llm.time.sleep"):  # avoid real sleep
                result = call_llm("Hi")
    assert result == "Success after retry"
    assert mock_client.models.generate_content.call_count == 2


def test_parse_retry_delay_prefers_retry_delay_parameter():
    """_parse_retry_delay_seconds prefers API retryDelay (e.g. '57s') over 'Please retry in Xs'."""
    from utils.call_llm import _parse_retry_delay_seconds

    msg = "429 ... 'retryDelay': '57s' ... Please retry in 22.5s."
    assert _parse_retry_delay_seconds(None, msg) == 57
    msg_no_retry_delay = "429 ... Please retry in 36.767s."
    assert _parse_retry_delay_seconds(None, msg_no_retry_delay) == 37


# --- Gemini AI Platform (REST) backend ---


def test_call_llm_gemini_aiplatform_returns_text():
    """When LLM_PROVIDER=gemini_aiplatform, call_llm POSTs to AI Platform and returns text from JSON body."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    body = '{"candidates":[{"content":{"parts":[{"text":"AI works by learning patterns."}],"role":"model"}}]}'
    mock_response.iter_content.return_value = iter([body.encode("utf-8")])
    with patch.dict(os.environ, {"LLM_PROVIDER": "gemini_aiplatform", "GEMINI_API_KEY": "test-key"}, clear=False):
        with patch("utils.call_llm.requests.post", return_value=mock_response):
            result = call_llm("Explain how AI works in a few words")
    assert result == "AI works by learning patterns."


def test_call_llm_gemini_aiplatform_parses_array_response():
    """gemini_aiplatform accepts response as array of objects (e.g. [{ candidates ... }])."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    body = '[{"candidates":[{"content":{"parts":[{"text":"Short answer."}],"role":"model"}}]}]'
    mock_response.iter_content.return_value = iter([body.encode("utf-8")])
    with patch.dict(os.environ, {"LLM_PROVIDER": "gemini_aiplatform", "GEMINI_API_KEY": "k"}, clear=False):
        with patch("utils.call_llm.requests.post", return_value=mock_response):
            result = call_llm("Hi")
    assert result == "Short answer."


def test_call_llm_gemini_aiplatform_calls_correct_url_and_body():
    """gemini_aiplatform POSTs to streamGenerateContent URL with model in path and contents in body."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = iter(
        [b'{"candidates":[{"content":{"parts":[{"text":"ok"}],"role":"model"}}]}']
    )
    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "gemini_aiplatform", "GEMINI_API_KEY": "mykey", "GEMINI_MODEL": "gemini-3-pro-preview"},
        clear=False,
    ):
        with patch("utils.call_llm.requests.post", return_value=mock_response) as mock_post:
            call_llm("Explain how AI works in a few words")
    mock_post.assert_called_once()
    call_kw = mock_post.call_args[1]
    url = mock_post.call_args[0][0]
    assert "aiplatform.googleapis.com" in url
    assert "streamGenerateContent" in url
    assert "publishers/google/models/gemini-3-pro-preview" in url
    assert "key=mykey" in url
    assert call_kw["json"] == {
        "contents": [{"role": "user", "parts": [{"text": "Explain how AI works in a few words"}]}]
    }


def test_call_llm_gemini_aiplatform_truncates_when_max_input_chars_set():
    """When LLM_MAX_INPUT_CHARS is set, prompt is truncated to that length."""
    long_prompt = "x" * 500
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = iter(
        [b'{"candidates":[{"content":{"parts":[{"text":"ok"}],"role":"model"}}]}']
    )
    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "gemini_aiplatform",
            "GEMINI_API_KEY": "k",
            "LLM_MAX_INPUT_CHARS": "100",
        },
        clear=False,
    ):
        with patch("utils.call_llm.requests.post", return_value=mock_response) as mock_post:
            call_llm(long_prompt)
    payload = mock_post.call_args[1]["json"]
    sent_text = payload["contents"][0]["parts"][0]["text"]
    assert len(sent_text) == 100
    assert sent_text == "x" * 100


def test_call_llm_gemini_aiplatform_raises_when_api_key_missing():
    """gemini_aiplatform raises ValueError when GEMINI_API_KEY is not set."""
    env_backup = os.environ.get("GEMINI_API_KEY")
    try:
        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini_aiplatform"}, clear=False):
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                call_llm("Hi")
    finally:
        if env_backup is not None:
            os.environ["GEMINI_API_KEY"] = env_backup


# --- Cursor backend ---


def test_call_llm_cursor_backend_returns_stdout():
    """When LLM_PROVIDER=cursor, call_llm uses subprocess and returns stdout."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Cursor reply\n"
    mock_result.stderr = ""
    with patch.dict(os.environ, {"LLM_PROVIDER": "cursor"}, clear=False):
        with patch("utils.call_llm.subprocess.run", return_value=mock_result):
            result = call_llm("Hello")
    assert result == "Cursor reply"
    assert isinstance(result, str)


def test_call_llm_cursor_passes_prompt_via_stdin():
    """Cursor backend passes prompt to subprocess via input=prompt."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "ok"
    mock_result.stderr = ""
    with patch.dict(os.environ, {"LLM_PROVIDER": "cursor"}, clear=False):
        with patch("utils.call_llm.subprocess.run", return_value=mock_result) as mock_run:
            call_llm("What is 2+2?")
    mock_run.assert_called_once()
    call_kw = mock_run.call_args[1]
    assert call_kw.get("input") == "What is 2+2?"


def test_call_llm_cursor_invokes_agent_with_output_format_text():
    """Cursor backend runs cursor agent --output-format text."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "x"
    mock_result.stderr = ""
    with patch.dict(os.environ, {"LLM_PROVIDER": "cursor"}, clear=False):
        with patch("utils.call_llm.subprocess.run", return_value=mock_result) as mock_run:
            call_llm("Hi")
    args = mock_run.call_args[0][0]
    assert "cursor" in args
    assert "agent" in args
    assert "--output-format" in args
    assert "text" in args


def test_call_llm_cursor_raises_on_nonzero_exit():
    """Cursor backend raises RuntimeError when subprocess exits non-zero."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "error"
    with patch.dict(os.environ, {"LLM_PROVIDER": "cursor"}, clear=False):
        with patch("utils.call_llm.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="exited with code 1"):
                call_llm("Hi")


def test_call_llm_cursor_raises_on_empty_stdout():
    """Cursor backend raises when stdout is empty."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch.dict(os.environ, {"LLM_PROVIDER": "cursor"}, clear=False):
        with patch("utils.call_llm.subprocess.run", return_value=mock_result):
            with pytest.raises(ValueError, match="Empty response"):
                call_llm("Hi")
