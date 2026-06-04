# PR #1649 compose regression CI gate

Date: 2026-06-04T01:20:37.644+00:00

Decision: Compose security regression checks that protect accepted CI/pre-release posture must run inside a required CI aggregate before merge, not remain manual-only validation.

Context: Lambert requested changes on PR #1649 because `tests/test-compose-security.sh` verified ZooKeeper host-port exposure and Solr auth wiring locally but was not wired into required CI.

Outcome: Add the compose regression script as a CI job feeding the required `All tests passed` check so future regressions block PR merge.
