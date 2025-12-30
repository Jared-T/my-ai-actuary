# Repository File Structure

Key directories and files in the openai-agents-python repository.

```
openai-agents-python/
├── src/agents/              # Main SDK source code
│   ├── __init__.py
│   ├── agent.py             # Agent class definition
│   ├── run.py               # Runner implementation
│   ├── tool.py              # Tool definitions
│   ├── guardrail.py         # Guardrail system
│   ├── lifecycle.py         # Lifecycle hooks
│   ├── memory/              # Session implementations
│   │   ├── session.py
│   │   └── sqlite_session.py
│   ├── models/              # Model providers
│   │   ├── interface.py
│   │   ├── openai_responses.py
│   │   └── openai_chatcompletions.py
│   ├── mcp/                 # MCP integration
│   │   ├── server.py
│   │   └── util.py
│   ├── tracing/             # Tracing system
│   │   ├── create.py
│   │   ├── spans.py
│   │   └── processors.py
│   ├── handoffs/            # Handoff logic
│   ├── realtime/            # Realtime/voice agents
│   ├── voice/               # Voice pipeline
│   └── extensions/          # Extensions (LiteLLM, etc.)
│       ├── memory/
│       │   ├── redis_session.py
│       │   ├── sqlalchemy_session.py
│       │   └── encrypt_session.py
│       └── models/
│           └── litellm_model.py
│
├── examples/                # Example implementations
│   ├── basic/               # Hello world, simple agents
│   ├── agent_patterns/      # Common patterns (routing, parallelization)
│   ├── handoffs/            # Multi-agent handoff examples
│   ├── tools/               # Tool usage examples
│   ├── mcp/                 # MCP server examples
│   ├── memory/              # Session examples
│   ├── model_providers/     # LiteLLM, custom providers
│   ├── realtime/            # Voice/realtime examples
│   └── customer_service/    # Full customer service example
│
├── docs/                    # MkDocs documentation
│   ├── agents.md
│   ├── handoffs.md
│   ├── guardrails.md
│   ├── sessions.md
│   ├── tracing.md
│   ├── mcp.md
│   └── models/
│
├── tests/                   # Test suite
│   ├── test_agent_runner.py
│   ├── test_guardrails.py
│   ├── test_session.py
│   └── ...
│
├── pyproject.toml           # Project configuration
├── README.md                # Main documentation
├── Makefile                 # Development commands
└── mkdocs.yml               # Documentation config
```

## Key Source Files

| File | Purpose |
|------|---------|
| `src/agents/agent.py` | Agent class with instructions, tools, handoffs |
| `src/agents/run.py` | Runner.run(), run_sync(), run_streamed() |
| `src/agents/tool.py` | @function_tool decorator, tool definitions |
| `src/agents/guardrail.py` | InputGuardrail, OutputGuardrail |
| `src/agents/memory/session.py` | Session protocol definition |
| `src/agents/mcp/server.py` | MCPServerStdio, MCPServerStreamableHttp |
| `src/agents/tracing/create.py` | Tracing initialization |

## Example Categories

| Directory | Contents |
|-----------|----------|
| `examples/basic/` | Hello world, tools, streaming |
| `examples/agent_patterns/` | Routing, parallelization, deterministic flows |
| `examples/handoffs/` | Multi-agent conversations |
| `examples/memory/` | SQLite, Redis, SQLAlchemy sessions |
| `examples/mcp/` | Filesystem, git, custom MCP servers |
| `examples/model_providers/` | LiteLLM for Claude, Gemini, etc. |
