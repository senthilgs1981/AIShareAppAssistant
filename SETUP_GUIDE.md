# Building InterestCalculator From Scratch

This is a Google ADK (Agent Development Kit) agent, served over FastAPI, that
answers finance questions and calculates simple interest, compound interest,
and the difference between the two. This guide walks through recreating the
project from an empty folder: which files to create, in what order, what
commands to run, and how the code is layered.

## 1. Prerequisites

- Python 3.12 (matches the `Dockerfile` base image)
- An OpenAI API key (the agent is routed through LiteLLM to an OpenAI model)

## 2. Project layout

```
InterestCalculator/
├── __init__.py                # marks the repo root as a package (for `agents_dir` discovery)
├── api.py                     # FastAPI entrypoint / app layer
├── requirements.txt           # dependency layer
├── Dockerfile                 # infra / deployment layer
└── fin_assistant/             # agent package
    ├── __init__.py            # exposes `agent` submodule to ADK
    ├── agent.py                # agent + tools (business logic layer)
    └── .env                    # secrets/config (OPENAI_API_KEY, MODEL_NAME)
```

`.adk/session.db` and `fin_assistant/.adk/session.db` are generated at
runtime by ADK to persist chat sessions — you don't create these by hand.

## 3. Step-by-step build order

### Step 1 — Initialize the folder and virtual environment

```bash
mkdir InterestCalculator && cd InterestCalculator
python3.12 -m venv .venv
source .venv/bin/activate
```

### Step 2 — Declare dependencies

Create `requirements.txt`:

```
google-adk
litellm
fastapi
uvicorn[standard]
sqlalchemy
python-dotenv
```

Install them:

```bash
pip install -r requirements.txt
```

### Step 3 — Create the agent package

```bash
mkdir fin_assistant
touch fin_assistant/__init__.py
```

`fin_assistant/__init__.py` just re-exports the agent module so ADK's
autodiscovery can find `root_agent`:

```python
from . import agent
```

### Step 4 — Write the agent and its tools

`fin_assistant/agent.py` — this is the core business-logic layer:

- Configures the model via `LiteLlm`, reading `MODEL_NAME` (and an
  `OPENAI_API_KEY` fallback) from the environment.
- Defines three plain Python functions as **tools**: `calculate_simple_interest`,
  `calculate_compound_interest`, `interest_difference`. ADK turns a
  function's docstring + signature into a tool schema automatically.
- Builds `root_agent = Agent(...)`, wiring the model, an instruction prompt
  that scopes the assistant to finance questions, and the tool list.

### Step 5 — Add environment config

Create `fin_assistant/.env` (never commit this — add it to `.gitignore`):

```
OPENAI_API_KEY=sk-...
MODEL_NAME=openai/gpt-4o-mini
```

### Step 6 — Write the FastAPI app layer

`api.py` at the repo root — this is the transport/API layer, thin on
purpose:

- Calls ADK's `get_fast_api_app(agents_dir=..., web=True)` to get a fully
  wired FastAPI app (chat endpoints, session storage, and the ADK web UI)
  built from every agent package found under `agents_dir`.
- Adds two small custom routes on top: `GET /health` and `GET /agent-info`.
- Runs via `uvicorn` on port `9999` when executed directly.

### Step 7 — Add the root `__init__.py`

An empty `__init__.py` at the repo root lets `agents_dir=BASE_DIR` in
`api.py` treat the project root as a package during agent discovery.

### Step 8 — Containerize

`Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 9999
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "9999"]
```

## 4. Commands to run it

**Local dev (with ADK's own CLI, hot web UI):**

```bash
adk web fin_assistant
```

**Local dev (via the FastAPI wrapper in `api.py`):**

```bash
python api.py
# or
uvicorn api:app --reload --port 9999
```

Then check:

```bash
curl http://localhost:9999/health
curl http://localhost:9999/agent-info
```

**Docker:**

```bash
docker build -t interest-calculator .
docker run --env-file fin_assistant/.env -p 9999:9999 interest-calculator
```

## 5. How the code is layered

| Layer | File(s) | Responsibility |
|---|---|---|
| **Config/Secrets** | `fin_assistant/.env`, `requirements.txt` | Environment variables and pinned dependencies — nothing here knows about agents or HTTP. |
| **Agent / Domain logic** | `fin_assistant/agent.py` | The actual "business logic": interest-calculation functions and the `Agent` definition (model, instructions, tools). This layer has no HTTP or server concerns — it could be imported and tested standalone. |
| **API / Transport** | `api.py` | Wraps the agent in a web server. Delegates almost everything to ADK's `get_fast_api_app`, and adds a couple of app-specific HTTP endpoints (`/health`, `/agent-info`). Depends on the agent layer, not vice versa. |
| **Packaging** | `__init__.py`, `fin_assistant/__init__.py` | Makes the folders importable packages so ADK's file-based agent discovery (`agents_dir`) can find `root_agent`. |
| **Runtime state** | `.adk/session.db` | Auto-generated session storage; not authored by hand, produced by the ADK server layer. |
| **Infra / Deployment** | `Dockerfile` | Packages the above layers into a container image; no application logic lives here. |

The dependency direction is one-way: **Infra → API → Agent → Config**. The
agent layer never imports from `api.py`, which keeps the tools and model
logic testable independent of the web server.

## 6. Extending the project

- **New tool**: add a plain function with a clear docstring in
  `fin_assistant/agent.py`, then append it to the `tools=[...]` list on
  `root_agent`.
- **New agent**: add a new package under the repo root (sibling to
  `fin_assistant/`) with its own `__init__.py` and `agent.py` — ADK's
  `agents_dir` discovery will pick it up automatically.
- **New HTTP endpoint**: add a route in `api.py` alongside `/health` and
  `/agent-info`.
