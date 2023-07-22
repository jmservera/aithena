#!/usr/bin/env python
# encoding: utf-8
import aiohttp
from qdrant_client import models, QdrantClient
from config import *

from fastapi import FastAPI, HTTPException


app = FastAPI(title="𐃆 Aithena DB Cleaning API")


@app.get("/v1/find-repeated/")
async def find_repeated():    
    points=qdrant.scroll(collection_name=QDRANT_COLLECTION, limit=100)
    count=0
    while True:
        count+=len(points[0])
        print(count)
        if(points[1]):
            points=qdrant.scroll(collection_name=QDRANT_COLLECTION, limit=100, offset=points[1])
        else:
            break
    return {"count": count}
    # else:
    #     raise HTTPException(status_code=400, detail="no input provided")


qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
