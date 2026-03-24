import json

import pandas as pd
import streamlit as st

import redis
from pages.shared.config import QUEUE_NAME, REDIS_HOST, REDIS_PORT

st.title("📄 Document Manager")

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def load_documents() -> tuple[list[dict], list[dict], list[dict]]:
    """Load all document states from Redis and split by status."""
    keys = redis_client.keys(f"/{QUEUE_NAME}/*")
    queued: list[dict] = []
    processed: list[dict] = []
    failed: list[dict] = []

    for key in keys:
        raw = redis_client.get(key)
        if not raw:
            continue
        try:
            state = json.loads(raw)
        except json.JSONDecodeError:
            continue
        state["_redis_key"] = key
        if state.get("failed"):
            failed.append(state)
        elif state.get("processed"):
            processed.append(state)
        else:
            queued.append(state)

    return queued, processed, failed


def requeue_document(key: str) -> None:
    """Delete the Redis key so the document-lister will re-discover and re-enqueue it."""
    redis_client.delete(key)


def make_df(docs: list[dict], columns: list[str]) -> pd.DataFrame:
    """Return a DataFrame with only the requested columns that are present."""
    if not docs:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(docs)
    available = [c for c in columns if c in df.columns]
    return df[available].reset_index(drop=True)


try:
    queued_docs, processed_docs, failed_docs = load_documents()

    tab_queued, tab_processed, tab_failed = st.tabs(
        [
            f"⏳ Queued ({len(queued_docs)})",
            f"✅ Processed ({len(processed_docs)})",
            f"❌ Failed ({len(failed_docs)})",
        ]
    )

    # ── Queued tab ───────────────────────────────────────────────────────────
    with tab_queued:
        st.subheader("Queued Documents")
        st.caption("These documents have been discovered by the lister and are waiting to be indexed.")
        if st.button("🔄 Refresh", key="refresh_queued"):
            st.rerun()
        if queued_docs:
            df = make_df(queued_docs, ["path", "timestamp", "last_modified"])
            st.dataframe(df, use_container_width=True)
        else:
            st.success("No documents currently queued.")

    # ── Processed tab ────────────────────────────────────────────────────────
    with tab_processed:
        st.subheader("Processed Documents")
        st.caption("These documents have been successfully indexed into Solr.")
        col_refresh, col_clear = st.columns([4, 1])
        with col_refresh:
            if st.button("🔄 Refresh", key="refresh_processed"):
                st.rerun()
        with col_clear:
            if st.button("🗑️ Clear All", key="clear_processed", type="secondary"):
                st.session_state["confirm_clear_processed"] = True

        if st.session_state.get("confirm_clear_processed"):
            st.warning(
                f"This will remove **{len(processed_docs)}** processed document(s) from Redis. "
                "The lister will re-index them on the next scan."
            )
            confirm_col, cancel_col = st.columns([1, 4])
            with confirm_col:
                if st.button("✅ Confirm", key="confirm_clear_processed_btn", type="primary"):
                    for doc in processed_docs:
                        redis_client.delete(doc["_redis_key"])
                    st.session_state.pop("confirm_clear_processed", None)
                    st.success(f"Cleared {len(processed_docs)} processed document(s).")
                    st.rerun()
            with cancel_col:
                if st.button("❌ Cancel", key="cancel_clear_processed"):
                    st.session_state.pop("confirm_clear_processed", None)
                    st.rerun()
        if processed_docs:
            display_cols = ["path", "title", "author", "year", "category", "page_count", "timestamp"]
            st.dataframe(make_df(processed_docs, display_cols), use_container_width=True)
        else:
            st.info("No processed documents yet.")

    # ── Failed tab ───────────────────────────────────────────────────────────
    with tab_failed:
        st.subheader("Failed Documents")
        st.caption(
            "These documents encountered an error during indexing. "
            "Requeue removes the Redis entry so the lister will pick them up again on next scan."
        )
        col_refresh, col_requeue_all = st.columns([4, 1])
        with col_refresh:
            if st.button("🔄 Refresh", key="refresh_failed"):
                st.rerun()
        with col_requeue_all:
            if failed_docs and st.button("🔄 Requeue All", key="requeue_all", type="primary"):
                for doc in failed_docs:
                    requeue_document(doc["_redis_key"])
                st.success(f"Requeued {len(failed_docs)} failed document(s).")
                st.rerun()

        if failed_docs:
            for doc in failed_docs:
                path_label = doc.get("path", doc.get("_redis_key", "Unknown"))
                with st.expander(f"❌ {path_label}"):
                    st.markdown(f"**Error:** {doc.get('error') or 'No error details recorded.'}")
                    st.markdown(f"**Timestamp:** {doc.get('timestamp', 'N/A')}")
                    if doc.get("last_modified"):
                        st.markdown(f"**Last modified:** {doc['last_modified']}")
                    if st.button("🔄 Requeue", key=f"requeue_{doc['_redis_key']}"):
                        requeue_document(doc["_redis_key"])
                        st.success("Document requeued — it will be picked up on the next lister scan.")
                        st.rerun()
        else:
            st.success("No failed documents. 🎉")

except redis.exceptions.ConnectionError:
    st.error(
        f"Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}. "
        "Check that the `REDIS_HOST` and `REDIS_PORT` environment variables are set correctly."
    )
