#!/usr/bin/env python
# encoding: utf-8

import aiohttp
from flask import Flask, request, jsonify
from qdrant_client import models, QdrantClient
from config import *

app = Flask(__name__)


async def get_embeddings_async(text):
    """Get embeddings for a text from embeddings service"""
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/v1/embeddings/",
            json={"input": text},
        ) as resp:
            return await resp.json()


async def get_chat_completion_async(context,question):
    
    stop=["Question:", "\n"]
    messages = []
    messages.append({"content": "Context: "+context+ "\n---\n"+"Question:" + question + "\n---\n" + "Answer:", "role": "user"})

    completionRequest={"messages": messages, "max_tokens": 1200, "stop": stop}
                       #, "temperature": 0.9, "top_p": 1, "frequency_penalty": 0, "presence_penalty": 0, "best_of": 1, "n": 1, "stream": False, "logprobs": None, "echo": False}
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{CHAT_HOST}:{CHAT_PORT}/v1/chat/completions/",
            json=completionRequest,
        ) as resp:
            return await resp.json()


@app.route("/question", methods=["GET"])
async def question():
    input = request.args.get("input").strip()
    if not input is None and len(input) != 0:
        embedding = await get_embeddings_async(input)

        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=embedding["data"][0]["embedding"],
            limit=CONTEXT_LIMIT,
        )
        messages = []

        context=""
        for hit in hits:
            context += hit.payload['text'] + "\n---\n"
            messages.append({"id": hit.id,"payload": hit.payload['text'], "score": hit.score, "path": hit.payload['path']})

        print(context)
        result = await get_chat_completion_async(context,input)
        result["messages"] = messages
        return jsonify(result)
    else:
        return jsonify({"error": "no input provided"}), 400


@app.route("/", methods=["GET"])
async def index():
    text = request.args.get("text")
    if not text is None and len(text) != 0:
        embedding = await get_embeddings_async(text)

        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=embedding["data"][0]["embedding"],
            limit=5,
        )
        results = []
        for hit in hits:
            results.append({"payload": hit.payload, "score": hit.score, "id": hit.id})
        return jsonify({"text": text, "results": results})
    else:
        return jsonify({"error": "no text provided"}), 400


qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")

if __name__ == "__main__":
    # run flask app for debugging
    app.run(host="0.0.0.0", port=PORT, debug=True)
