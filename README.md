# AI Actuary

An actuarial manager agent system that automates 80-95% of actuarial workstreams while maintaining hard governance gates for professional sign-off, independence, confidentiality, and auditability.

## Architecture Overview

The system operates on two planes:

- **Control Plane (Agentic Orchestration)**: OpenAI Agents SDK decides what to do, when, and why
- **Data/Compute Plane (Deterministic Execution)**: ETL, actuarial models, reports, dashboards, and approvals via tools and services

```
[Triggers/UI] ---> [Orchestrator API (Python + Agents SDK)]
                      |  (sessions, tracing, guardrails)
                      |
                      +--> [Tool Gateway]
                      |       |-- Python function tools (internal APIs)
                      |       |-- MCP servers (internal tool bundles)
                      |       |-- Codex MCP server (long-running tasks)
                      |
                      +--> [Knowledge + Retrieval]
                      |       |-- Vector store (methods, templates, prior work)
                      |       |-- Web search (regulatory updates, market data)
                      |
                      +--> [Model Execution Service]
                      |       |-- Reserving / IFRS17 / ALM / Credit models
                      |       |-- Job scheduler + artefact store
                      |
                      +--> [Document & BI Output]
                      |       |-- Word/PDF/PPT generator
                      |       |-- Power BI / Tableau refresh hooks
                      |
                      +--> [Governance]
                              |-- approvals workflow
                              |-- independence/confidentiality checks
                              |-- audit trails (trace_id, artefact hashes)
```

## Tech Stack

### Frontend
- **Next.js 16** with App Router
- **Supabase** for authentication and database
- **Tailwind CSS** with Radix UI components
- **TypeScript**

### Backend (Python)
- **OpenAI Agents SDK** for multi-agent orchestration
- **FastAPI** for API endpoints
- **Codex CLI** as MCP server for long-running tasks
- **SQLAlchemy** for session persistence

## Key Concepts

### OpenAI Agents SDK Components

| Concept | Description |
|---------|-------------|
| **Agent** | An LLM configured with instructions, tools, guardrails, and handoffs |
| **Runner** | Executes agents in a loop until final output is produced |
| **Handoff** | Transfers control from one agent to another |
| **Session** | Manages conversation history across multiple runs |
| **Guardrail** | Safety checks for input/output validation |
| **Tracing** | Built-in tracking for debugging and optimization |

### Agent Team Design

**Top-Level: Engagement Manager Agent**
- Intake and classify requests (monthly close, pricing, IFRS17 build, M&A due diligence)
- Plan workflow and allocate tasks
- Own the run state (what's done, what's blocked, what needs approval)
- Synthesise final narrative outputs

**Specialist Agents:**
1. **Data Quality and Reconciliation Agent** - ETL checks, triangle reconciliation, completeness checks
2. **Reserving Agent** - Method selection, model runs, sensitivity analysis
3. **IFRS17 Agent** - Model output mapping, disclosure tables, traceability
4. **ALM and Reinsurance Agent** - Scenario tests, reinsurance optimisation
5. **Banking and Credit Risk Agent** - ECL models, stress tests, governance documentation
6. **Reporting and Visualisation Agent** - Memos, board decks, exhibits
7. **PMO Agent** - Timelines, task assignment, progress reporting
8. **Compliance and Ethics Agent** - Confidentiality, independence constraints
9. **QA Reviewer Agent** - Second pair of eyes, consistency checks

## Governance by Design

### Three-Layer Governance

1. **Policy Guardrails (Blocking)**
   - Check request is in scope
   - Verify actor permissions for client/engagement
   - Block expensive runs that should not start

2. **Work-Product Guardrails (Output Tripwires)**
   - Required sections exist (assumptions, limitations, reconciliation, methods, sensitivity)
   - Every number references a model artefact or data source
   - Disclaimers and independence wording present where required

3. **Approval Workflow (Hard Gate)**
   - "Approval required" metadata on artefacts
   - Agent prepares everything, then requests approval
   - Distribution only after approval tool returns approved

## Example Workflows

### Monthly Reserving Cycle
1. Engagement Manager creates/loads session
2. Data Quality Agent runs validations and reconciliations
3. If issues: PMO Agent creates tasks, blocks downstream modelling
4. Reserving Agent selects methods, runs models, produces analysis
5. QA Reviewer Agent checks consistency
6. Reporting Agent assembles reserve memo
7. Output guardrails + approval gate before distribution

### IFRS 17 Quarterly Disclosure Pack
1. Data Quality Agent validates ledger and policy data
2. IFRS17 Agent produces CSM, RA, fulfilment cashflow tables
3. Reporting Agent assembles disclosure tables and narrative
4. QA Reviewer cross-checks against ledger
5. Approval gate before external distribution

### Client Advisory Request
1. Engagement Manager classifies as scenario analysis
2. ALM/Reinsurance Agent and Reserving Agent run modelling
3. Reporting Agent produces board-ready summary
4. Compliance Agent checks scope, disclaimers

## Getting Started

### Prerequisites
- Node.js 18+
- pnpm
- Python 3.10+
- Supabase account

### Installation

```bash
# Install frontend dependencies
pnpm install

# Set up environment variables
cp .env.example .env
# Edit .env with your Supabase credentials

# Run development server
pnpm dev
```

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run backend API
uvicorn api.main:app --reload --port 8000
```

The frontend reads the backend base URL from `NEXT_PUBLIC_API_URL`
(defaults to `http://localhost:8000`).

### Environment Variables

```env
NEXT_PUBLIC_SUPABASE_URL=your-project-url
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-publishable-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
my-ai-actuary/
├── app/                    # Next.js App Router pages
├── components/             # React components (Radix UI)
├── lib/                    # Utility functions and Supabase client
├── backend/               # Python backend (to be created)
│   ├── agents/            # OpenAI Agents SDK agent definitions
│   ├── tools/             # Function tools and MCP servers
│   ├── services/          # Business logic services
│   ├── models/            # Actuarial model wrappers
│   └── api/               # FastAPI endpoints
└── .claude/               # Claude Code skills (to be created)
    └── skills/
        ├── openai-agents-sdk/
        ├── fastapi/
        └── actuarial/
```

## Build Roadmap

### Phase 1: One Workflow, One Client, One Line of Business
- Monthly reserving close workflow only
- Read-only data tools + model run submission + memo drafting
- Tracing, sessions, and output guardrails from day one

### Phase 2: Add Governance and PMO Automation
- Approval workflow integration
- Task generation and milestone tracking
- QA reviewer agent with deterministic checklists

### Phase 3: Expand Actuarial Domains
- IFRS17 pack and ALM/reinsurance modules
- Retrieval over methods library and templates

### Phase 4: Scale-Out and Harden
- MCP servers for tool bundles
- Strong access controls and auditing
- Regression tests and evals per workflow

## Security Considerations

- **Least Privilege**: Network access off by default, workspace-only writes
- **Approval Policies**: Configurable per call (on-request, never, etc.)
- **Shell Environment Policy**: Restrict forwarded environment variables
- **Execution Policy Rules**: Allow/prompt/forbidden rules for command prefixes

## Observability and Audit

1. **OpenAI Agents SDK Trace**
   - Records agent runs: generations, tool calls, handoffs, guardrails
   - Trace metadata: engagement_id, period, workflow_name
   - Configurable sensitive data capture

2. **Enterprise Audit Record**
   - Model run manifests (input hash, parameter set, code version, output hash)
   - Approvals history (who approved, when, what artefact hash)
   - Distribution logs (who received what, when)

## License

Private - All Rights Reserved

## References

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [Codex CLI](https://developers.openai.com/codex)
- [MCP Protocol](https://modelcontextprotocol.github.io/python-sdk/)
- [Supabase](https://supabase.com/docs)
- [Next.js](https://nextjs.org/docs)
