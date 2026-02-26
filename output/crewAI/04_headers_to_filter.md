# Chapter 4: HEADERS_TO_FILTER

Welcome to Chapter 4!

In the previous chapter, [vcr_cassette_dir](03_vcr_cassette_dir.md), we organized our file system so that every test has a specific place to store its recordings (cassettes).

Now we have a dedicated folder for our files, but we have a major security problem. When we record a conversation with an AI model (like GPT-4), the recording includes **everything**—including your private passwords and API keys.

## The Motivation: Why do we need this?

**The Use Case:**
Imagine you write a test that sends a request to OpenAI. To make this work, your computer sends your secret API key in the header of the message:

`Authorization: Bearer sk-real-secret-key-12345`

**The Disaster:**
1.  VCR records this request and saves it to a text file: `cassette.yaml`.
2.  You push your code (and the cassette file) to GitHub.
3.  A hacker scans GitHub, finds your key inside `cassette.yaml`, and uses your credit card to generate millions of words.

**The Solution:**
We need a "Censor" or a "Redactor." Before any text is written to a file, we need to find the secrets and scrub them out with a black marker.

We want the saved file to look like this:
`Authorization: AUTHORIZATION-XXX`

The `HEADERS_TO_FILTER` concept is simply the **list of words** that the Censor needs to look for.

## What is `HEADERS_TO_FILTER`?

It is a simple Python **dictionary**.
*   **Keys (The Target):** The names of the headers we want to hide (e.g., `authorization`, `api-key`).
*   **Values (The Replacement):** The fake text we want to write instead (e.g., `AUTHORIZATION-XXX`).

## How It Works: The "Find and Replace" List

Think of this as a set of instructions you give to a security guard. "If you see a badge that says 'Authorization', put a sticker over the ID number that says 'XXX'."

```mermaid
sequenceDiagram
    participant Request as Real Request
    participant List as HEADERS_TO_FILTER
    participant Recorder as VCR Tape

    Request->>List: "I have an 'authorization' header."
    List->>List: Check List... Found match!
    List->>List: Get replacement: "AUTHORIZATION-XXX"
    List->>Recorder: Write "AUTHORIZATION-XXX" to file
```

## Under the Hood: The Code

This dictionary is defined in `conftest.py`. It is quite long because CrewAI supports many different AI providers (OpenAI, Anthropic, Google, AWS, Azure), and they all name their keys differently.

We will break the code down into small categories to make it easy to read.

### Part 1: Standard Web Security

These are standard headers used by almost all websites for login and security.

```python
HEADERS_TO_FILTER = {
    "authorization": "AUTHORIZATION-XXX",
    "cookie": "COOKIE-XXX",
    "set-cookie": "SET-COOKIE-XXX",
    "x-api-key": "X-API-KEY-XXX",
    # ... logic continues ...
```

*   **`authorization`**: Used by OpenAI and many others for Bearer tokens.
*   **`cookie`**: Contains session data that could let someone impersonate you.
*   **`x-api-key`**: A common standard for passing keys.

### Part 2: OpenAI and Azure Specifics

OpenAI and Microsoft Azure have their own specific headers.

```python
    "openai-organization": "OPENAI-ORG-XXX",
    "openai-project": "OPENAI-PROJECT-XXX",
    "azureml-model-session": "AZUREML-MODEL-SESSION-XXX",
    "x-ms-client-request-id": "X-MS-CLIENT-REQUEST-ID-XXX",
    # ... logic continues ...
```

*   **`openai-organization`**: Identifies which company account gets billed. We mask this to keep your org ID private.
*   **`x-ms-...`**: Microsoft (MS) headers used for Azure cloud tracking.

### Part 3: Google and Anthropic

Other AI providers use different names for their keys. We must catch them all.

```python
    "x-goog-api-key": "X-GOOG-API-KEY-XXX",
    "anthropic-organization-id": "ANTHROPIC-ORGANIZATION-ID-XXX",
    "anthropic-ratelimit-tokens-remaining": "ANTHROPIC-RATELIMIT-XXX",
    # ... logic continues ...
```

*   **`x-goog-api-key`**: Google's version of an API key.
*   **`anthropic-ratelimit...`**: Notice we are filtering "rate limits" (how many tokens you have left).
    *   **Why?** These numbers change every second. If we record "You have 99 tokens left," but the next test runs and says "You have 98 tokens left," the test might fail because the files don't match. We filter them to make the test **deterministic** (always the same).

### Part 4: AWS (Amazon)

Amazon Web Services (AWS) is very strict about security signatures.

```python
    "x-amz-date": "X-AMZ-DATE-XXX",
    "amz-sdk-invocation-id": "AMZ-SDK-INVOCATION-ID-XXX",
    "x-amzn-requestid": "X-AMZN-REQUESTID-XXX",
}
```

*   **`x-amz-date`**: AWS requests often require a precise timestamp. We mask this so we don't have to worry about time zones or clock drift in our recordings.

## How is this used?

You might remember this list from [Chapter 2: vcr_config](02_vcr_config.md). This dictionary is imported and converted into a list format that VCR understands.

Here is the snippet from Chapter 2 to refresh your memory:

```python
@pytest.fixture(scope="module")
def vcr_config(vcr_cassette_dir: str) -> dict[str, Any]:
    config = {
        # ... other config ...
        "filter_headers": [(k, v) for k, v in HEADERS_TO_FILTER.items()],
    }
    return config
```

By passing this list to the config, we ensure that **globally**, for every single test in CrewAI, these secrets are never written to disk.

## Summary

In this chapter, we learned about `HEADERS_TO_FILTER`:

1.  It is a **security measure** to prevent leaking API keys and tokens.
2.  It creates **determinism** by hiding changing data (like timestamps and rate limits).
3.  It is a simple **Dictionary** mapping sensitive keys to safe placeholders (like `XXX`).

However, a list is just a piece of paper. It doesn't do anything by itself. We need an active worker to take this list, look at the incoming network requests, and actually perform the replacement.

In the next chapter, we will look at the function that applies these rules to outgoing requests.

[Next Chapter: _filter_request_headers](05__filter_request_headers.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)