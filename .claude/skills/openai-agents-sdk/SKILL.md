---
name: openai-agents-sdk
description: OpenAI Agents SDK - A lightweight, powerful framework for building multi-agent workflows with Python
---

# OpenAI Agents SDK

A lightweight yet powerful framework for building multi-agent workflows. Provider-agnostic, supporting OpenAI Responses and Chat Completions APIs, plus 100+ other LLMs via LiteLLM.

**Repository:** [openai/openai-agents-python](https://github.com/openai/openai-agents-python)
**Documentation:** [openai.github.io/openai-agents-python](https://openai.github.io/openai-agents-python/)
**Version:** v0.6.1 (Latest)
**License:** MIT

## When to Use This Skill

### Trigger Conditions
Use this skill when the user:
- Asks how to create agents with the OpenAI Agents SDK
- Wants to implement multi-agent workflows or handoffs
- Needs to add tools/functions to agents
- Asks about session management or conversation history
- Wants to implement guardrails (input/output validation)
- Needs help with MCP (Model Context Protocol) integration
- Asks about streaming responses from agents
- Wants to use non-OpenAI models (Claude, Gemini, etc.) via LiteLLM
- Needs to implement tracing or debugging for agent runs

### Concrete Use Cases
1. **Building a chatbot** - Create an agent with custom instructions and tools
2. **Multi-agent orchestration** - Implement handoffs between specialized agents
3. **Tool-calling agents** - Add custom functions that agents can invoke
4. **Conversation persistence** - Store and retrieve chat history with sessions
5. **Safety guardrails** - Validate inputs/outputs before processing
6. **Voice agents** - Build realtime voice-enabled agents
7. **Provider switching** - Use Claude, Gemini, or other models via LiteLLM

## Key Concepts

### Core Architecture
| Concept | Description |
|---------|-------------|
| **Agent** | An LLM configured with instructions, tools, guardrails, and handoffs |
| **Runner** | Executes agents in a loop until final output is produced |
| **Handoff** | Transfers control from one agent to another |
| **Session** | Manages conversation history across multiple runs |
| **Guardrail** | Safety checks for input/output validation |
| **Tracing** | Built-in tracking for debugging and optimization |

### The Agent Loop
1. Call the LLM with model settings and message history
2. LLM returns response (may include tool calls)
3. If final output → return and end loop
4. If handoff → switch to new agent, go to step 1
5. Process tool calls, append responses, go to step 1

## Quick Reference - Code Examples

### 1. Hello World - Basic Agent

```python
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are a helpful assistant")
result = Runner.run_sync(agent, "Write a haiku about recursion.")
print(result.final_output)
```

### 2. Agent with Custom Tool

```python
from agents import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"The weather in {city} is sunny."

agent = Agent(
    name="Weather Bot",
    instructions="You are a helpful weather assistant.",
    tools=[get_weather],
)

result = Runner.run_sync(agent, "What's the weather in Tokyo?")
print(result.final_output)  # The weather in Tokyo is sunny.
```

### 3. Multi-Agent Handoff

```python
from agents import Agent, Runner
import asyncio

spanish_agent = Agent(
    name="Spanish agent",
    instructions="You only speak Spanish.",
)

english_agent = Agent(
    name="English agent",
    instructions="You only speak English",
)

triage_agent = Agent(
    name="Triage agent",
    instructions="Handoff to the appropriate agent based on language.",
    handoffs=[spanish_agent, english_agent],
)

async def main():
    result = await Runner.run(triage_agent, input="Hola, como estas?")
    print(result.final_output)

asyncio.run(main())
```

### 4. Session Memory (Conversation Persistence)

```python
from agents import Agent, Runner, SQLiteSession

agent = Agent(name="Assistant", instructions="Reply concisely.")
session = SQLiteSession("conversation_123", "conversations.db")

# First turn
result = await Runner.run(
    agent,
    "What city is the Golden Gate Bridge in?",
    session=session
)
print(result.final_output)  # "San Francisco"

# Second turn - agent remembers context
result = await Runner.run(
    agent,
    "What state is it in?",
    session=session
)
print(result.final_output)  # "California"
```

### 5. Structured Output

```python
from agents import Agent, Runner
from pydantic import BaseModel

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

agent = Agent(
    name="Calendar Assistant",
    instructions="Extract calendar events from text.",
    output_type=CalendarEvent,
)

result = Runner.run_sync(
    agent,
    "Meeting with Alice and Bob on Friday to discuss Q4 planning"
)
print(result.final_output)  # CalendarEvent object
```

### 6. Using LiteLLM (Non-OpenAI Models)

```python
from agents import Agent, Runner, RunConfig
from agents.extensions.models.litellm import LiteLLMModel

agent = Agent(
    name="Claude Assistant",
    instructions="You are helpful.",
    model=LiteLLMModel(model="anthropic/claude-sonnet-4-20250514"),
)

result = Runner.run_sync(agent, "Hello!")
```

### 7. Input Guardrail

```python
from agents import Agent, Runner, InputGuardrail, GuardrailFunctionOutput

async def check_math_question(ctx, agent, input_text):
    """Only allow math questions."""
    if "math" not in input_text.lower() and "calculate" not in input_text.lower():
        return GuardrailFunctionOutput(
            output_info={"reason": "Not a math question"},
            tripwire_triggered=True,
        )
    return GuardrailFunctionOutput(
        output_info={"reason": "Valid math question"},
        tripwire_triggered=False,
    )

agent = Agent(
    name="Math Tutor",
    instructions="Help with math problems only.",
    input_guardrails=[
        InputGuardrail(guardrail_function=check_math_question)
    ],
)
```

### 8. Streaming Responses

```python
from agents import Agent, Runner

agent = Agent(name="Storyteller", instructions="Tell engaging stories.")

async def stream_story():
    result = Runner.run_streamed(agent, "Tell me a short story.")
    async for event in result.stream_events():
        if event.type == "raw_response_event":
            print(event.data, end="", flush=True)

asyncio.run(stream_story())
```

### 9. MCP Server Integration

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

async with MCPServerStdio(
    params={"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]}
) as mcp_server:
    agent = Agent(
        name="File Assistant",
        instructions="Help with file operations.",
        mcp_servers=[mcp_server],
    )
    result = await Runner.run(agent, "List files in the current directory")
```

### 10. Agent as Tool (Nested Agents)

```python
from agents import Agent, Runner

research_agent = Agent(
    name="Researcher",
    instructions="Research topics thoroughly.",
)

writer_agent = Agent(
    name="Writer",
    instructions="Write articles. Use the researcher for facts.",
    tools=[research_agent.as_tool(
        tool_name="research",
        tool_description="Research a topic"
    )],
)
```

## Available Reference Files

| File | Contents |
|------|----------|
| `references/README.md` | Complete README with installation, examples, and core concepts |
| `references/issues.md` | Recent GitHub issues - useful for known bugs and feature requests |
| `references/releases.md` | Release notes for v0.6.1, v0.6.0, v0.5.x with breaking changes |
| `references/file_structure.md` | Repository structure showing examples, docs, and source locations |

## Working with This Skill

### For Beginners
1. Start with the **Hello World** example (Example 1)
2. Add a tool to your agent (Example 2)
3. Implement session memory for multi-turn conversations (Example 4)

### For Intermediate Users
1. Implement multi-agent handoffs (Example 3)
2. Use structured outputs with Pydantic models (Example 5)
3. Add guardrails for safety (Example 7)
4. Explore streaming for better UX (Example 8)

### For Advanced Users
1. Integrate MCP servers for external tools (Example 9)
2. Build nested agent architectures (Example 10)
3. Use LiteLLM for provider-agnostic deployments (Example 6)
4. Check `references/releases.md` for breaking changes in v0.6.0 (handoff behavior changed)

## Important Notes

### Breaking Changes in v0.6.0
- **Handoff behavior changed**: Message history is now collapsed into a single message when handing off. Test before upgrading.

### Requirements
- Python 3.9 or newer
- `openai` package v2.x (v1.x no longer supported as of v0.4.0)
- Set `OPENAI_API_KEY` environment variable

### Installation
```bash
pip install openai-agents
# For voice support:
pip install 'openai-agents[voice]'
# For Redis sessions:
pip install 'openai-agents[redis]'
```

---

**Skill Version:** Based on openai-agents-python v0.6.1 (November 2025)
