"""Infrastructure page — quick links to infrastructure management UIs."""

import os

import streamlit as st

from pages.shared.config import (
    RABBITMQ_HOST,
    RABBITMQ_MGMT_PATH_PREFIX,
    RABBITMQ_MGMT_PORT,
    REDIS_HOST,
    REDIS_PORT,
)

SOLR_ADMIN_URL = os.environ.get("SOLR_ADMIN_URL", "/admin/solr/")
RABBITMQ_ADMIN_URL = os.environ.get("RABBITMQ_ADMIN_URL", "/admin/rabbitmq/")

st.title("🏗️ Infrastructure")
st.caption("Quick links to infrastructure management dashboards.")

st.subheader("Management UIs")

col1, col2 = st.columns(2)

with col1, st.container(border=True):
    st.markdown("#### 🗄️ Apache Solr")
    st.markdown("Full-text search engine admin console.")
    st.markdown(
        f"[Open Solr Admin ↗]({SOLR_ADMIN_URL})",
    )

with col2, st.container(border=True):
    st.markdown("#### 🐰 RabbitMQ")
    st.markdown("Message queue management console.")
    st.markdown(
        f"[Open RabbitMQ Management ↗]({RABBITMQ_ADMIN_URL})",
    )

st.divider()
st.subheader("Connection Details")

rabbitmq_management_url = (
    f"http://{RABBITMQ_HOST}:{RABBITMQ_MGMT_PORT}{RABBITMQ_MGMT_PATH_PREFIX}"
)

st.markdown(
    f"""
| Service | Endpoint |
|---------|----------|
| **Redis** | `{REDIS_HOST}:{REDIS_PORT}` |
| **RabbitMQ Management** | `{rabbitmq_management_url}` |
"""
)
