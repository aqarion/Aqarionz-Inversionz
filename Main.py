## Directory layout

```text
aqarionz_inversionz/
  app/
    __init__.py
    main.py
    config.py
    api/
      __init__.py
      ideas.py
      health.py
    agents/
      __init__.py
      base.py
      registry.py
    orchestration/
      __init__.py
      pipelines.py
    observability/
      __init__.py
      events.py
      models.py
  tests/
    test_health.py
    test_ideas.py
pyproject.toml
README.md
```

## Core files (starter content)

### app/config.py

```python
from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Aqarionz Inversionz Spine"
    environment: str = "local"
    database_url: str = "sqlite:///./inversionz.db"

    class Config:
        env_file = ".env"


settings = Settings()
```

### app/main.py

```python
from fastapi import FastAPI
from .config import settings
from .api import health, ideas

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="FastAPI multi‑agent orchestration spine for AQARIONZ Inversionz.",
)

app.include_router(health.router, prefix="/api")
app.include_router(ideas.router, prefix="/api")
```

### app/api/health.py

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}
```

### app/agents/base.py

```python
from typing import Protocol, Any, Dict


class AgentContext(Dict[str, Any]):
    """Shared context for a pipeline run."""


class AgentResult(Dict[str, Any]):
    """Structured result from an agent."""


class Agent(Protocol):
    name: str

    async def run(self, payload: Dict[str, Any], ctx: AgentContext) -> AgentResult: ...
```

### app/agents/registry.py

```python
from typing import Dict
from .base import Agent


REGISTRY: Dict[str, Agent] = {}


def register(agent: Agent) -> None:
    REGISTRY[agent.name] = agent


def get_agent(name: str) -> Agent:
    return REGISTRY[name]
```

### app/observability/models.py

```python
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class IdeaRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    idea_text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int
    kind: str
    payload: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### app/observability/events.py

```python
from sqlmodel import Session
from .models import Event


def log_event(
    session: Session, run_id: int, kind: str, payload_json: str
) -> Event:
    event = Event(run_id=run_id, kind=kind, payload=payload_json)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
```

### app/orchestration/pipelines.py

```python
from typing import Dict, Any
from sqlmodel import Session
from ..agents.registry import get_agent
from ..observability.events import log_event
from ..observability.models import IdeaRun


async def run_idea_pipeline(
    session: Session, idea_text: str
) -> Dict[str, Any]:
    run = IdeaRun(idea_text=idea_text)
    session.add(run)
    session.commit()
    session.refresh(run)

    ctx: Dict[str, Any] = {"run_id": run.id, "idea": idea_text}

    research = get_agent("research")
    research_result = await research.run({"idea": idea_text}, ctx)
    # log
    import json

    log_event(session, run.id, "research_result", json.dumps(research_result))

    return {"run_id": run.id, "research": research_result}
```

### app/api/ideas.py

```python
from typing import Any, Dict
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, SQLModel, create_engine

from ..config import settings
from ..orchestration.pipelines import run_idea_pipeline
from ..observability import models  # noqa: F401


router = APIRouter(tags=["ideas"])

engine = create_engine(settings.database_url, echo=False)


def get_session() -> Session:
    with Session(engine) as session:
        yield session


@router.on_event("startup")
def on_startup() -> None:
    SQLModel.metadata.create_all(engine)


class IdeaPayload(BaseModel):
    text: str


@router.post("/ideas")
async def submit_idea(
    payload: IdeaPayload, session: Session = Depends(get_session)
) -> Dict[str, Any]:
    result = await run_idea_pipeline(session, payload.text)
    return result
```

## Basic tests

### tests/test_health.py

```python
from fastapi.testclient import TestClient
from aqarionz_inversionz.app.main import app


client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

### tests/test_ideas.py

```python
from fastapi.testclient import TestClient
from aqarionz_inversionz.app.main import app


client = TestClient(app)


def test_submit_idea():
    r = client.post("/api/ideas", json={"text": "test idea"})
    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body
    assert "research" in body or body == {}  # until agents are wired
```

## pyproject.toml (minimal)

```toml
[project]
name = "aqarionz-inversionz"
version = "0.1.0"
description = "FastAPI multi-agent orchestration spine for AQARIONZ Inversionz."
requires-python = ">=3.11"

dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "sqlmodel",
]

[project.optional-dependencies]
dev = ["pytest", "httpx"]

[tool.pytest.ini_options]
pythonpath = ["."]
```

With this in place, the next move is to implement a simple `research` agent (even a dummy echo agent) and point your CorePrototype UI at `/api/ideas`, giving you the first complete idea → agent → log loop professionals can actually run.[1]

Citations:
[1] 1000010457.jpg https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/images/83180058/02e02dd3-72e8-4c47-aeef-544218d555d8/1000010457.jpg
