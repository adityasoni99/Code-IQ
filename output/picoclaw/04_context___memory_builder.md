# Chapter 4: Context & Memory Builder

In the previous chapter, [LLM Providers](03_llm_providers.md), we connected our agent to a powerful "Brain" (like GPT-4 or Claude).

However, there is a catch. **LLMs are amnesiacs.**

If you say "My name is Alice" to the AI, and then restart the program, the AI will have no idea who you are. In fact, even within the same program, if we don't handle it correctly, the AI treats every single message as the very first time it has ever met you.

We need a system to remind the AI of who it is, what it knows, and what you talked about yesterday. We call this the **Context & Memory Builder**.

## The Problem: The "Blank Slate"

Imagine an actor stepping onto a stage. Every time the curtain opens, their mind is wiped blank. To perform the scene correctly, someone needs to hand them a dossier immediately before the curtain rises:

1.  **Script:** "You are a helpful assistant named PicoClaw."
2.  **Props:** "You are holding a wrench and a calculator."
3.  **Backstory:** "Yesterday, the user asked you to fix a server."
4.  **Current Line:** "The user just said: 'Is it done?'"

If we don't give the actor this dossier, they will just stand there confused.

In `picoclaw`, the **Context Builder** is the stage manager who compiles this dossier (the "System Prompt") before every single interaction.

## Concept 1: The "Identity" (Who Am I?)

The first thing the builder does is establish the agent's personality. Instead of hard-coding this in Go, we use simple Markdown files in your workspace.

The builder looks for files like `AGENT.md` or `IDENTITY.md`.

### Use Case
You want your agent to be a "Grumpy System Admin." You don't change the code; you just edit a text file.

```markdown
<!-- workspace/AGENT.md -->
You are a grumpy system admin. 
You answer questions briefly. 
Always complain about the lack of coffee.
```

### The Code
Here is how the Context Builder loads these files. It acts like a biographer, reading your notes to build the persona.

```go
// pkg/agent/context.go (Simplified)

func (cb *ContextBuilder) LoadBootstrapFiles() string {
    // We look for these specific files
    files := []string{"AGENT.md", "IDENTITY.md"}
    var content string

    for _, filename := range files {
        // Read the file from the disk
        data, _ := os.ReadFile(filepath.Join(cb.workspace, filename))
        
        // Add it to our "Dossier"
        content += fmt.Sprintf("## %s\n%s\n", filename, string(data))
    }
    return content
}
```

**Explanation:** The function loops through the file names, reads their text, and stitches them together into one big string.

## Concept 2: The "Environment" (Where Am I?)

The AI doesn't have a watch or eyes. It doesn't know what time it is or what computer it's running on. The Context Builder generates this dynamically.

It adds a section to the System Prompt that looks like this:

```text
## Current Time
2023-10-27 14:30 (Friday)

## Runtime
linux amd64, Go 1.22
```

### The Code
The `getIdentity` function injects this dynamic data.

```go
// pkg/agent/context.go (Simplified)

func (cb *ContextBuilder) getIdentity() string {
    // 1. Get the current time
    now := time.Now().Format("2006-01-02 15:04 (Monday)")
    
    // 2. Get OS info
    osInfo := fmt.Sprintf("%s %s", runtime.GOOS, runtime.GOARCH)

    // 3. Format into a string for the AI
    return fmt.Sprintf("# System Info\nTime: %s\nOS: %s", now, osInfo)
}
```

## Concept 3: The "Memory" (What Happened?)

This is the most critical part. We want the agent to remember things long-term.

In `picoclaw`, memory is just a text file!
1.  **Long-term:** `memory/MEMORY.md` (Facts about the user, preferences).
2.  **Short-term:** `memory/202310/20231027.md` (Daily notes).

When the Context Builder runs, it grabs the content of these files and pastes them into the System Prompt.

### Use Case
User: *"My birthday is in June."*
Agent (writes to file): *Updates MEMORY.md*

Next week:
User: *"When is my birthday?"*
Context Builder: *Reads MEMORY.md -> Sends to AI -> AI answers "June".*

### The Code (Reading Memory)
```go
// pkg/agent/memory.go (Simplified)

func (ms *MemoryStore) GetMemoryContext() string {
    // 1. Read the permanent memory file
    longTerm := ms.ReadLongTerm()

    // 2. Read recent daily notes (e.g., last 3 days)
    recentNotes := ms.GetRecentDailyNotes(3)

    // 3. Combine them
    return fmt.Sprintf("# Memory\n%s\n\n# Recent Events\n%s", 
        longTerm, recentNotes)
}
```

## Internal Workflow

Let's visualize exactly what happens when a message arrives. The **Agent Loop** calls the **Context Builder** to assemble the full packet before calling the **Provider**.

```mermaid
sequenceDiagram
    participant Loop as Agent Loop
    participant Builder as Context Builder
    participant Files as Disk (MD Files)
    participant Provider as LLM Provider

    Loop->>Builder: "Build context for User msg: Hello"
    
    activate Builder
    Builder->>Files: Read AGENT.md (Identity)
    Builder->>Files: Read MEMORY.md (History)
    Note over Builder: Checks Time & OS
    
    Builder->>Builder: Stitch into one massive string
    deactivate Builder
    
    Builder-->>Loop: Returns System Prompt
    
    Loop->>Provider: Chat(System Prompt + "Hello")
```

## Assembling the Final Prompt

Finally, the `BuildMessages` function puts it all together. This creates the exact list of messages that gets sent to the [LLM Provider](03_llm_providers.md).

It follows a specific order:
1.  **System Prompt:** (Identity + Environment + Skills + Memory)
2.  **Conversation History:** (What we said 5 minutes ago)
3.  **User Message:** (What the user just said)

```go
// pkg/agent/context.go (Simplified)

func (cb *ContextBuilder) BuildMessages(history []Message, userMsg string) []Message {
    // 1. Generate the huge context string (Identity + Memory + Tools)
    systemPrompt := cb.BuildSystemPrompt()

    // 2. Start the list with the System Prompt
    messages := []Message{{
        Role: "system", 
        Content: systemPrompt,
    }}

    // 3. Add history and the new user message
    messages = append(messages, history...)
    messages = append(messages, Message{Role: "user", Content: userMsg})

    return messages
}
```

**Why is this important?**
Because the AI reads from top to bottom.
1. It reads "I am a helpful assistant."
2. It reads "Memory: User likes Python."
3. It reads "User: Write me a script."
4. It concludes: "I should write a Python script."

## Summary

In this chapter, we learned:
1.  **Context Builder** is the "Biographer" that tells the AI who it is before every interaction.
2.  **Identity** is loaded from simple Markdown files (`AGENT.md`).
3.  **Memory** is injected by reading text files (`MEMORY.md`) and pasting them into the prompt.
4.  **Dynamic Info** like time and tools are generated on the fly.

Now our agent has a personality, knows what time it is, and can remember facts. But... it still can't *do* anything other than talk.

To make our agent useful, we need to teach it **Skills**.

[Next: Chapter 5 - Skills System](05_skills_system.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)