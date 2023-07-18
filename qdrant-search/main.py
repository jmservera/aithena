#!/usr/bin/env python
# encoding: utf-8

import json
import asyncio
import aiohttp
from flask import request, jsonify
from qdrant_client import models, QdrantClient
from config import *

app = Flask(__name__)


async def get_embeddings_async(text):
    """Get embeddings for a text from embeddings service"""
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.post(
            f"http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/v1/embeddings",
            json={"input": text}
        ) as resp:
            return await resp.json()

@app.route('/', methods=['GET'])
async def index():
    text = request.args.get('text')
    if(not text is None and len(text) != 0):
        embedding=await get_embeddings_async(text)

        hits = qdrant.search(
            collection_name="documents",
            query_vector=embedding["data"][0]["embedding"],
            limit=5
        )
        results=[]
        for hit in hits:
            results.append({'payload':hit.payload,'score':hit.score})
        return {'text':text,'results':results}
    else:
        return {'error':'no text provided'},400

qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")

if __name__ == "__main__":
    # run flask app on port 5001 for debugging
    app.run(host='0.0.0.0', port=5001, debug=True)