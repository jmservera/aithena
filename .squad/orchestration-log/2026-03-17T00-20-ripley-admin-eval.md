# Orchestration: Admin Service Evaluation (Ripley — Lead)

**Timestamp:** 2026-03-17T00:20:00Z  
**Agent:** Ripley (Lead)  
**Mode:** Background  
**Task:** Evaluate whether admin service (Streamlit-based) should be kept or consolidated into aithena-ui

## Scope

The admin dashboard (`src/admin/`) is a separate Python service using Streamlit. The question: is it redundant? Should we consolidate it into the React UI and deprecate Streamlit?

## Analysis Performed

1. **Feature audit:** Compared Streamlit admin functionality (document listing, search testing, stats views) vs. React UI capabilities
2. **User feedback:** Checked if team/users rely on Streamlit for admin functions
3. **Maintenance burden:** Evaluated Docker image size, dependency complexity, Streamlit upgrade risk
4. **Integration cost:** Assessed effort to add admin functionality to React UI

## Finding

The Streamlit admin dashboard is **functionally redundant**:
- All document listing functions are available in aithena-ui
- Search testing can be done via the React UI search interface
- Statistics/monitoring is duplicated across services

Maintenance burden is non-zero: Streamlit is a heavy dependency (Plotly, pandas, etc.) for limited utility.

## Recommendation

**Consolidate admin functions into aithena-ui.** Deprecate Streamlit service in v1.3.0. Timeline:

- v1.3.0: Mark admin service as deprecated in docs
- v1.4.0: Integrate remaining admin functions into React UI (likely just advanced search + stats views)
- v1.5.0: Remove Streamlit service

## Outcome

✅ **SUCCESS** — Evaluation complete, recommendation documented

## Impact

- Simplifies Docker Compose setup (one fewer Python service)
- Reduces dependency surface (no Streamlit in production)
- Consolidates UI surface (single React entrypoint for all user functions)
- Frees developer time: no Streamlit maintenance burden

## Blockers / Dependencies

None (this is a planning/evaluation task).

## Artifacts

- Decision documented in `.squad/decisions.md`
- Deprecation plan ready for product roadmap (v1.3.0–v1.5.0)
