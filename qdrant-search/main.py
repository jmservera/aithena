#!/usr/bin/env python
# encoding: utf-8
import aiohttp
from pydantic.dataclasses import dataclass
from pydantic import BaseModel
from qdrant_client import models, QdrantClient
from config import *

from fastapi import FastAPI, HTTPException


app = FastAPI(title=TITLE,version=VERSION)


async def get_embeddings_async(text):
    """Get embeddings for a text from embeddings service"""
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/v1/embeddings/",
            json={"input": text},
        ) as resp:
            return await resp.json()


async def get_completion_async(context, question):
    # TODO: create prompts by language (e.g. English, German, Spanish, Catalan, etc.)
    completionRequest = { "prompt": f"### Context:{context}\n\n###\n Instructions:\n{question}\n\n### Response:\n",
                          "max_tokens": 2048,
                          "stop" : ["###"]
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
            return await resp.json()

@dataclass
class info_class:
    title: str
    version: str
    def __init__(self, title: str, version: str):
        self.title = title
        self.version = version

@app.get("/")
async def info()-> info_class:
    return info_class(TITLE, VERSION)

@app.get("/v1/question/")
async def question(input: str, limit: int = 10):
    if not input is None and len(input) > 0:
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
                        "page": hit.payload["page"]
                    }
                )

            print(context)
            result = await get_completion_async(context, input)
            result["messages"] = messages
            return result
        else:
            raise HTTPException(status_code=400, detail="embedding is None or has no data")
    else:
        raise HTTPException(status_code=400, detail="no input provided")


@app.get("/v1/search/")
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
