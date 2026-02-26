# Chapter 6: _filter_response_headers

Welcome to Chapter 6!

In the previous chapter, [_filter_request_headers](05__filter_request_headers.md), we built a security guard for **outgoing** messages. We made sure that when our tests ask the AI for something, we don't accidentally send secrets or rigid server names to our recording files.

Now, we must handle the **incoming** messages. When the AI server replies to us, that message needs to be cleaned up, too!

## The Motivation: Why do we need this?

**The Use Case:**
You run a test where your agent asks GPT-4 for a summary. The server replies.
1.  **The Gibberish Problem:** To make the internet faster, servers often "zip" (compress) their answers. If you look at the raw recording, it looks like `\x1f\x8b\x08...`. You can't read it, and you can't debug it.
2.  **The Ghost Problem:** Sometimes, due to how code libraries work, the recorder thinks it sees a response, but it's actually empty. We don't want to save empty "ghost" files.
3.  **The Secret Problem:** Just like requests, responses can contain secrets (like `Set-Cookie`) that we don't want in our files.

**The Solution:**
We need an "Incoming Mail Clerk" (`_filter_response_headers`). This clerk opens the packages, unzips the contents so they are readable, throws away empty envelopes, and scrubs out any sensitive return addresses.

## How It Works: The Mail Clerk

This function sits between the Server (OpenAI) and our Hard Drive (VCR). It modifies the data *before* it gets saved to the cassette file.

```mermaid
sequenceDiagram
    participant Server as OpenAI Server
    participant Clerk as _filter_response_headers
    participant Recorder as VCR Tape

    Server->>Clerk: Sends Response (Compressed & Sensitive)
    
    rect rgb(240, 240, 240)
        Note over Clerk: Step 1: Check contents
        Clerk->>Clerk: Is body empty? If yes, discard!
    end

    rect rgb(230, 240, 255)
        Note over Clerk: Step 2: Unzip
        Clerk->>Clerk: Detect GZIP -> Decompress to text
    end

    rect rgb(255, 240, 240)
        Note over Clerk: Step 3: Redact
        Clerk->>Clerk: Scrub headers using Filter List
    end

    Clerk->>Recorder: Save Clean, Readable Response
```

## Under the Hood: The Code

Let's look at `conftest.py` to see how this is implemented. We will break it into three distinct tasks.

### Task 1: Filtering "Ghost" Responses

Sometimes, the HTTP client (the code talking to the server) acts strange. It might read a stream of data and then trigger a second "read" event that is empty. We want to ignore that second event.

```python
def _filter_response_headers(response: dict[str, Any]) -> dict[str, Any] | None:
    """Filter sensitive headers and handle empty bodies."""
    
    # Get the body content and headers
    body = response.get("body", {}).get("string", "")
    headers = response.get("headers", {})
    content_length = headers.get("content-length", [])

    # If the body is empty or length is 0, DO NOT RECORD IT
    if body == "" or body == b"" or content_length == ["0"]:
        return None 
```

*   **`response`**: A dictionary representing the HTTP response.
*   **`return None`**: This is a special signal to VCR. It means "Pretend this never happened. Do not write anything to disk."

### Task 2: Unzipping the Data (GZIP)

If the server sent us a compressed package, we want to unzip it *now*. If we save the unzipped version, we can open our `cassette.yaml` files later and actually read what the AI said!

```python
    # Check if the server sent compressed data
    for encoding_header in ["Content-Encoding", "content-encoding"]:
        if encoding_header in headers:
            encoding = headers.pop(encoding_header) # Remove the header
            
            # If it is GZIP, we need to decompress it
            if encoding and encoding[0] == "gzip":
                body = response.get("body", {}).get("string", b"")
                
                # Check magic bytes to ensure it's actually gzip
                if isinstance(body, bytes) and body.startswith(b"\x1f\x8b"):
                    # Decompress and turn into readable text
                    response["body"]["string"] = gzip.decompress(body).decode("utf-8")
```

*   **`headers.pop`**: We remove the `Content-Encoding: gzip` header. Why? Because we are unzipping it! If we left the header, a browser trying to read our recording would try to unzip it *again* and fail.
*   **`gzip.decompress`**: The standard Python tool for unzipping data.

### Task 3: Scrubbing Secrets

Finally, we apply the same security rules we learned in [HEADERS_TO_FILTER](04_headers_to_filter.md).

```python
    # Loop through our blacklist of sensitive headers
    for header_name, replacement in HEADERS_TO_FILTER.items():
        # Check all capitalizations (Key, KEY, key)
        for variant in [header_name, header_name.upper(), header_name.title()]:
            if variant in headers:
                # Replace the value with XXX
                headers[variant] = [replacement]
                
    return response
```

*   **Logic**: This is identical to the logic in Chapter 5, but it runs on the *Response* headers instead of the Request headers.

## Example: Inputs and Outputs

Let's see the transformation this function performs.

**Input (What the Server Sent):**
```text
HTTP/1.1 200 OK
Content-Encoding: gzip
Set-Cookie: session_id=SECRET_123
Body: [Unreadable Binary Data]
```

**Output (What VCR Saves to Disk):**
```text
HTTP/1.1 200 OK
Set-Cookie: SET-COOKIE-XXX
Body: "The capital of France is Paris."
```

As you can see, the `Content-Encoding` header is gone, the binary data is now readable text, and the secret cookie is redacted.

## Summary

In this chapter, we learned about `_filter_response_headers`:

1.  It acts as a **cleaning service** for incoming server messages.
2.  It prevents **duplicate "ghost" recordings** by filtering empty bodies.
3.  It makes our test files **human-readable** by decompressing GZIP data.
4.  It ensures **security** by redacting sensitive response headers.

We have now secured both the outgoing requests (Chapter 5) and the incoming responses (Chapter 6). Our VCR system is safe and organized!

However, there is a specific bug in the underlying `vcrpy` library. It crashes when we try to upload files (binary data) to the AI. Since CrewAI agents often need to read files, we need to fix this.

In the next chapter, we will write a "Patch"—a small piece of code that fixes a bug in someone else's library.

[Next Chapter: _patched_make_vcr_request](07__patched_make_vcr_request.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)