# Chapter 2: The Agent Loop

In the previous chapter, **[Channel Gateway](01_channel_gateway.md)**, we gave our bot **ears** to hear messages and a **mouth** to speak them. But right now, if you say "Hello", the bot just holds that message. It has no brain to process it.

In this chapter, we will build the **Brain**, technically known as the **Agent Loop**.

## 1. The Conductor of the Orchestra

An AI agent isn't just a simple script that says `if input == "hi" then print("hello")`. It is a dynamic system that needs to coordinate several moving parts.

Think of the **Agent Loop** as the **Conductor** of an orchestra.

*   **The Musicians:**
    *   **History:** Past conversations (Memory).
    *   **Tools:** Calculators, Google Search, File writers.
    *   **The LLM:** The creative composer (e.g., GPT-4, Claude).

The Conductor's job is to take a request from the audience (the User), look at the sheet music (Context), wave the baton to let the LLM compose a plan, and signal the Tools to play their part.

### The Central Use Case: "What is the date?"
If a user asks: *"What is today's date?"*

1.  **LLM:** The AI model knows a lot, but it doesn't know "today" because its training data is old. It decides: "I need to check a clock."
2.  **Agent Loop:** Sees the AI wants to check a clock. It runs the `get_date` tool.
3.  **Tool:** Returns `"2023-10-27"`.
4.  **Agent Loop:** Gives this info back to the LLM.
5.  **LLM:** "Oh, thanks. The date is October 27th, 2023."
6.  **Agent Loop:** Sends the final answer to the user.

This back-and-forth process is the **Loop**.

---

## 2. Building the Context (The "Orient" Phase)

Before the Conductor can make a decision, it needs to understand the situation. Large Language Models (LLMs) are **stateless**—they don't remember what you said 5 seconds ago unless you send that text back to them every time.

We use a **ContextBuilder** to gather everything the bot needs to know.

### How it Works visually
```mermaid
flowchart LR
    Identity[Identity: "You are a bot..."] --> Mixer
    History[History: "User said hi..."] --> Mixer
    Skills[Skills: "You can search web..."] --> Mixer
    Current[Current: "What is the date?"] --> Mixer
    
    Mixer[Context Builder] --> Prompt[Final Prompt]
```

### The Code: Assembling the Prompt
In `nanobot/agent/context.py`, the `ContextBuilder` stitches these pieces together.

```python
# nanobot/agent/context.py

def build_messages(self, history, current_message, ...):
    messages = []

    # 1. System Prompt (Identity & Instructions)
    system_prompt = self.build_system_prompt()
    messages.append({"role": "system", "content": system_prompt})

    # 2. Conversation History (Short-term memory)
    messages.extend(history)

    # 3. The New Message
    messages.append({"role": "user", "content": current_message})

    return messages
```

**Explanation:**
*   **System Prompt:** Defines who the bot is (e.g., "You are nanobot, a helpful assistant...").
*   **History:** We pull recent chat logs from [Memory & Persistence](04_memory___persistence.md) so the bot can hold a conversation.
*   **Result:** A clean list of messages ready for the LLM.

---

## 3. The Loop Implementation

Now let's look at the heart of the engine: `nanobot/agent/loop.py`.

The loop is designed to run in cycles. Why? Because sometimes one tool isn't enough. The bot might need to:
1.  Search Google (Loop 1).
2.  Read a webpage found in the search (Loop 2).
3.  Summarize the answer (Loop 3).

### The Flow Diagram
Here is what happens inside the `AgentLoop` class.

```mermaid
sequenceDiagram
    participant User
    participant Loop as Agent Loop
    participant LLM as LLM Provider
    participant Tool as Tooling System

    User->>Loop: "Check weather in NY"
    
    loop Thinking Cycle
        Loop->>LLM: Sends Context + Available Tools
        LLM->>Loop: Response: "Call Tool 'weather(NY)'"
        
        Note over Loop: Bot sees a tool request...
        
        Loop->>Tool: Executes 'weather(NY)'
        Tool->>Loop: Result: "Sunny, 25C"
        
        Loop->>Loop: Appends result to History
    end
    
    Loop->>LLM: Sends Context + Tool Result
    LLM->>Loop: Response: "It's sunny in NY!"
    Loop->>User: "It's sunny in NY!"
```

### The Code: The While Loop
This is the most critical logic in the bot. It keeps asking the LLM "What's next?" until the LLM says "I'm done."

```python
# nanobot/agent/loop.py

async def _run_agent_loop(self, messages):
    iteration = 0
    
    # Keep going until we hit a limit (e.g., 20 steps)
    while iteration < self.max_iterations:
        # 1. Ask the LLM what to do
        response = await self.provider.chat(messages, tools=self.tools)

        # 2. Did the LLM ask to use a tool?
        if response.has_tool_calls:
            # Execute the tool (e.g., read_file, web_search)
            for tool_call in response.tool_calls:
                result = await self.tools.execute(tool_call.name, tool_call.args)
                
                # 3. Add the result to the message list for the next loop
                messages = self.context.add_tool_result(messages, result)
        else:
            # 4. No tool needed? Then this is the final answer.
            return response.content
```

**Explanation:**
1.  **`provider.chat`**: This sends the data to the AI (covered in **[LLM Provider Abstraction](03_llm_provider_abstraction.md)**).
2.  **`has_tool_calls`**: The AI didn't reply with text; it replied with a JSON command like `{"name": "web_search", "args": "weather"}`.
3.  **`tools.execute`**: We run the Python function requested (covered in **[Tooling System](05_tooling_system.md)**).
4.  **Recursion:** We feed the tool result *back* into the loop so the AI can read it.

---

## 4. Connecting to the Bus

In Chapter 1, we learned that the **Channel Gateway** puts messages onto a `MessageBus`. The Agent Loop needs to take them off that bus.

This happens in the `run()` method of the Agent Loop. It acts as a permanent listener.

```python
# nanobot/agent/loop.py

async def run(self):
    self._running = True
    
    while self._running:
        # 1. Wait for a message from the Gateway
        msg = await self.bus.consume_inbound()
        
        # 2. Process it (Run the loop we saw above)
        response = await self._process_message(msg)
        
        # 3. Send the reply back to the Gateway
        if response:
            await self.bus.publish_outbound(response)
```

**Explanation:**
*   This method runs forever (an infinite loop).
*   It sits idle until `consume_inbound()` gives it work.
*   It ensures the main application thread is never blocked while waiting for the AI to think.

---

## 5. Subagents (Multitasking)

Sometimes a task is too big for one loop. For example: *"Research the history of Rome and write a report."* This might take 50 steps. We don't want to block the user from saying "Stop!" while that happens.

`nanobot` supports **Subagents**. These are mini-loops that run in the background.

```python
# nanobot/agent/subagent.py

async def spawn(self, task):
    # Create a background task (Fire and Forget)
    asyncio.create_task(self._run_subagent(task))
    
    return "I started a subagent to handle that for you."
```

When the Subagent finishes, it sends a special "System Message" back into the main loop saying: *"Hey, I finished the report, here it is."*

---

## Summary

The **Agent Loop** is the bridge between raw text and intelligent action.

1.  **Context:** It remembers who it is and what you said.
2.  **Deliberation:** It talks to the LLM to decide on a plan.
3.  **Action:** It executes tools if the plan requires them.
4.  **Iteration:** It loops until the task is complete.

Currently, our loop calls `self.provider.chat`. But what exactly is `provider`? How do we switch between OpenAI, Anthropic, or a local Llama model without rewriting our loop?

We will discover that in the next chapter: **[LLM Provider Abstraction](03_llm_provider_abstraction.md)**.

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)