import streamlit as st
import redis
from pages.shared.config import *
import json
import pandas as pd

st.markdown("# Document Lister 📄")
st.sidebar.markdown("# Document Lister 📄")

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
# define variable keys with type list[str]
keys = []
df=pd.DataFrame()

def load_data()->list[str]:
    
    global keys
    global df
    # load keys and values from the collection QUEUE_NAME
    keys = redis_client.keys(f"/{QUEUE_NAME}/*")
    # load values
    dfv = [json.loads(redis_client.get(key)) for key in keys]

    df=pd.DataFrame(dfv)
    return keys

load_data()

if st.button("Clear all documents"):
    # delete all keys from the collection QUEUE_NAME
    for key in keys:
        n=redis_client.delete(key)

    load_data()

if st.button("Refresh"):
    load_data()

#keys
st.dataframe(df, use_container_width=True)


