# Chapter 2: Agent Runtime

Welcome to the second chapter of the **pi-mono** tutorial!

In the previous [Agent Session](01_agent_session.md) chapter, we built the "body" of our AI—the system that saves files and manages history. Now, we are going to look at the **"Central Nervous System"**: the **Agent Runtime**.

While the Session manages *files*, the Runtime manages *thought*.

## Motivation: The Loop of Thought

A raw Large Language Model (LLM) is actually quite simple: you give it text, and it predicts the next text. It doesn't know how to "browse the web" or "run code." It can only *write* about browsing the web.

To create a true Agent, we need a system that can:
1.  **Read** the LLM's desire to use a tool (e.g., "I need to run the `ls` command").
2.  **Execute** that command on the real computer.
3.  **Feed** the result back to the LLM.
4.  **Repeat** until the task is done.

This cycle—**Think → Act → Observe → Repeat**—is the job of the `Agent` class.

## Key Concepts

### 1. The Event Stream
The Agent is chatty. It doesn't just give you the final answer; it emits events for everything happening inside its brain:
*   `message_start`: "I'm starting to type."
*   `tool_execution_start`: "I'm about to run a command."
*   `tool_execution_end`: "I finished the command."

### 2. The Context
The Agent keeps a list of `AgentMessage` objects. This is its short-term working memory. It contains the User's prompt, its own previous replies, and the results of any tools it used.

### 3. The Recursive Loop
Unlike a standard chat where you say "Hello" and the bot says "Hi", the Agent Runtime enters a **Loop**. One user prompt might trigger 10 internal steps of tool usage before the Agent finally replies to you.

## Use Case: The "Weather" Agent

Imagine a user asks: *"What is the weather in Tokyo?"*

1.  **LLM:** "I don't know the future. I should call the `get_weather` tool."
2.  **Runtime:** Sees this request. Stops the LLM. Calls the actual weather API.
3.  **Runtime:** Gets "Sunny, 25°C". Pastes this into the chat history as a "Tool Result".
4.  **Runtime:** Pokes the LLM again: "Here is the tool result. What now?"
5.  **LLM:** "The weather in Tokyo is Sunny and 25°C."

The `Agent` class automates this entire dance.

## Usage Example

Using the `Agent` directly is lower-level than using the Session. Here is how you initialize the brain and send a thought.

### 1. Setup the Agent
We create an agent and give it an initial state (like which model to use).

```typescript
import { Agent } from "@mariozechner/pi-ai";

const agent = new Agent({
    initialState: {
        model: myGeminiModel, // The AI Brain
        tools: [weatherTool],  // The AI Hands
    }
});
```

*Explanation:* We configure the agent with a model and a list of tools it is allowed to use. We'll learn how to build tools in [Standard Tools](04_standard_tools.md).

### 2. Sending a Prompt
We send a message using `.prompt()`.

```typescript
// Subscribe to see what happens in real-time
agent.subscribe((event) => {
    if (event.type === "tool_execution_start") {
        console.log(`Agent is using tool: ${event.toolName}`);
    }
});

// Trigger the thought loop
await agent.prompt("Check the weather in Tokyo");
```

*Explanation:* Calling `prompt` starts the `agentLoop`. This function won't return until the Agent has finished *everything*—including all tool calls and the final text response.

## Internal Implementation: The `agentLoop`

How does the Runtime handle this multi-step process without getting lost?

### Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant Loop as Agent Loop
    participant LLM as AI Model
    participant Tool as Tool

    U->>Loop: prompt("Check Weather")
    
    loop Thinking Cycle
        Loop->>LLM: Stream Response...
        LLM->>Loop: "Call Tool: Weather('Tokyo')"
        
        Loop->>Tool: Execute Weather('Tokyo')
        Tool-->>Loop: Result: "Sunny"
        
        Loop->>Loop: Add Result to History
        Loop->>LLM: "Here is the result. Continue."
        LLM-->>Loop: "It is Sunny in Tokyo."
    end
    
    Loop->>U: Final Answer
```

### Deep Dive: The Code

The logic lives primarily in two files: `agent.ts` (the class) and `agent-loop.ts` (the logic).

#### 1. The Agent Class (`agent.ts`)
The class is primarily a container for **State**.

```typescript
export class Agent {
    private _state: AgentState = {
        messages: [],      // History
        tools: [],         // Available capabilities
        isStreaming: false // Are we thinking right now?
    };
    
    // ... logic to update state ...
}
```

*Explanation:* This holds the "Context Window" of the conversation. When you call `prompt()`, it adds your message to `_state.messages` and calls the loop.

#### 2. The Loop (`agent-loop.ts`)
This is the heart of the engine. It uses a `while (true)` loop to process steps until the AI is satisfied.

```typescript
// Simplified logic from agentLoop function
async function runLoop(...) {
    while (true) {
        // 1. Ask the LLM for a response based on current history
        const message = await streamAssistantResponse(...);
        
        // 2. Did the LLM ask to use a tool?
        const toolCalls = message.content.filter(c => c.type === "toolCall");

        if (toolCalls.length > 0) {
            // 3. Execute the tools
            await executeToolCalls(currentContext.tools, message, ...);
            
            // 4. CONTINUE the loop (go back to step 1)
            continue; 
        }

        // 5. No tools used? We are done.
        break; 
    }
}
```

*Explanation:* This `while` loop is what makes the agent "autonomous." It will keep looping, executing tools, and feeding results back into the conversation until the LLM decides to write standard text instead of a tool call.

#### 3. Executing Tools
When a tool call is detected, the Agent must run it and format the output.

```typescript
async function executeToolCalls(tools, message, stream) {
    // Find the requested tool
    const tool = tools.find(t => t.name === toolCall.name);

    // Run the actual function
    const result = await tool.execute(toolCall.id, args);

    // Create a specific "Tool Result" message
    const resultMsg = {
        role: "toolResult", 
        content: result.content
    };
    
    return resultMsg;
}
```

*Explanation:* The result is wrapped in a special message with the role `toolResult`. This tells the LLM, "This is exactly what the computer returned when you ran that command."

## Why "Steering" Matters

You might notice functions like `steer()` in the full source code.
Sometimes an Agent gets stuck in a loop (e.g., trying to read a file that doesn't exist 100 times).

**Steering** allows the User to inject a message *while the loop is running*.
*   *User:* "Stop trying to read that file, just create a new one."
*   *Runtime:* Injects this message into the event stream immediately.
*   *LLM:* Receives the user's correction and changes course.

## Conclusion

The **Agent Runtime** is the engine that transforms a static LLM into a dynamic worker. It handles the complex logic of chaining thoughts, executing code, and managing the conversation flow.

In this chapter, we learned:
*   The Runtime operates in a **Loop** (Think -> Act -> Repeat).
*   It manages **State** (messages and tools).
*   It emits **Events** so the UI knows what's happening.

But wait—how do we actually talk to different LLMs like OpenAI, Anthropic, or Gemini without rewriting our code every time? That is handled by the **Unified AI Interface**.

[Next Chapter: Unified AI Interface](03_unified_ai_interface.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)