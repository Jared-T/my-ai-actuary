# CLAUDE.md

Project-specific instructions for Claude Code CLI.

## Project Overview

AI Actuary is an actuarial manager agent system using:
- **OpenAI Agents SDK** (Python) for multi-agent orchestration
- **Codex CLI** as MCP server for long-running, auditable tasks
- **Next.js 16 + Supabase** for frontend and authentication
- **FastAPI** for backend API

## Single-User Development Policy

This is a single-user project. The owner is the only user, so:

- **No legacy code support** - Remove deprecated patterns; don't maintain backwards compatibility
- **No fallbacks** - Code should work correctly or fail explicitly; no graceful degradation
- **No browser compatibility polyfills** - Target latest Chrome/Safari only
- **No migration paths** - Break things when needed; start fresh if simpler
- **No defensive coding for other users** - Skip permission systems, user preferences toggles, and multi-tenant patterns
- **Dark mode only** - No theme system needed

When in doubt: keep it simple, break what's broken, and optimize for the single user.

## Directory Structure

```
my-ai-actuary/
├── app/                    # Next.js App Router
├── components/             # React components (Radix UI + shadcn)
├── lib/                    # Supabase client, utilities
├── backend/               # Python backend
│   ├── agents/            # OpenAI Agents SDK definitions
│   │   ├── engagement_manager.py
│   │   ├── data_quality.py
│   │   ├── reserving.py
│   │   ├── ifrs17.py
│   │   ├── alm_reinsurance.py
│   │   ├── reporting.py
│   │   ├── pmo.py
│   │   ├── compliance.py
│   │   └── qa_reviewer.py
│   ├── tools/             # Function tools and MCP servers
│   ├── services/          # Business logic
│   ├── models/            # Actuarial model wrappers
│   └── api/               # FastAPI endpoints
└── .claude/skills/        # Claude Code skills
```

## Development Commands

```bash
# Frontend
pnpm dev                    # Start Next.js dev server
pnpm build                  # Production build
pnpm lint                   # Run ESLint

# Backend (once created)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

## Code Style Rules

### TypeScript/React (Frontend)
- Use TypeScript strict mode
- Prefer functional components with hooks
- Use early returns over nested conditions
- Keep components under 200 lines; split if larger
- Use Tailwind CSS utility classes, avoid inline styles
- Import order: React, Next.js, external libs, internal modules, styles

### Python (Backend)
- Python 3.10+, PEP 8, 4-space indents
- Type hints required on all function signatures
- Concise docstrings for public functions
- Keep files under 500 lines; refactor if larger
- Use `@function_tool` decorator for agent tools
- Absolutely no silent fallbacks - fail explicitly

### Naming Conventions
- **AVOID** generic names: `utils`, `helpers`, `common`, `shared`
- **USE** domain-specific names: `ReserveCalculator`, `ClaimsTriangleBuilder`, `IFRS17DisclosureMapper`
- Modules/filenames in `snake_case`
- Constants in `UPPER_SNAKE_CASE`
- React components in `PascalCase`

## Agent Implementation Patterns

### Creating a New Agent

```python
from agents import Agent, Runner, function_tool

@function_tool
def fetch_claims_data(period: str, line_of_business: str) -> dict:
    """Fetch claims data for a specific period and LOB."""
    # Implementation here
    pass

reserving_agent = Agent(
    name="Reserving Agent",
    instructions="""You are a reserving specialist. Your responsibilities:
    - Select appropriate reserving methods per segment
    - Request model runs and interpret diagnostics
    - Produce sensitivity analysis with commentary

    Always reference model artefacts for any numerical outputs.
    Never produce numbers without a traceable source.""",
    tools=[fetch_claims_data],
)
```

### Handoff Pattern (Manager → Specialist)

```python
engagement_manager = Agent(
    name="Engagement Manager",
    instructions="Route requests to appropriate specialist agents.",
    handoffs=[reserving_agent, ifrs17_agent, reporting_agent],
)
```

### Agents as Tools Pattern (Specialist as Callable)

```python
writer_agent = Agent(
    name="Report Writer",
    instructions="Write actuarial memos and reports.",
    tools=[
        reserving_agent.as_tool(
            tool_name="get_reserve_analysis",
            tool_description="Get reserve analysis for a period"
        )
    ],
)
```

## Guardrail Implementation

### Input Guardrail (Permission Check)

```python
from agents import Agent, InputGuardrail, GuardrailFunctionOutput

async def check_engagement_permission(ctx, agent, input_text):
    """Verify user has permission for this engagement."""
    engagement_id = extract_engagement_id(input_text)
    if not user_has_access(ctx.user_id, engagement_id):
        return GuardrailFunctionOutput(
            output_info={"reason": "No access to engagement"},
            tripwire_triggered=True,
        )
    return GuardrailFunctionOutput(tripwire_triggered=False)

agent = Agent(
    name="Engagement Manager",
    input_guardrails=[
        InputGuardrail(guardrail_function=check_engagement_permission)
    ],
)
```

### Output Guardrail (Artefact Reference Check)

```python
async def check_artefact_references(ctx, agent, output):
    """Ensure all numbers reference model artefacts."""
    numbers = extract_numbers(output)
    for num in numbers:
        if not has_artefact_reference(num):
            return GuardrailFunctionOutput(
                output_info={"reason": f"Number {num} has no artefact reference"},
                tripwire_triggered=True,
            )
    return GuardrailFunctionOutput(tripwire_triggered=False)
```

## Supabase Integration

### Database Schema (to be created)

```sql
-- Engagements
create table engagements (
  id uuid primary key default gen_random_uuid(),
  client_code text not null,
  name text not null,
  status text default 'active',
  created_at timestamptz default now()
);

-- Workflow Runs
create table workflow_runs (
  id uuid primary key default gen_random_uuid(),
  engagement_id uuid references engagements(id),
  workflow_type text not null,
  period text not null,
  status text default 'pending',
  trace_id text,
  created_at timestamptz default now()
);

-- Artefacts
create table artefacts (
  id uuid primary key default gen_random_uuid(),
  workflow_run_id uuid references workflow_runs(id),
  type text not null,
  name text not null,
  hash text not null,
  storage_path text not null,
  created_at timestamptz default now()
);

-- Approvals
create table approvals (
  id uuid primary key default gen_random_uuid(),
  artefact_id uuid references artefacts(id),
  approver_id uuid references auth.users(id),
  status text not null,
  notes text,
  created_at timestamptz default now()
);
```

## HTTPException Handling Pattern

```python
from fastapi import HTTPException

try:
    result = await process_request(data)
except HTTPException:
    raise  # Re-raise, don't wrap
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

## Null Safety Pattern

```python
total_tokens += result.performance.total_tokens or 0
```

## Environment Variables

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-key

# OpenAI (backend)
OPENAI_API_KEY=sk-xxx

# Tracing (optional)
AGENTS_TRACING_DISABLED=1
AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=0
```

## Testing Guidelines

- Framework: pytest for backend, vitest for frontend
- Add tests for new agent wiring and prompt behaviors
- Run `pytest` before finishing work
- Include test results in PR descriptions

## Things You Must Never Do

- Never add fallbacks or alternate execution paths without explicit approval
- Never produce actuarial numbers without referencing a model artefact
- Never bypass approval gates for regulated deliverables
- Do not add dependencies without approval
- Stay on-task - no unsolicited features beyond the requested scope
- Never expose sensitive client data in traces or logs

## Docs Map

- Product overview, architecture, roadmap: `README.md`
- Claude-specific runtime notes: `CLAUDE.md` (this file)
- Agent SDK reference: `.claude/skills/openai-agents-sdk/SKILL.md`
- FastAPI patterns: `.claude/skills/fastapi/SKILL.md`
