"""Log Viewer page — tail container logs via the Docker SDK when available.

Helper functions (list_running_containers, tail_logs) and AITHENA_SERVICES are
import-safe. The render_page() function contains all UI/Docker I/O and is only
called inside the Streamlit runtime.

⚠️ Security: This feature requires mounting the Docker socket into the admin
container (/var/run/docker.sock:/var/run/docker.sock:ro). While mounted
read-only, this still grants significant access to the host Docker daemon.
The feature is gated behind the ENABLE_LOG_VIEWER environment variable
(default: false) so administrators must explicitly opt in.
"""

from __future__ import annotations

import os

import streamlit as st

try:
    import docker

    _DOCKER_AVAILABLE = True
except ImportError:
    docker = None  # type: ignore[assignment]
    _DOCKER_AVAILABLE = False

ENABLE_LOG_VIEWER = os.environ.get("ENABLE_LOG_VIEWER", "false").lower() in (
    "true",
    "1",
    "yes",
)

AITHENA_SERVICES = [
    "solr-search",
    "embeddings-server",
    "document-indexer",
    "document-lister",
    "streamlit-admin",
    "aithena-ui",
    "redis",
    "rabbitmq",
    "nginx",
    "solr",
    "solr2",
    "solr3",
    "zoo1",
    "zoo2",
    "zoo3",
]


def list_running_containers(client: object) -> dict[str, object]:
    """Return a map of service-name → Container for aithena-related services."""
    containers: dict[str, object] = {}
    for container in client.containers.list():
        name = container.name.lstrip("/")
        for svc in AITHENA_SERVICES:
            if svc in name:
                containers[svc] = container
                break
        else:
            labels = container.labels or {}
            project = labels.get("com.docker.compose.project", "")
            if "aithena" in project:
                containers[name] = container
    return containers


def tail_logs(
    container: object,
    tail_lines: int,
) -> str:
    """Return the last *tail_lines* of a container's logs as a string."""
    raw = container.logs(tail=tail_lines, timestamps=True)
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def render_page() -> None:
    """Render the log viewer page (requires Streamlit runtime + Docker)."""
    st.title("📜 Service Log Viewer")

    if not ENABLE_LOG_VIEWER:
        st.warning(
            "🔒 The Log Viewer is **disabled** by default for security.  \n"
            "To enable it, set `ENABLE_LOG_VIEWER=true` in the admin container environment "
            "and mount the Docker socket (`/var/run/docker.sock:/var/run/docker.sock:ro`).  \n\n"
            "⚠️ **Security note:** Mounting the Docker socket grants the admin container "
            "read access to the host Docker daemon. Only enable this in trusted environments "
            "with restricted network access to the admin portal."
        )
        st.info(
            "💡 **Tip:** You can still view indexing progress on the **Indexing Status** page, "
            "which reads from Redis and requires no Docker access."
        )
        st.stop()

    if not _DOCKER_AVAILABLE:
        st.warning(
            "The **docker** Python package is not installed.  \n"
            "Install it (`pip install docker`) and mount the Docker socket "
            "(`/var/run/docker.sock:/var/run/docker.sock:ro`) to enable live log viewing."
        )
        st.info(
            "💡 **Tip:** You can still view indexing progress on the **Indexing Status** page, "
            "which reads from Redis and requires no Docker access."
        )
        st.stop()

    # Docker is importable — try to connect
    try:
        docker_client = docker.from_env()
        docker_client.ping()
    except Exception as exc:
        st.error(
            f"Cannot connect to Docker daemon: {exc}  \n"
            "Make sure the Docker socket is mounted into this container:\n"
            "```yaml\nvolumes:\n  - /var/run/docker.sock:/var/run/docker.sock:ro\n```"
        )
        st.stop()

    # Controls
    control_col1, control_col2, control_col3 = st.columns([3, 1, 1])

    available_containers = list_running_containers(docker_client)
    service_names = sorted(available_containers.keys())

    if not service_names:
        st.info("No aithena-related containers found running.")
        st.stop()

    with control_col1:
        selected_service = st.selectbox(
            "Service",
            options=service_names,
            index=0,
        )

    with control_col2:
        tail_count = st.select_slider(
            "Tail lines",
            options=[50, 100, 200, 500, 1000],
            value=100,
        )

    with control_col3:
        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

    if st.button("🔄 Refresh Logs"):
        st.rerun()

    # Display logs
    if selected_service and selected_service in available_containers:
        container = available_containers[selected_service]
        with st.spinner(f"Fetching logs for **{selected_service}**…"):
            log_text = tail_logs(container, tail_count)

        st.code(log_text, language="log")

        if auto_refresh:
            st.caption("Auto-refreshing every 30 seconds…")
            import time

            time.sleep(30)
            st.rerun()


def _in_streamlit_context() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


if _in_streamlit_context():
    render_page()
