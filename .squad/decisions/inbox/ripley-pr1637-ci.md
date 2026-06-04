# Decision: PR #1637 CI Routing Fix

**Author:** Ripley (Lead)  
**Date:** 2026-06-03T22:02:03.765+00:00  
**Status:** Implemented  
**Scope:** Squad Issue Assign PR label routing

## Context

PR #1637 was product-approved by Newt but blocked by the `assign-work` check. The failing job was triggered by PR label routing and failed while creating the assignment comment with `Resource not accessible by integration`.

## Decision

Run the `Squad Issue Assign` workflow on `pull_request_target` for PR label routing and explicitly grant `pull-requests: write` alongside `issues: write`.

## Rationale

The `assign-work` job is team routing metadata automation: it comments on issues/PRs when a `squad:{member}` label is applied. It needs the base-repository token context to write PR assignment comments; the routing decision itself does not depend on untrusted PR code.

## Safety Boundary

Keep PR-triggered `pull_request_target` routing workflows restricted to trusted metadata operations and base-branch checkout. Do not add steps that execute PR-head code in this workflow context.
