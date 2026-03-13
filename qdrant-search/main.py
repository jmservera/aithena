#!/usr/bin/env python
# encoding: utf-8
import aiohttp
from enum import Enum
from fastapi.staticfiles import StaticFiles
from pydantic.dataclasses import dataclass
from pydantic import BaseModel, Field
from qdrant_client import models, QdrantClient
from config import *
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
import json
from typing import Optional

app = FastAPI(title="api " + TITLE, version=VERSION)
api_app = FastAPI(title=TITLE, version=VERSION)
origins = ["http://localhost:5173"]

app.mount("/v1", api_app)
app.mount("/", StaticFiles(directory="static", html=True), name="assets")

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Search mode
# ---------------------------------------------------------------------------

class SearchMode(str, Enum):
    keyword = "keyword"
    semantic = "semantic"
    hybrid = "hybrid"


# ---------------------------------------------------------------------------
# Normalized result models
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """Normalized search result shared by all search modes."""
    id: str
    score: float
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    file_path: Optional[str] = None
    folder_path: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    highlights: list[str] = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Normalized search response payload shared by all search modes."""
    query: str
    mode: SearchMode
    total: int
    results: list[SearchResult]
    facets: dict = Field(default_factory=dict)
    highlights: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# LLM model properties
# ---------------------------------------------------------------------------

class ModelProperties(BaseModel):
    prompt: str = None
    suffix: str = None
    max_tokens: int = 2048
    temperature: float = 0.8
    top_p: float | None
    mirostat_mode: int | None
    mirostat_tau: int | None
    mirostat_eta: float | None
    stream: bool | None
    presence_penalty: float | None
    frequency_penalty: float | None
    n: float | None
    best_of: int | None
    top_k: int | None
    repeat_penalty: float | None
    stop: list | None = ["###"]


class ChatInput(BaseModel):
    input: str
    limit: int = 10
    model_properties: ModelProperties = ModelProperties()


# ---------------------------------------------------------------------------
# Embeddings helper
# ---------------------------------------------------------------------------

async def get_embeddings_async(text):
    """Get embeddings for a text from embeddings service"""
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/v1/embeddings/",
            json={"input": text},
        ) as resp:
            return await resp.json()


# ---------------------------------------------------------------------------
# LLM completion helper
# ---------------------------------------------------------------------------

async def get_completion_async(context: str, question: str, props: ModelProperties):
    # TODO: create prompts by language (e.g. English, German, Spanish, Catalan, etc.)

    prompts = [
        f"### Context:{context}\n\n###\n Instructions:\nAnswer the following based on the provided context:\n{question}\n\n### Response:\n",
        f"### Context:{context}\n\n###\n Instructions:\n{question}\n\n### Response:\n",
        f"""
### Instruction:

You are an assistant that summarizes provided content that answers a question from the user. Write a response that appropriately completes the request.

Write a detailed summary from the provided Input that answers the provided Question. Let's think step by step.

### Question:

{question}

### Input:

{context}

### Response:
""",
    ]

    props.prompt = prompts[0]
    props.stop = ["###"]
    props_dict = props.dict(exclude_none=True)
    print(props_dict)

    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{CHAT_HOST}:{CHAT_PORT}/v1/completions",
            json=props_dict,
            headers={
                "Content-Type": "application/json",
                "X-Accel-Buffering": "no",
                "Accept": "text/event-stream",
            },
        ) as resp:
            async for line in resp.content:
                if line.strip() == b"data: [DONE]":
                    return
                yield line.decode("utf-8")


# ---------------------------------------------------------------------------
# Keyword search (Solr BM25)
# ---------------------------------------------------------------------------

async def _solr_keyword_search(query: str, limit: int) -> SearchResponse:
    """Query Solr using BM25 keyword search and return a normalized SearchResponse."""
    params = {
        "q": query,
        "defType": "edismax",
        "qf": "title_t^2 author_t^1.5 _text_",
        "rows": limit,
        "hl": "true",
        "hl.fl": "content",
        "hl.snippets": 2,
        "hl.fragsize": 200,
        "facet": "true",
        "facet.field": ["author_s", "category_s", "language_detected_s"],
        "facet.mincount": 1,
        "fl": "id,title_s,author_s,year_i,file_path_s,folder_path_s,category_s,language_detected_s,score",
        "wt": "json",
    }

    solr_url = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{SOLR_COLLECTION}/select"

    async with aiohttp.ClientSession() as session:
        async with session.get(solr_url, params=params) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(
                    status_code=502,
                    detail=f"Solr error {resp.status}: {body[:200]}",
                )
            data = await resp.json()

    response_body = data.get("response", {})
    raw_docs = response_body.get("docs", [])
    total = response_body.get("numFound", len(raw_docs))
    hl_data = data.get("highlighting", {})
    facet_data = {}
    raw_facets = data.get("facet_counts", {}).get("facet_fields", {})
    for field, counts in raw_facets.items():
        # Solr returns [value, count, value, count, ...] — always pairs
        facet_data[field] = {
            counts[i]: counts[i + 1]
            for i in range(0, len(counts) - 1, 2)
            if counts[i + 1] > 0
        }

    results = []
    for doc in raw_docs:
        doc_id = doc.get("id", "")
        snippets = hl_data.get(doc_id, {}).get("content", [])
        results.append(
            SearchResult(
                id=doc_id,
                score=float(doc.get("score", 0.0)),
                title=doc.get("title_s"),
                author=doc.get("author_s"),
                year=doc.get("year_i"),
                file_path=doc.get("file_path_s"),
                folder_path=doc.get("folder_path_s"),
                category=doc.get("category_s"),
                language=doc.get("language_detected_s"),
                highlights=snippets,
                payload={k: v for k, v in doc.items() if k != "score"},
            )
        )

    return SearchResponse(
        query=query,
        mode=SearchMode.keyword,
        total=total,
        results=results,
        facets=facet_data,
        highlights={doc_id: hl for doc_id, hl in hl_data.items()},
    )


# ---------------------------------------------------------------------------
# Semantic search (Qdrant vector)
# ---------------------------------------------------------------------------

async def _qdrant_semantic_search(query: str, limit: int) -> SearchResponse:
    """Query Qdrant using vector similarity and return a normalized SearchResponse."""
    embedding = await get_embeddings_async(query)

    if not (embedding and "data" in embedding and len(embedding["data"]) > 0):
        raise HTTPException(status_code=400, detail="embedding is None or has no data")

    hits = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=embedding["data"][0]["embedding"],
        limit=limit,
    )

    results = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            SearchResult(
                id=str(hit.id),
                score=float(hit.score),
                title=payload.get("title_s") or payload.get("title"),
                author=payload.get("author_s") or payload.get("author"),
                year=payload.get("year_i") or payload.get("year"),
                file_path=payload.get("file_path_s") or payload.get("path"),
                folder_path=payload.get("folder_path_s"),
                category=payload.get("category_s"),
                language=payload.get("language_detected_s"),
                highlights=[],
                payload=payload,
            )
        )

    return SearchResponse(
        query=query,
        mode=SearchMode.semantic,
        total=len(results),
        results=results,
        facets={},
        highlights={},
    )


# ---------------------------------------------------------------------------
# Hybrid search (Reciprocal Rank Fusion)
# ---------------------------------------------------------------------------

def _reciprocal_rank_fusion(
    keyword_results: list[SearchResult],
    semantic_results: list[SearchResult],
    k: int = RRF_K,
) -> list[SearchResult]:
    """
    Combine keyword and semantic result lists using Reciprocal Rank Fusion (RRF).

    RRF score for a document d across ranked lists is:
        sum_over_lists( 1 / (k + rank(d, list)) )

    where rank is 1-based.  Higher combined score → better rank.
    """
    scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    for rank, result in enumerate(keyword_results, start=1):
        scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (k + rank)
        result_map[result.id] = result

    for rank, result in enumerate(semantic_results, start=1):
        scores[result.id] = scores.get(result.id, 0.0) + 1.0 / (k + rank)
        if result.id not in result_map:
            result_map[result.id] = result

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    fused = []
    for doc_id, rrf_score in ranked:
        r = result_map[doc_id]
        fused.append(
            SearchResult(
                id=r.id,
                score=rrf_score,
                title=r.title,
                author=r.author,
                year=r.year,
                file_path=r.file_path,
                folder_path=r.folder_path,
                category=r.category,
                language=r.language,
                highlights=r.highlights,
                payload=r.payload,
            )
        )
    return fused


async def _hybrid_search(query: str, limit: int) -> SearchResponse:
    """
    Run keyword and semantic searches in parallel, fuse with RRF, and return
    a normalized SearchResponse.

    Facets and highlights are sourced from the keyword leg only.  Semantic-only
    results are included in the merged list but will have empty highlights.
    """
    # Fetch more candidates from each leg so RRF has good input
    candidate_limit = max(limit * 2, 20)

    keyword_resp, semantic_resp = await _run_both(query, candidate_limit)

    fused = _reciprocal_rank_fusion(
        keyword_resp.results, semantic_resp.results, k=RRF_K
    )[:limit]

    return SearchResponse(
        query=query,
        mode=SearchMode.hybrid,
        total=len(fused),
        results=fused,
        # Facets and highlights come from the keyword leg; not available for
        # semantic-only hits.  See solr/README.md for degradation details.
        facets=keyword_resp.facets,
        highlights=keyword_resp.highlights,
    )


async def _run_both(query: str, limit: int):
    """Run keyword and semantic search concurrently and return both responses."""
    import asyncio

    kw_task = asyncio.create_task(_solr_keyword_search(query, limit))
    sem_task = asyncio.create_task(_qdrant_semantic_search(query, limit))
    keyword_resp = await kw_task
    semantic_resp = await sem_task
    return keyword_resp, semantic_resp


# ---------------------------------------------------------------------------
# Info / question endpoints (unchanged)
# ---------------------------------------------------------------------------

@dataclass
class info_class:
    title: str
    version: str

    def __init__(self, title: str, version: str):
        self.title = title
        self.version = version


@api_app.get("/info")
async def info() -> info_class:
    return info_class(TITLE, VERSION)


async def generate_question(
    input: str, limit: int, props: ModelProperties = ModelProperties()
):
    embedding = await get_embeddings_async(input)

    if embedding is not None and "data" in embedding and len(embedding["data"]) > 0:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=embedding["data"][0]["embedding"],
            limit=limit,
        )
        messages = []

        context = ""

        for hit in hits:
            context += f"{hit.payload['text']}\n"
            messages.append(
                {
                    "id": hit.id,
                    "payload": hit.payload["text"],
                    "score": hit.score,
                    "path": hit.payload["path"],
                    "page": hit.payload["page"],
                }
            )

        print(context)
        if props.stream:
            yield bytes("data: " + json.dumps({"messages": messages}) + "\n\n", "utf-8")
            async for line in get_completion_async(context, input, props):
                yield bytes(f"{line}\n", "utf-8")
        else:
            syncresult = ""
            async for line in get_completion_async(context, input, props):
                syncresult += line
            resp = json.loads(syncresult)
            resp["messages"] = messages
            yield json.dumps(resp)
    else:
        raise HTTPException(status_code=400, detail="embedding is None or has no data")


async def _question(
    input: str, limit: int = 10, props: ModelProperties = ModelProperties()
):
    # todo: receive config from request
    if not input is None and len(input) > 0:
        if props.stream:
            return StreamingResponse(
                generate_question(input, limit, props),
                media_type="text/event-stream",
            )  # application/json
        else:
            async for line in generate_question(input, limit, props):
                return line
    else:
        raise HTTPException(status_code=400, detail="no input provided")


@api_app.get("/question/")
async def question(
    input: str, limit: int = 10, props: ModelProperties = ModelProperties()
):
    return await _question(input, limit, props)


@api_app.post("/question/")
async def question(input: ChatInput):
    return await _question(input.input, input.limit, input.model_properties)


# ---------------------------------------------------------------------------
# Search endpoint — supports keyword (default), semantic, and hybrid modes
# ---------------------------------------------------------------------------

@api_app.get("/search/", response_model=SearchResponse)
async def search(
    input: str,
    limit: int = 5,
    mode: SearchMode = SearchMode(DEFAULT_SEARCH_MODE),
):
    """Search for books.

    - **mode=keyword** (default): BM25 full-text search via Solr.
    - **mode=semantic**: Dense vector similarity search via Qdrant.
    - **mode=hybrid**: Reciprocal Rank Fusion of keyword + semantic results.

    All three modes return the same ``SearchResponse`` payload shape so that
    the UI can consume results uniformly.

    Facets and highlights are populated only in ``keyword`` and ``hybrid``
    modes (sourced from the Solr leg).  In ``semantic`` mode both fields are
    returned as empty objects.  See ``solr/README.md`` for full details.
    """
    if not input or len(input) == 0:
        raise HTTPException(status_code=400, detail="no input provided")

    if mode == SearchMode.keyword:
        return await _solr_keyword_search(input, limit)
    elif mode == SearchMode.semantic:
        return await _qdrant_semantic_search(input, limit)
    else:
        return await _hybrid_search(input, limit)


# ---------------------------------------------------------------------------
# Qdrant client (lazy — only needed for semantic / hybrid modes)
# ---------------------------------------------------------------------------

qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
