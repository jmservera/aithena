---
name: "fastapi-query-params"
description: "FastAPI silently ignores undeclared query parameters — must explicitly declare them"
domain: "api-design"
confidence: "high"
source: "bug discovered in #656: fq_folder sent by frontend but not received by backend"
author: "Parker"
created: "2026-03-21"
last_validated: "2026-03-21"
---

## Context

FastAPI silently ignores query parameters that are not explicitly declared in the endpoint function signature. Unlike Flask or Express, which make all query parameters available via a request object by default, FastAPI only processes parameters that are declared as function arguments or explicitly read from `request.query_params`. This caused a real bug in issue #656 where the frontend was sending `fq_folder` as a query parameter but the backend endpoint never received it — the parameter was silently dropped.

## Patterns

- **Always declare query parameters in the function signature:**
  ```python
  @app.get("/search")
  async def search(q: str, fq_folder: str | None = None, page: int = 1):
      ...
  ```
- **Use `Query()` for validation and documentation:**
  ```python
  from fastapi import Query

  @app.get("/search")
  async def search(
      q: str = Query(..., min_length=1, description="Search query"),
      fq_folder: str | None = Query(None, description="Folder filter"),
  ):
      ...
  ```
- **Use `request.query_params` for dynamic/unknown parameters:**
  ```python
  from fastapi import Request

  @app.get("/search")
  async def search(request: Request):
      all_params = dict(request.query_params)
  ```
- **When adding a new frontend filter, always update the backend endpoint signature** to include the new parameter.

## Examples

```python
# BUG: fq_folder is silently ignored — not in function signature
@app.get("/search")
async def search(q: str):
    # request for /search?q=hello&fq_folder=books → fq_folder is LOST
    ...

# FIX: explicitly declare fq_folder
@app.get("/search")
async def search(q: str, fq_folder: str | None = None):
    # request for /search?q=hello&fq_folder=books → fq_folder = "books"
    ...
```

```python
# Defensive: log unexpected query params for debugging
from fastapi import Request

@app.get("/search")
async def search(request: Request, q: str, fq_folder: str | None = None):
    declared = {"q", "fq_folder"}
    extra = set(request.query_params.keys()) - declared
    if extra:
        logger.warning(f"Unexpected query params: {extra}")
    ...
```

## Anti-Patterns

- **Don't assume all query params are automatically available** — this is the #1 mistake when coming from Flask or Express. FastAPI requires explicit declaration.
- **Don't add a query param to the frontend without updating the backend** — the request will succeed (200 OK) but the parameter will be silently ignored, making the bug hard to detect.
- **Don't rely on integration tests alone to catch this** — unit tests that check the endpoint function signature or OpenAPI schema are more reliable.
- **Don't use `**kwargs` in endpoint signatures** — FastAPI doesn't support it for query parameter collection. Use `request.query_params` instead.
