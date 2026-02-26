# Chapter 3: LLM Provider Abstraction

In the previous chapter, **[The Agent Loop](02_the_agent_loop.md)**, we built the "Conductor" that orchestrates the bot's thinking process. We saw code like `self.provider.chat(messages)`.

But wait—what exactly is `self.provider`?

If you want your bot to switch from OpenAI's **GPT-4** to Anthropic's **Claude** or even a local **Llama 3** model running on your laptop, you shouldn't have to rewrite your entire codebase.

This is where the **LLM Provider Abstraction** comes in.

## 1. The Universal Remote

Imagine if every TV brand required a completely different hand motion to change the channel. For Sony, you have to wave; for Samsung, you have to clap. That would be exhausting. Instead, we have **Universal Remotes**. You press "Channel Up," and the remote handles the specific signal for the TV.

The **LLM Provider Abstraction** is that universal remote for AI models.

### The Problem
*   **OpenAI** expects a JSON input like `{"messages": [...]}`.
*   **Anthropic** expects `{"system": "...", "messages": [...]}`.
*   **Local Models** might expect a raw text prompt.

### The Solution: A Universal Driver
We create a standard "Driver" layer. The core of our bot (The Agent Loop) simply says: **"Here is the conversation history. Give me a response."**

The Provider Abstraction translates that request into the specific language of the AI model being used.

### Central Use Case: Switching Brains
Let's say you are running your bot on **GPT-4**. It's smart but expensive. You want to test a local model, **Mistral**, to save money.

*   **Without Abstraction:** You have to find every line of code calling OpenAI and rewrite it.
*   **With Abstraction:** You change one line in your configuration file: `model: "ollama/mistral"`. The bot continues working instantly.

---

## 2. Key Concepts

To build this, we need to standardize two things: **Input** and **Output**.

### Standardized Input
No matter which AI we use, we always format our conversation history as a list of dictionaries. This is the industry standard (popularized by OpenAI).

```python
[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
]
```

### Standardized Output (`LLMResponse`)
AI APIs return messy, deeply nested JSON. Some put the text in `choices[0].message.content`, others in `content[0].text`.

We define a clean Python object called `LLMResponse`. This is the only thing our Agent Loop ever sees.

```python
@dataclass
class LLMResponse:
    content: str | None       # The text reply (e.g., "Hi there!")
    tool_calls: list          # Did the bot ask to use a tool?
    usage: dict               # How many tokens did we use?
```

---

## 3. How It Works (The Flow)

Here is how the data flows when the Agent Loop asks for a completion.

```mermaid
sequenceDiagram
    participant Loop as Agent Loop
    participant Prov as LLM Provider
    participant GPT as OpenAI
    participant Claude as Anthropic

    Note over Loop: Loop needs a reply
    Loop->>Prov: chat(messages, model="gpt-4")
    
    Note over Prov: Driver translates request
    Prov->>GPT: POST /v1/chat/completions (OpenAI Format)
    GPT->>Prov: Raw JSON Response
    
    Prov->>Prov: Convert to LLMResponse object
    Prov->>Loop: Returns Clean Object
```

If we changed the config to use Anthropic, the **Agent Loop** wouldn't change at all. The **LLM Provider** would simply route the arrow to `Claude` instead of `GPT`.

---

## 4. Implementation: The Blueprint

First, we define the rules in `nanobot/providers/base.py`. This is an **Abstract Base Class** (ABC). It forces any new provider we write to follow the same rules.

```python
# nanobot/providers/base.py

class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        # ... other settings
    ) -> LLMResponse:
        """
        Every provider MUST implement this function.
        It takes messages and tools, and MUST return an LLMResponse.
        """
        pass
```

**Explanation:**
*   This code doesn't *do* anything. It just sets the law: "If you want to be an LLM Provider, you must have a `chat` function."

---

## 5. Implementation: The Universal Worker

In `nanobot`, we use a library called `LiteLLM` to handle the heavy lifting. `LiteLLM` is an open-source library that already knows how to talk to 100+ models. We wrap it in our own class to make it fit our system perfectly.

This is found in `nanobot/providers/litellm_provider.py`.

### The Chat Method
This is the most important function in the abstraction.

```python
# nanobot/providers/litellm_provider.py

async def chat(self, messages, tools=None, model=None, ...) -> LLMResponse:
    # 1. Prepare the arguments for LiteLLM
    kwargs = {
        "model": model or self.default_model,
        "messages": messages,
        "temperature": 0.7
    }

    # 2. Add tools if the Agent Loop sent any
    if tools:
        kwargs["tools"] = tools

    # 3. Call the external library (The "Universal Driver")
    raw_response = await litellm.acompletion(**kwargs)

    # 4. Clean up the messy response into our standard format
    return self._parse_response(raw_response)
```

**Explanation:**
1.  **Preparation:** We bundle up the inputs (`messages`, `model`) into a dictionary.
2.  **Execution:** `litellm.acompletion` sends the request over the internet to OpenAI, Azure, or wherever the model lives.
3.  **Normalization:** We receive a messy raw object and pass it to `_parse_response`.

### The Parser (Cleaning Data)
The Agent Loop shouldn't have to dig through JSON to find the answer. The provider does that work.

```python
# nanobot/providers/litellm_provider.py

def _parse_response(self, response) -> LLMResponse:
    # Extract the first choice from the response
    choice = response.choices[0]
    message = choice.message

    # Return our clean, standard object
    return LLMResponse(
        content=message.content,          # The text: "Hello!"
        finish_reason=choice.finish_reason,
        usage=dict(response.usage)        # Cost tracking
    )
```

**Explanation:**
*   We extract exactly what we need.
*   We ignore the specific weirdness of different APIs.
*   We return the clean `LLMResponse`.

---

## 6. Handling Tool Calls

One of the most complex parts of modern LLMs is **Function Calling** (or Tool Use). The bot might say: *"I need to run the `get_weather` function."*

Different providers format this differently. Our abstraction standardizes this into a list of `ToolCallRequest` objects.

```python
# Inside _parse_response in litellm_provider.py

tool_calls = []
if message.tool_calls:
    for tc in message.tool_calls:
        # 1. Standardize the tool request
        tool_calls.append(ToolCallRequest(
            id=tc.id,
            name=tc.function.name,     # e.g., "get_weather"
            arguments=tc.function.arguments # e.g., {"location": "Paris"}
        ))

# Add the list to the response object
return LLMResponse(..., tool_calls=tool_calls)
```

Now, the **[Agent Loop](02_the_agent_loop.md)** can simply check `response.tool_calls`. It doesn't care if the underlying model formatted the tool call as XML (Anthropic) or JSON (OpenAI)—the Provider Abstraction handled the translation.

---

## Summary

In this chapter, we created the "Universal Driver" for our bot.

1.  **Uniformity:** The bot uses the same code to talk to any AI model.
2.  **Flexibility:** We can swap "brains" (models) just by changing a configuration string.
3.  **Cleanliness:** The messy API details are hidden inside the Provider class, keeping our Agent Loop logic clean.

Now we have a bot that can **Hear** (Gateway), **Think** (Agent Loop), and **Generate Thoughts** (LLM Provider).

However, currently, every time you restart the bot, it forgets everything you just said. It has no long-term memory.

In the next chapter, we will give the bot a permanent brain using **[Memory & Persistence](04_memory___persistence.md)**.

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)