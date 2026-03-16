import json
import logging
import os

import redis
import requests
import streamlit as st
from auth import AuthSettings, logout, require_auth
from logging_config import setup_logging
from pages.shared.config import (
    AUTH_ENABLED,
    QUEUE_NAME,
    RABBITMQ_HOST,
    RABBITMQ_MGMT_PATH_PREFIX,
    RABBITMQ_MGMT_PORT,
    RABBITMQ_PASS,
    RABBITMQ_USER,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)

auth_user = None
if AUTH_ENABLED:
    try:
        settings = AuthSettings.from_env()
    except ValueError as exc:
        st.error(f"Authentication configuration error: {exc}")
        st.stop()
    auth_user = require_auth(settings)

setup_logging(service_name="admin")
logger = logging.getLogger(__name__)

rabbitmq_management_url = f"http://{RABBITMQ_HOST}:{RABBITMQ_MGMT_PORT}{RABBITMQ_MGMT_PATH_PREFIX}"
admin_version = os.getenv("VERSION", "dev")

st.set_page_config(page_title="Aithena Admin", page_icon="🏛️", layout="wide")
st.title("🏛️ Aithena Admin Dashboard")
st.caption(
    f"Redis: `{REDIS_HOST}:{REDIS_PORT}` · Queue: `{QUEUE_NAME}` · RabbitMQ management: `{rabbitmq_management_url}`"
)

st.sidebar.caption(f"Admin v{admin_version}")
if auth_user is not None:
    st.sidebar.markdown(f"Signed in as **{auth_user.username}**")
    if st.sidebar.button("🚪 Sign out"):
        logout()
        st.rerun()

# ── Redis metrics ────────────────────────────────────────────────────────────
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)
    keys = redis_client.keys(f"/{QUEUE_NAME}/*")

    total = len(keys)
    queued = processed = failed = 0
    for key in keys:
        raw = redis_client.get(key)
        if not raw:
            continue
        try:
            state = json.loads(raw)
            if state.get("failed"):
                failed += 1
            elif state.get("processed"):
                processed += 1
            else:
                queued += 1
        except json.JSONDecodeError:
            pass

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📚 Total Documents", total)
    col2.metric("⏳ Queued", queued)
    col3.metric("✅ Processed", processed)
    col4.metric("❌ Failed", failed)

except redis.exceptions.ConnectionError:
    logger.error("Cannot connect to Redis", extra={"redis_host": REDIS_HOST, "redis_port": REDIS_PORT})
    st.error(f"Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}")

# ── RabbitMQ management API ──────────────────────────────────────────────────
st.subheader("📨 RabbitMQ Queue")
try:
    resp = requests.get(
        f"{rabbitmq_management_url}/api/queues/%2F/{QUEUE_NAME}",
        auth=(RABBITMQ_USER, RABBITMQ_PASS),
        timeout=5,
    )
    if resp.status_code == 200:
        queue_info = resp.json()
        c1, c2, c3 = st.columns(3)
        c1.metric("Messages Ready", queue_info.get("messages_ready", "N/A"))
        c2.metric("Messages Unacked", queue_info.get("messages_unacknowledged", "N/A"))
        c3.metric("Total Messages", queue_info.get("messages", "N/A"))
    elif resp.status_code == 404:
        st.info(f"Queue `{QUEUE_NAME}` not found — it will be created when the first document is listed.")
    else:
        st.warning(f"RabbitMQ management API returned HTTP {resp.status_code}.")
except requests.exceptions.RequestException:
    st.info(
        "RabbitMQ management API not reachable. Verify `RABBITMQ_HOST`, "
        "`RABBITMQ_MGMT_PORT`, and `RABBITMQ_MGMT_PATH_PREFIX`."
    )

st.divider()
st.info("Use **Document Manager** in the sidebar to inspect documents and trigger requeue or clear actions.")
