"""Reindex page — triggers a full reindex of the book library.

Clears the Solr collection and all Redis tracking state so the
document-lister rediscovers every file and the indexer re-embeds them
with the current embedding model (multilingual-e5-base).
"""

from __future__ import annotations

import requests
import streamlit as st

from pages.shared.config import ADMIN_API_KEY, AUTH_ENABLED, SOLR_SEARCH_URL

if AUTH_ENABLED:
    from auth import AuthSettings, require_auth

    try:
        _settings = AuthSettings.from_env()
    except ValueError as _exc:
        st.error(f"Authentication configuration error: {_exc}")
        st.stop()
    require_auth(_settings)


st.set_page_config(page_title="Reindex Library", page_icon="🔄", layout="wide")
st.title("🔄 Reindex Library")

st.markdown(
    """
Use this page to trigger a **full reindex** of the book library.
This is required after changing the embedding model or updating the Solr schema.

**What happens:**
1. All documents are deleted from the Solr `books` collection
2. All Redis tracking state is cleared (processed, failed, queued)
3. The document-lister automatically rediscovers every file on its next scan
4. The document-indexer re-embeds and re-indexes each document

⚠️ **Search will be unavailable** until reindexing completes.
"""
)


def _api_headers() -> dict[str, str]:
    """Build request headers, including admin API key when configured."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if ADMIN_API_KEY:
        headers["X-API-Key"] = ADMIN_API_KEY
    return headers


def trigger_reindex(collection: str = "books") -> dict:
    """Call the solr-search admin reindex endpoint."""
    url = f"{SOLR_SEARCH_URL}/v1/admin/reindex?collection={collection}"
    resp = requests.post(url, headers=_api_headers(), timeout=60)
    resp.raise_for_status()
    return resp.json()


st.divider()

if st.button("🔄 Start Full Reindex", type="primary", use_container_width=True):
    st.session_state["confirm_reindex"] = True

if st.session_state.get("confirm_reindex"):
    st.warning(
        "⚠️ **This will delete all indexed documents and re-embed the entire library.** "
        "Search will be unavailable until reindexing completes. Are you sure?"
    )
    confirm_col, cancel_col = st.columns([1, 4])
    with confirm_col:
        if st.button("✅ Confirm Reindex", type="primary"):
            st.session_state.pop("confirm_reindex", None)
            with st.spinner("Reindexing..."):
                try:
                    result = trigger_reindex()
                    st.success(
                        f"✅ **Reindex triggered successfully!**\n\n"
                        f"- Solr collection: `{result.get('collection', 'books')}` — {result.get('solr', 'cleared')}\n"
                        f"- Redis entries cleared: {result.get('redis_cleared', '?')}\n\n"
                        f"{result.get('message', '')}"
                    )
                except requests.exceptions.HTTPError as exc:
                    detail = ""
                    try:
                        detail = exc.response.json().get("detail", "")
                    except Exception:
                        detail = exc.response.text[:200] if exc.response else str(exc)
                    st.error(f"❌ Reindex failed: {detail}")
                except requests.exceptions.RequestException as exc:
                    st.error(
                        f"❌ Cannot reach solr-search at `{SOLR_SEARCH_URL}`. "
                        f"Check that the service is running. Error: {exc}"
                    )
    with cancel_col:
        if st.button("❌ Cancel"):
            st.session_state.pop("confirm_reindex", None)
            st.rerun()
