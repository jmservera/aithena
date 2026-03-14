# Decision Inbox — nginx admin entry point

- **Date:** 2026-03-14
- **Author:** Copilot working as Brett
- **Decision:** Standardize local/prod-style web ingress through the repo-managed nginx service. The main React UI is now served at `/`, and admin tooling is grouped under `/admin/`.
- **Implementation details:**
  - `/admin/solr/` proxies Solr Admin.
  - RabbitMQ now uses the management image plus `management.path_prefix = /admin/rabbitmq` so both the UI and API work behind `/admin/rabbitmq/`.
  - Streamlit runs with `--server.baseUrlPath=/admin/streamlit`.
  - Redis Commander is added with `URL_PREFIX=/admin/redis`.
  - `/admin/` serves a simple landing page linking to all admin surfaces.
- **Impact on teammates:**
  - Frontend/UI traffic should go through nginx at `http://localhost/` in proxied runs.
  - Ops/testing docs should prefer the `/admin/...` URLs over direct service ports, though direct ports remain available for local debugging.
