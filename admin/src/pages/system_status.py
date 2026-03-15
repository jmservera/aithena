from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
import streamlit as st
from pages.shared.config import SOLR_SEARCH_URL

APP_SERVICE_ORDER = [
    "solr-search",
    "embeddings-server",
    "document-indexer",
    "document-lister",
    "streamlit-admin",
    "admin",
    "aithena-ui",
]
INFRA_SERVICE_ORDER = ["solr", "redis", "rabbitmq", "nginx", "zookeeper", "zoo1", "zoo2", "zoo3"]
DISPLAY_NAME_OVERRIDES = {"streamlit-admin": "admin"}
STATUS_STYLE = {
    "up": ("✅", "green"),
    "running": ("✅", "green"),
    "healthy": ("✅", "green"),
    "down": ("❌", "red"),
}

st.set_page_config(page_title="System Status", page_icon="🔧", layout="wide")
st.title("🔧 System Status")


def get_status_style(status: str) -> tuple[str, str]:
    return STATUS_STYLE.get(status.lower(), ("⚠️", "orange"))


@st.cache_data(ttl=30, show_spinner=False)
def fetch_container_status() -> dict[str, Any]:
    response = requests.get(f"{SOLR_SEARCH_URL}/v1/admin/containers", timeout=5)
    response.raise_for_status()
    return response.json()


def get_display_name(container: dict[str, Any]) -> str:
    name = str(container.get("name") or "unknown")
    return DISPLAY_NAME_OVERRIDES.get(name, name)


def format_value(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    return text or "unknown"


def shorten_commit(commit: Any) -> str:
    text = format_value(commit)
    return text if text == "unknown" else text[:8]


def format_timestamp(timestamp: str) -> str:
    if not timestamp:
        return "unknown"

    try:
        normalized = timestamp.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return timestamp

    return parsed.strftime("%Y-%m-%d %H:%M:%S %Z") or timestamp


def order_containers(containers: list[dict[str, Any]], preferred_order: list[str]) -> list[dict[str, Any]]:
    order_index = {name: index for index, name in enumerate(preferred_order)}
    return sorted(
        containers,
        key=lambda container: (
            order_index.get(str(container.get("name")), len(order_index)),
            get_display_name(container),
        ),
    )


def split_containers(containers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    application: list[dict[str, Any]] = []
    infrastructure: list[dict[str, Any]] = []

    for container in containers:
        name = str(container.get("name") or "")
        container_type = str(container.get("type") or "")
        if name in INFRA_SERVICE_ORDER or container_type == "infrastructure":
            infrastructure.append(container)
        else:
            application.append(container)

    return (
        order_containers(application, APP_SERVICE_ORDER),
        order_containers(infrastructure, INFRA_SERVICE_ORDER),
    )


def render_container_group(title: str, containers: list[dict[str, Any]], columns_per_row: int) -> None:
    st.subheader(title)
    if not containers:
        st.info("No containers reported for this group.")
        return

    columns = st.columns(columns_per_row)
    for index, container in enumerate(containers):
        status = format_value(container.get("status"))
        emoji, color = get_status_style(status)
        version = format_value(container.get("version"))
        commit = shorten_commit(container.get("commit"))
        error = container.get("error")

        with columns[index % columns_per_row]:
            with st.container(border=True):
                st.markdown(f"**{emoji} {get_display_name(container)}**")
                st.markdown(f"Status: :{color}[{status}]")
                st.markdown(f"Version: `{version}`")
                st.markdown(f"Commit: `{commit}`")
                if error:
                    st.warning(str(error))


summary_col, action_col = st.columns([4, 1])
with action_col:
    if st.button("🔄 Refresh", use_container_width=True):
        fetch_container_status.clear()
        st.rerun()

try:
    payload = fetch_container_status()
except requests.exceptions.RequestException as exc:
    st.warning(
        f"Container status is currently unavailable from {SOLR_SEARCH_URL}/v1/admin/containers. {exc}"
    )
else:
    containers = payload.get("containers", [])
    total = int(payload.get("total", len(containers)))
    healthy = int(payload.get("healthy", 0))
    last_updated = format_timestamp(format_value(payload.get("last_updated")))
    application_services, infrastructure_services = split_containers(containers)

    with summary_col:
        st.caption(f"Last updated: {last_updated}")

    metric_total, metric_healthy, metric_attention = st.columns(3)
    metric_total.metric("Total containers", total)
    metric_healthy.metric("Healthy", healthy)
    metric_attention.metric("Need attention", max(total - healthy, 0))

    render_container_group("📦 Application Services", application_services, columns_per_row=3)
    render_container_group("🏗️ Infrastructure Services", infrastructure_services, columns_per_row=4)
