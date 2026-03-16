# Decision: manage RabbitMQ and Redis credentials via the installer

**Date:** 2026-03-16  
**Author:** @copilot  
**Related files:** `installer/setup.py`, `.env.example`, `docker-compose.yml`, `docs/deployment/production.md`

## Context

Issue #216 requires the production stack to stop depending on hardcoded/default service credentials and to document a clear rotation path for operators.

RabbitMQ and Redis already sit behind the same `.env`-driven Docker Compose deployment as the auth database and JWT secret, so operators need one canonical place to review and rotate runtime secrets.

## Decision

Extend the installer-managed `.env` contract to include `RABBITMQ_USER`, `RABBITMQ_PASS`, and `REDIS_PASSWORD`, and wire Docker Compose plus service clients to consume those variables.

## Why

This keeps credential rotation aligned with the existing installer-first deployment flow, avoids split-brain configuration between docs and Compose, and makes production hardening repeatable for future operators and reviewers.