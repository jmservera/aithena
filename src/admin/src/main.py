import logging
import os

import streamlit as st

from auth import AuthSettings, logout, require_auth
from logging_config import setup_logging
from pages.shared.config import AUTH_ENABLED

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

admin_version = os.getenv("VERSION", "dev")

st.set_page_config(page_title="Aithena Admin", page_icon="🏛️", layout="wide")

# ── Sidebar: version + auth ─────────────────────────────────────────────────
st.sidebar.caption(f"Admin v{admin_version}")
if auth_user is not None:
    st.sidebar.markdown(f"Signed in as **{auth_user.username}**")
    if st.sidebar.button("🚪 Sign out"):
        logout()
        st.rerun()

# ── Navigation ───────────────────────────────────────────────────────────────
pages = {
    "Overview": [
        st.Page("pages/dashboard.py", title="Dashboard", icon="📊", default=True),
    ],
    "Documents": [
        st.Page("pages/document_lister.py", title="Document Manager", icon="📄"),
    ],
    "Indexing": [
        st.Page("pages/reindex.py", title="Reindex Library", icon="🔄"),
    ],
    "System": [
        st.Page("pages/system_status.py", title="System Status", icon="🔧"),
        st.Page("pages/infrastructure.py", title="Infrastructure", icon="🏗️"),
    ],
}

nav = st.navigation(pages)
nav.run()
