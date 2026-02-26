# Chapter 2: The Recursive Agent Loop

In the previous chapter, [Interactive CLI & State Management](01_interactive_cli___state_management.md), we built the dashboard (the body) of our application. We created a way to see what the agent is doing.

Now, we need to build the **Brain**.

Most simple programs follow a straight line: `Step A -> Step B -> Step C`. But an AI Agent is different. It doesn't know the steps ahead of time. It has to figure them out as it goes.

This chapter explains the **Recursive Agent Loop**—the core engine that allows Dexter to "think," act, observe the results, and think again.

---

### The Motivation: The Detective Analogy

Imagine a detective trying to solve a mystery.

1.  **Linear Script (Bad Detective):** They walk into a room, look at the floor, pick up a specific cup, and declare "Case Closed!" regardless of what they found. This only works if every crime scene is exactly the same.
2.  **Recursive Agent (Good Detective):**
    *   **Observe:** They see a broken window.
    *   **Think:** "I need to check for fingerprints."
    *   **Act:** They dust for prints (Use a Tool).
    *   **Observe:** They find a print.
    *   **Think:** "I need to identify this print."
    *   **Act:** Run it through the database (Use a Tool).
    *   **Result:** It's "Argumentative Alice."
    *   **Answer:** "Alice broke the window."

Dexter works like the Good Detective. We don't hard-code steps; we give Dexter a **Loop**.

---

### The High-Level Concept

The "Brain" of Dexter is implemented in `src/agent/agent.ts`. It doesn't just run once; it runs in a cycle called **ReAct** (Reason + Act).

#### The Cycle
1.  **Input:** The user asks a question.
2.  **Model Call:** The Agent sends the question + history to the LLM (Large Language Model).
3.  **Decision:** The LLM decides: "Do I have the answer, or do I need more info?"
4.  **Action:** If it needs info, it calls a **Tool**.
5.  **Update:** The tool result is added to the history.
6.  **Loop:** Go back to Step 2.

---

### Solving the Use Case: "What is Apple's Price?"

Let's look at how this loop solves a simple financial question.

**User Query:** *"What is the stock price of Apple?"*

1.  **Start:** The loop begins.
2.  **Iteration 1:**
    *   **Think:** The Agent realizes it doesn't know the live price. It decides to call `financial_search("AAPL price")`.
    *   **Act:** It executes the code for that tool.
    *   **Observe:** The tool returns `"{ ticker: 'AAPL', price: 150.00 }"`.
3.  **Iteration 2:**
    *   **Think:** The Agent looks at the new history. It sees the price is $150.
    *   **Decision:** "I have enough information."
    *   **Answer:** "The current stock price of Apple is $150.00."
4.  **End:** The loop terminates.

---

### Internal Implementation: Under the Hood

Let's look at the code in `src/agent/agent.ts`. We will simplify it to focus on the logic.

#### Visualizing the Flow

```mermaid
sequenceDiagram
    participant Loop as Agent Loop
    participant Brain as LLM (Brain)
    participant Tool as Tool Execution

    Note over Loop: User asks: "Check Apple Price"

    loop Until Answered
        Loop->>Brain: Here is the history. What next?
        Brain->>Loop: Response: "Call Tool: Price Check"
        
        alt Uses Tool
            Loop->>Tool: Execute "Price Check"
            Tool-->>Loop: Result: "$150"
            Loop->>Loop: Add "$150" to History
        else Has Answer
            Brain->>Loop: Response: "The price is $150"
            Loop->>Loop: Stop Loop
        end
    end
```

#### Code Walkthrough

The core logic lives in the `run()` method of the `Agent` class.

**1. The Setup**
We start a loop that will run until we have an answer or we hit a limit (so we don't loop forever).

```typescript
// src/agent/agent.ts
async *run(query: string) {
  // We keep track of the conversation context
  const ctx = createRunContext(query);
  
  // We build the very first prompt for the AI
  let currentPrompt = this.buildInitialPrompt(query);

  // THE LOOP starts here
  while (ctx.iteration < this.maxIterations) {
    ctx.iteration++;
    // ... logic continues below ...
  }
}
```
**Explanation:** `ctx` holds our variables. `maxIterations` is usually set to 10 to prevent infinite loops if the agent gets confused.

**2. Asking the Brain**
Inside the loop, we send the current situation to the AI model.

```typescript
    // Inside the while loop...
    
    // 1. Ask the AI what to do
    const { response } = await this.callModel(currentPrompt);
    
    // 2. Check if the AI wants to use a tool
    if (!hasToolCalls(response)) {
      // If NO tools are called, we are done!
      yield* this.generateFinalAnswer(ctx);
      return; 
    }
```
**Explanation:** `callModel` sends the text to the LLM. If the LLM returns text (e.g., "Hi there"), `hasToolCalls` is false, and we exit the loop.

**3. Executing Tools**
If the AI *does* want to use a tool, we execute it and stay in the loop.

```typescript
    // Inside the while loop (continued)...

    // 3. The AI wants to use a tool. Let's run it.
    // This executes the function (e.g., searching the web)
    yield* this.toolExecutor.executeAll(response, ctx);

    // 4. Update the Prompt
    // We take the tool results and add them to the prompt for the next turn
    currentPrompt = buildIterationPrompt(
        query, 
        ctx.scratchpad.getToolResults() // The "Evidence"
    );
    // The loop now repeats with the new evidence!
```
**Explanation:** This is the recursive part. We take the result of the tool, stick it into `currentPrompt`, and go back to the top of the `while` loop. Next time we call `callModel`, the AI will "see" the tool's result.

---

### How the Agent "Remembers"

You might wonder: *How does the agent know what it did in the previous step?*

It's all in the **Prompt**.

In `src/agent/prompts.ts`, we have a function `buildIterationPrompt`. Every time the loop runs, we reconstruct the prompt to look like this:

**Iteration 1 Prompt:**
> User Query: "Apple Stock Price"

**Iteration 2 Prompt:**
> User Query: "Apple Stock Price"
>
> **Data retrieved from tool calls:**
> Tool: financial_search
> Result: {"price": 150}

When the AI sees the Iteration 2 prompt, it knows it has the data, so it stops asking for tools and gives the answer.

---

### Summary

In this chapter, we built the engine that powers Dexter:
1.  **The Loop:** A `while` loop that allows the agent to try multiple times to solve a problem.
2.  **The Decision:** Checking `hasToolCalls` to see if we need to work (run a tool) or talk (answer the user).
3.  **The Memory:** Appending tool results to the prompt so the agent learns as it goes.

However, a detective is only as good as their gadgets. Right now, our agent knows *how* to call tools, but it doesn't have any specific skills yet.

In the next chapter, we will give Dexter specialized abilities.

**Next Chapter:** [Skills System](03_skills_system.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)