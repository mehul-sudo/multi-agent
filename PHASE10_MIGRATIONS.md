# Phase 10 — Database Migrations Guide

## Migration Chain Summary

| Migration Revision ID | Phase | Description |
|-----------------------|-------|-------------|
| `bb7369877553` | Phase 1 | Initial `users` table |
| `a1b2c3d4e5f6` | Phase 4 | `token_blocklist` table |
| `c1d2e3f4a5b6` | Phase 5 | Orchestration session, plan, task, event tables |
| `d1e2f3a4b5c6` | Phase 6 | `llm_usage` log table & agent fields |
| `e1f2a3b4c5d6` | Phase 7 | Async jobs and schedules tables |
| `f2a3b4c5d6e7` | Phase 8 | Multi-agent collaboration & delegation tables |
| `g1h2i3j4k5l6` | Phase 9 | Intelligence & execution plan tables |
| `h1i2j3k4l5m6` | Phase 10 | Enterprise Security, RBAC & Governance tables |

---

## Schema Changes Introduced in Phase 10

### New Tables Created
1. `organizations`: Multi-tenant organization boundaries and quota settings.
2. `organization_members`: User memberships and organization roles.
3. `workflow_policies`: Workflow security governance policies.
4. `tool_policies`: Tool capability policies and allow/deny lists.
5. `encrypted_credentials`: AES-256 Fernet encrypted credential vault.
6. `rate_limit_state`: Sliding window rate limit counters.

### Existing Tables Modified (Backward-Compatible Nullable Columns)
- `workflows`: added nullable `organization_id` (foreign key -> `organizations.id`)
- `agents`: added nullable `organization_id` (foreign key -> `organizations.id`)
- `workflow_schedules`: added nullable `organization_id` (foreign key -> `organizations.id`)
- `audit_events`: added nullable `organization_id` and `correlation_id`

---

## Running Migrations

### Apply Migrations
```bash
flask db upgrade
```

### Rollback Migration
```bash
flask db downgrade
```
