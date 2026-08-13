# Multi-Agent Support Triage API

Production-style FastAPI service demonstrating multi-agent LLM orchestration with LangGraph,
Pydantic contracts, LangChain prompt composition, optional AWS Bedrock support, and Langfuse tracing.

[![CI](https://github.com/LordKay-sudo/multi-agent-support-triage-api/actions/workflows/ci.yml/badge.svg)](https://github.com/LordKay-sudo/multi-agent-support-triage-api/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Portfolio](https://img.shields.io/badge/portfolio-portfolio.lordkay.com-38bdf8)](https://portfolio.lordkay.com)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab?logo=python&logoColor=white)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](app/main.py)
[![LangGraph](https://img.shields.io/badge/LangGraph-agents-1C3C3C)](pyproject.toml)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-e92063?logo=pydantic&logoColor=white)](pyproject.toml)
[![Langfuse](https://img.shields.io/badge/Langfuse-tracing-000000?logo=langfuse&logoColor=white)](pyproject.toml)
[![AWS Bedrock](https://img.shields.io/badge/AWS_Bedrock-optional-FF9900?logo=amazonaws&logoColor=white)](pyproject.toml)

The demo takes an incoming support ticket and routes it through a small agent workflow:

1. Classifier agent identifies category and priority.
2. Supervisor agent decides whether risk review is required.
3. Risk review agent adds controls for high-impact cases.
4. Retrieval agent pulls local support guidance.
5. Planner agent creates recommended next actions.
6. Drafting agent prepares a customer-facing response.
7. Escalation agent decides whether the ticket should be escalated.

## Why This Exists

This repository is designed as a compact portfolio project for production AI engineering roles. It
shows how to expose a multi-agent workflow through an API while keeping the app testable, observable,
and runnable without cloud credentials.

## Production Engineering Signals

- Versioned API routes under `/api/v1`
- Strict Pydantic request models with bounded input sizes
- Idempotent triage endpoint with an explicit `force=true` override
- Thread-safe in-memory repository for local/demo execution
- Request ID middleware for traceability across API calls
- Deterministic mock LLM for tests and CI
- Optional Bedrock provider abstraction for real LLM calls
- Optional Langfuse export with trace/session/user metadata

## Architecture

```mermaid
flowchart LR
    Client[Client] --> API[FastAPI API]
    API --> Store[Ticket Store]
    API --> Graph[LangGraph Workflow]
    Graph --> Classifier[Classifier]
    Classifier --> Supervisor[Supervisor]
    Supervisor -->|high risk| Risk[Risk Review]
    Supervisor -->|standard| Retrieval[Guidance Retrieval]
    Risk --> Retrieval
    Retrieval --> Planner[Action Planner]
    Planner --> Drafting[Response Drafting]
    Drafting --> Escalation[Escalation Decision]
    Graph --> Tracing[Langfuse Trace Export]
```

## Tech Stack

- Python 3.11+
- FastAPI
- Pydantic
- LangGraph
- LangChain Core
- Langfuse
- Optional AWS Bedrock via `langchain-aws`
- Pytest and Ruff

## Project Structure

```text
app/
  agents/       LangGraph state, nodes, and compiled workflow
  core/         settings and logging
  models/       Pydantic request/response models
  services/     LLM provider, knowledge base, tracing, and ticket store
  api.py        FastAPI routes
  main.py       FastAPI application entrypoint
examples/       Sample support ticket payloads and demo output
scripts/        Local demo and smoke-check utilities
tests/          API and graph tests
```

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
cp .env.example .env
make dev
```

Open the API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

## One-Command Demo

Run a complete ticket triage flow without starting a server:

```bash
make demo
```

The demo loads `examples/support_ticket.json`, creates a ticket through the FastAPI app, runs the
LangGraph triage workflow, and prints a compact JSON summary. A shortened example output is stored
in `examples/demo_output.json`.

To run the same demo against a live API:

```bash
python3 scripts/demo_request.py --base-url http://localhost:8000
```

## Example Request

Create a ticket:

```bash
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "cust_123",
    "subject": "Cannot access account before payroll",
    "description": "I am locked out after MFA setup and payroll closes today.",
    "channel": "email"
  }'
```

Run triage:

```bash
curl -X POST http://localhost:8000/api/v1/tickets/{ticket_id}/triage
```

Example response shape:

```json
{
  "status": "triaged",
  "report": {
    "category": "account",
    "priority": "high",
    "confidence": 0.78,
    "recommended_actions": [
      "Route to a senior support owner for same-day review.",
      "Verify identity before changing account access.",
      "Respond using the high priority support SLA."
    ],
    "escalate": true,
    "workflow_path": ["classifier", "supervisor", "risk_review", "retrieval", "planner", "drafting", "escalation"]
  }
}
```

## Configuration

The default `LLM_PROVIDER=mock` gives deterministic responses and needs no API keys.

To use AWS Bedrock:

```bash
python3 -m pip install -e ".[bedrock]"
```

Then set:

```env
LLM_PROVIDER=bedrock
AWS_REGION=eu-west-2
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
```

To enable Langfuse tracing, configure:

```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Quality Checks

```bash
make lint
make test
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```
