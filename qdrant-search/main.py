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


async def get_embeddings_async(text):
    """Get embeddings for a text from embeddings service"""
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/v1/embeddings/",
            json={"input": text},
        ) as resp:
            return await resp.json()


async def get_completion_async(context: str, question: str, stream: bool):
    # TODO: create prompts by language (e.g. English, German, Spanish, Catalan, etc.)
    completionRequest = {
        "prompt": f"### Context:{context}\n\n###\n Instructions:\n{question}\n\n### Response:\n",
        "max_tokens": 2048,
        "stop": ["###"],
        "stream": stream,
    }
    print(completionRequest)

    # completionRequest = {"messages": messages, "max_tokens": 2048}
    # , "temperature": 0.9, "top_p": 1, "frequency_penalty": 0, "presence_penalty": 0, "best_of": 1, "n": 1, "stream": False, "logprobs": None, "echo": False}
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{CHAT_HOST}:{CHAT_PORT}/v1/completions",
            json=completionRequest,
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


async def generate_question(input: str, limit: int, stream: bool):
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
        if stream:
            yield bytes("data: " + json.dumps({"messages": messages}) + "\n\n", "utf-8")
            async for line in get_completion_async(context, input, stream):
                yield bytes(f"{line}\n", "utf-8")
        else:
            syncresult = ""
            async for line in get_completion_async(context, input, stream):
                syncresult += line
            resp = json.loads(syncresult)
            resp["messages"] = messages
            yield json.dumps(resp)
    else:
        raise HTTPException(status_code=400, detail="embedding is None or has no data")


def fake_data_streamer() -> str:
    for i in range(10):
        yield b"data: some fake data\n\n"
        time.sleep(0.5)


class ChatInput(BaseModel):
    input: str
    limit: int = 10
    stream: bool = False


@api_app.post("/chat/")
async def chat(input: ChatInput):
    # todo: receive config from request
    if not input.input is None and len(input.input) > 0:
        return StreamingResponse(
            fake_data_streamer(), media_type="text/event-stream"
        )  # application/json
    else:
        raise HTTPException(status_code=400, detail="no input provided")


async def _question(input: str, limit: int = 10, stream: bool = False):
    # todo: receive config from request
    if not input is None and len(input) > 0:
        if stream:
            return StreamingResponse(
                generate_question(input, limit, stream), media_type="text/event-stream"
            )  # application/json
        else:
            async for line in generate_question(input, limit, stream):
                return line
    else:
        raise HTTPException(status_code=400, detail="no input provided")


@api_app.get("/question/")
async def question(input: str, limit: int = 10, stream: bool = False):
    return await _question(input, limit, stream)


@api_app.post("/question/")
async def question(input: ChatInput):
    return await _question(input.input, input.limit, input.stream)


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
