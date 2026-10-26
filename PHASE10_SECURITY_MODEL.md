# Phase 10 — Security Model & Governance Specification

## Threat Model & Mitigations

### 1. Insecure Direct Object References (IDOR) & Cross-Tenant Leakage
- **Threat**: A user accessing another organization's workflow, agent, schedule, credential, or audit log by guessing numeric or UUID identifiers.
- **Mitigation**: All database queries resolve tenant scope (`organization_id`). `OrganizationService.validate_tenant_access()` verifies active membership before returning any resource.

### 2. Privilege Escalation (Horizontal & Vertical)
- **Threat**: Regular users calling administrative APIs or executing workflows they do not own.
- **Mitigation**: Backend-enforced RBAC via `PermissionService.has_permission()` and `@require_permission` decorator. All authorization happens server-side.

### 3. Arbitrary Command Execution & Unsafe Tool Invocations
- **Threat**: Malicious or hijacked AI agents attempting to run unauthorized tools, shell commands, or SQL injections.
- **Mitigation**: `ToolAuthorizationService` enforces agent capability allowlists, tool denylists, dangerous tool classification, domain restrictions, and prompt injection defense heuristics.

### 4. Credential & Secret Exposure
- **Threat**: Plaintext API keys, passwords, or tokens leaked in database dumps, log files, exception stack traces, or API GET responses.
- **Mitigation**: `CredentialService` encrypts all secrets at rest using AES-256 Fernet encryption. Plaintext is decrypted only in-memory during execution. API responses return metadata only. `SecretService` automatically redacts secrets from audit logs and error messages.

### 5. Self-Approval & Replay Attacks
- **Threat**: An operator approving their own high-risk request or replaying expired approval tokens.
- **Mitigation**: `ApprovalService` checks for self-approval attempts (`orchestration.user_id == user_id`) and rejects expired requests (`expiry_time < _utcnow()`).

### 6. Distributed Denial of Service (DDoS) & Brute Force Attacks
- **Threat**: Malicious actors flooding authentication endpoints or workflow execution dispatches.
- **Mitigation**: `RateLimitService` implements sliding-window rate limiting per IP, user ID, and endpoint category, returning HTTP 429 when limits are exceeded.
