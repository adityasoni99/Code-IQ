# Chapter 7: Agent Runtime

In the previous chapter, [Messages](06_messages.md), we learned how to package data into rich objects containing text, images, and metadata.

Up until now, our scripts have been simple: we create an agent variable, call a method on it, and wait. But real-world applications are complex. You might have agents running in the background, agents waking up only when a specific event happens, or agents distributed across different computers.

To manage this complexity, we need an **Agent Runtime**.

## The Problem: The Busy Kitchen

Imagine a large restaurant kitchen.
*   **Without a Runtime:** The Waiter has to run physically to the Chef to give an order. Then run to the Bartender for drinks. Then run to the Manager to complain. It is a chaotic web of direct connections.
*   **With a Runtime:** The Waiter puts a ticket on a central **Wheel**. The Chef picks it up when ready. The Bartender picks up drink tickets. The system manages the flow.

## What is the Agent Runtime?

The **Agent Runtime** is the operating system for your agents. It creates a layer between your code and the agents.

Instead of saying "Agent A, tell Agent B...", you say "Runtime, deliver this message to Agent B."

This provides three superpowers:
1.  **Lifecycle Management:** The runtime wakes up agents when they receive a message and shuts them down to save memory.
2.  **Message Routing:** It handles the delivery of messages (like a post office).
3.  **Pub/Sub (Publish/Subscribe):** An agent can shout "I found a bug!" and any agent subscribed to "bugs" will receive it, without the sender knowing who they are.

## Use Case: The News Broadcaster

Let's build a system where a **Broadcaster** sends out a news alert. We want a **Subscriber** to receive it automatically without the Broadcaster knowing who is listening.

We will use the `SingleThreadedAgentRuntime`, which runs everything efficiently in one process.

### Step 1: Initialize the Runtime

First, we create the runtime environment. This is the container for our world.

```python
from autogen_core import SingleThreadedAgentRuntime

# Create the engine that will drive our agents
runtime = SingleThreadedAgentRuntime()
```

### Step 2: Register an Agent

In a Runtime, you don't usually create the agent object yourself instantly. Instead, you give the runtime a **Factory** (a recipe) to create the agent when needed.

Let's assume we have a simple agent class `MyAgent` (created as per [Chapter 1](01_agent.md)).

```python
from autogen_core import AgentId, AgentType

# Define the ID for our new worker
agent_id = AgentId("news_listener", "default")

# Register the recipe. 
# The runtime will call 'MyAgent' only when a message arrives.
await runtime.register_factory(
    type=AgentType("news_listener"),
    agent_factory=lambda: MyAgent(name="Listener")
)
```

### Step 3: Subscribe to a Topic

Now we tell the runtime that this agent is interested in a specific topic. This is like following a hashtag on social media.

```python
from autogen_core import TopicId, Subscription

# Define the topic
news_topic = TopicId("breaking_news", source="default")

# Create a subscription
sub = Subscription(
    id="sub1", 
    topic_type=news_topic.type, 
    agent_type="news_listener"
)

# Tell the runtime to connect them
await runtime.add_subscription(sub)
```

### Step 4: Publish a Message

Now, we don't talk to the agent. We talk to the **Runtime**. We publish a message to the "breaking_news" topic.

```python
from autogen_agentchat.messages import TextMessage

# Start the runtime background processing
runtime.start()

# Publish a message into the ether
await runtime.publish_message(
    TextMessage(content="Aliens have landed!", source="broadcaster"),
    topic_id=news_topic
)

# Wait for the system to finish processing
await runtime.stop_when_idle()
```

**What happens?**
1.  You drop a message into the Runtime.
2.  The Runtime looks up who subscribed to `breaking_news`.
3.  It finds `news_listener`.
4.  It checks if the agent is running. If not, it uses the **Factory** to create it.
5.  It delivers the message to the agent's `on_message` handler.

## Internal Mechanics: The Event Loop

How does the runtime handle messages without freezing your application? It uses an **Event Loop** and a **Message Queue**.

```mermaid
sequenceDiagram
    participant User
    participant Queue as Message Queue
    participant Loop as Runtime Loop
    participant Agent

    User->>Queue: Publish "Hello"
    Note over Queue: Message sits in line
    Loop->>Queue: Any new mail?
    Queue->>Loop: Yes, 1 message for Topic X
    Loop->>Loop: Who is subscribed? -> Agent A
    Loop->>Agent: Wake up & Process Message
    Agent->>Loop: Done!
```

### Looking Under the Hood

Let's look at the actual code in `autogen_core/_single_threaded_agent_runtime.py`.

The core of the runtime is a `Queue` (a list of waiting tasks).

```python
class SingleThreadedAgentRuntime(AgentRuntime):
    def __init__(self, ...):
        # This is the mailbox where all messages wait
        self._message_queue = Queue() 
        # This is the directory of known agents
        self._agent_factories = {}
```

When you call `start()`, a background task begins running `process_next()`. This function pulls an envelope off the queue and figures out what to do with it.

```python
    async def _process_next(self) -> None:
        # 1. Get the next envelope
        envelope = await self._message_queue.get()

        # 2. Check if it is a Direct Send or a Publish
        match envelope:
            case PublishMessageEnvelope(topic_id=topic, ...):
                # 3. Find everyone listening to this topic
                recipients = await self._sub_manager.get_recipients(topic)
                
                # 4. Deliver to all of them
                for agent_id in recipients:
                    agent = await self._get_agent(agent_id)
                    await agent.on_message(envelope.message, ...)
```

The `_get_agent` method is the **Lifecycle Manager**. It checks if the agent is already alive in memory (`_instantiated_agents`). If not, it runs the factory function you registered earlier to create it.

## Distributed Runtime

The examples above used `SingleThreadedAgentRuntime`. This runs everything on **one computer** in **one process**.

But what if you are building a massive application?
*   **Computer A:** Runs the database agents.
*   **Computer B:** Runs the heavy AI processing agents.

Autogen supports a **Distributed Runtime** (typically using gRPC).

The logic remains the same (Register -> Subscribe -> Publish), but the Runtime sends the message over the network to a "Worker" on another machine instead of just looking in local memory.

## Summary

*   The **Agent Runtime** is the infrastructure that manages your agents.
*   It decouples **Senders** from **Receivers** using **Topics** and **Subscriptions**.
*   It manages the **Lifecycle** of agents (creating them only when needed).
*   **`SingleThreadedAgentRuntime`** is great for simple, single-process apps.
*   **Distributed Runtimes** allow agents to communicate across different computers.

## Conclusion

Congratulations! You have completed the **Autogen Beginner Tutorial**.

We started with a single **[Agent](01_agent.md)**, gave it a **[Brain](02_model_client.md)**, equipped it with **[Tools](03_tools_and_capabilities.md)**, formed a **[Team](04_teams_and_orchestration.md)**, set rules for **[Termination](05_termination_conditions.md)**, learned the structure of **[Messages](06_messages.md)**, and finally built a robust **[Runtime](07_agent_runtime.md)** to manage it all.

You are now equipped to build scalable, intelligent multi-agent systems. Happy coding!

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)