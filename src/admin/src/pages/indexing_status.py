"""Detailed indexing status page — shows per-file processing progress from Redis.

Helper functions (classify_document, load_all_documents, build_status_dataframe) are
import-safe and can be used by tests without triggering Streamlit UI or Redis I/O.
The render_page() function contains all UI and I/O logic and is only called when
running inside the Streamlit runtime.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

import redis
from pages.shared.config import QUEUE_NAME, REDIS_HOST, REDIS_PORT


STATUS_LABELS = {
    "processing": ("🔄", "Processing"),
    "queued": ("⏳", "Queued"),
    "processed": ("✅", "Done"),
    "failed": ("❌", "Failed"),
}


def classify_document(state: dict[str, Any]) -> str:
    """Return a status label for a document based on its Redis state."""
    if state.get("failed"):
        return "failed"
    if state.get("processed"):
        return "processed"
    if state.get("text_indexed") or state.get("solr_id"):
        return "processing"
    return "queued"


def load_all_documents(
    redis_client: redis.Redis,
) -> list[dict[str, Any]]:
    """Load all document states from Redis with computed status."""
    keys = redis_client.keys(f"/{QUEUE_NAME}/*")
    documents: list[dict[str, Any]] = []

    for key in keys:
        raw = redis_client.get(key)
        if not raw:
            continue
        try:
            state = json.loads(raw)
        except json.JSONDecodeError:
            continue

        state["_redis_key"] = key
        state["status"] = classify_document(state)
        documents.append(state)

    return documents


def build_status_dataframe(
    documents: list[dict[str, Any]],
    status_filter: str | None = None,
) -> pd.DataFrame:
    """Build a display-ready DataFrame from document states."""
    if status_filter:
        documents = [d for d in documents if d["status"] == status_filter]

    if not documents:
        return pd.DataFrame()

    columns = [
        "status",
        "path",
        "title",
        "text_indexed",
        "embedding_indexed",
        "page_count",
        "chunk_count",
        "error",
        "error_stage",
        "timestamp",
    ]

    df = pd.DataFrame(documents)
    available = [c for c in columns if c in df.columns]
    df = df[available].copy()

    if "status" in df.columns:
        df["status"] = df["status"].map(
            lambda s: f"{STATUS_LABELS.get(s, ('', s))[0]} {STATUS_LABELS.get(s, ('', s))[1]}"
        )

    bool_cols = ["text_indexed", "embedding_indexed"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].map({True: "✅", False: "❌", None: "—"}).fillna("—")

    int_cols = ["page_count", "chunk_count"]
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    return df.reset_index(drop=True)


def render_page() -> None:
    """Render the indexing status page (requires Streamlit runtime + Redis)."""
    st.title("📊 Indexing Status")

    try:
        redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
        )

        all_docs = load_all_documents(redis_client)

        # Summary metrics
        counts = {"queued": 0, "processing": 0, "processed": 0, "failed": 0}
        total_pages = 0
        total_chunks = 0
        for doc in all_docs:
            status = doc.get("status", "queued")
            counts[status] = counts.get(status, 0) + 1
            total_pages += int(doc.get("page_count") or 0)
            total_chunks += int(doc.get("chunk_count") or 0)

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("📚 Total Files", len(all_docs))
        col2.metric("⏳ Queued", counts["queued"])
        col3.metric("🔄 Processing", counts["processing"])
        col4.metric("✅ Done", counts["processed"])
        col5.metric("📄 Pages Indexed", total_pages)
        col6.metric("🧩 Chunks Indexed", total_chunks)

        st.divider()

        # Filter controls
        filter_col, refresh_col = st.columns([4, 1])
        with filter_col:
            status_options = ["All", "Queued", "Processing", "Done", "Failed"]
            selected = st.selectbox("Filter by status", status_options, index=0)
        with refresh_col:
            st.markdown("")  # spacing
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()

        status_map = {
            "All": None,
            "Queued": "queued",
            "Processing": "processing",
            "Done": "processed",
            "Failed": "failed",
        }
        active_filter = status_map.get(selected)

        # Currently processing section
        processing_docs = [d for d in all_docs if d["status"] == "processing"]
        if processing_docs:
            st.subheader("🔄 Currently Processing")
            for doc in processing_docs:
                path = doc.get("path", "Unknown")
                text_done = "✅" if doc.get("text_indexed") else "⏳"
                embed_done = "✅" if doc.get("embedding_indexed") else "⏳"
                pages = int(doc.get("page_count") or 0)
                chunks = int(doc.get("chunk_count") or 0)

                with st.container(border=True):
                    pcol1, pcol2, pcol3, pcol4 = st.columns([4, 1, 1, 1])
                    pcol1.markdown(f"**{path}**")
                    pcol2.markdown(f"Text: {text_done}")
                    pcol3.markdown(f"Pages: **{pages}**")
                    pcol4.markdown(f"Embed: {embed_done} ({chunks} chunks)")
            st.divider()

        # Full table
        st.subheader("📋 All Documents")
        df = build_status_dataframe(all_docs, active_filter)
        if df.empty:
            st.info("No documents match the selected filter.")
        else:
            st.dataframe(df, use_container_width=True, height=500)

    except redis.exceptions.ConnectionError:
        st.error(
            f"Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}. "
            "Check that the `REDIS_HOST` and `REDIS_PORT` environment variables are set correctly."
        )


def _in_streamlit_context() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


if _in_streamlit_context():
    render_page()
