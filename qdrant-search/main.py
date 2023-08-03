#!/usr/bin/env python
# encoding: utf-8
import time
import aiohttp
from fastapi.staticfiles import StaticFiles
from pydantic.dataclasses import dataclass
from pydantic import BaseModel
from qdrant_client import models, QdrantClient
from config import *
from fastapi.middleware.cors import CORSMiddleware

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
import json

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


class ModelProperties(BaseModel):
    prompt: str = None
    suffix: str = None
    max_tokens: int = 2048
    temperature: float = 0.8
    top_p: float = 0.95
    mirostat_mode: int = 0
    mirostat_tau: int = 5
    mirostat_eta: float = 0.1
    stream: bool = False
    presence_penalty: float = 0
    frequency_penalty: float = 0
    n: float = 1
    best_of: int = 1
    top_k: int = 40
    repeat_penalty: float = 1.1


class ChatInput(BaseModel):
    input: str
    limit: int = 10
    model_properties: ModelProperties = ModelProperties()


async def get_embeddings_async(text):
    """Get embeddings for a text from embeddings service"""
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/v1/embeddings/",
            json={"input": text},
        ) as resp:
            return await resp.json()


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
    print(props)

    # completionRequest = {"messages": messages, "max_tokens": 2048}
    # , "temperature": 0.9, "top_p": 1, "frequency_penalty": 0, "presence_penalty": 0, "best_of": 1, "n": 1, "stream": False, "logprobs": None, "echo": False}
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{CHAT_HOST}:{CHAT_PORT}/v1/completions",
            json=jsonable_encoder(props),
        ) as resp:
            async for line in resp.content:
                if line.strip() == b"data: [DONE]":
                    return
                yield line.decode("utf-8")


@dataclass
class info_class:
    title: str
    version: str

    def __init__(self, title: str, version: str):
        self.title = title
        self.version = version


# @app.get("/")
# def serve_home(request: Request):
#     return templates.TemplateResponse("index.html", context= {"request": request})


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


@api_app.get("/search/")
async def index(input: str, limit: int = 5):
    if not input is None and len(input) != 0:
        embedding = await get_embeddings_async(input)

        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=embedding["data"][0]["embedding"],
            limit=limit,
        )
        results = []
        for hit in hits:
            results.append({"payload": hit.payload, "score": hit.score, "id": hit.id})
        return {"text": input, "results": results}
    else:
        raise HTTPException(status_code=400, detail="no input provided")


qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
