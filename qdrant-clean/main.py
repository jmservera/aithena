#!/usr/bin/env python
# encoding: utf-8
import aiohttp
from qdrant_client import models, QdrantClient
from config import *

from fastapi import FastAPI, HTTPException, BackgroundTasks
import httpx

app = FastAPI(title="𐃆 Aithena DB Cleaning API")

async def post_callback(url: str, payload: dict):
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def long_running_task(callback_url: str):
    try:
        points=qdrant.scroll(collection_name=QDRANT_COLLECTION, limit=100)
        count=0
        while True:
            count+=len(points[0])
            print(count)
            if(points[1]):
                points=qdrant.scroll(collection_name=QDRANT_COLLECTION, limit=100, offset=points[1])
            else:
                break

        result = {"status": "completed", "data": {"count": count}}
        await post_callback(callback_url, result)
    except Exception as e:
        print(f"Task failed: {e}")
    finally:
        print("Task completed")

@app.get("/v1/find-repeated/")
async def find_repeated(background_tasks: BackgroundTasks, callback_url: str = "http://example.com/callback"):
    background_tasks.add_task(long_running_task, callback_url)
    return {"message": "Task started! You'll receive a notification at the callback URL once it's complete."}


    # else:
    #     raise HTTPException(status_code=400, detail="no input provided")


qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")

if __name__ == "__main__":
    import uvicorn

    print("Starting server locally...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
