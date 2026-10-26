"""
Real HTTP / Webhook Agent.

Executes outbound HTTP requests to validated domain allowlists, enforces strict SSRF protections
against localhost and private IP subnets, sanitizes sensitive auth headers, and requires human approval
for external side-effect payloads.
"""

import os
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.agents.base import AgentContext, AgentResult, ArtifactRef, BaseAgent


class HttpWebhookAgent(BaseAgent):
    """Production HTTP / Webhook Agent with SSRF safeguards and approval governance."""

    agent_type = "http_webhook"
    description = "Invokes authorized external REST APIs and Webhooks with domain & SSRF policy enforcement."
    requires_side_effect_approval = False

    BLOCKED_HOST_PATTERNS = [
        r"^localhost$",
        r"^127\.\d+\.\d+\.\d+$",
        r"^10\.\d+\.\d+\.\d+$",
        r"^172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+$",
        r"^192\.168\.\d+\.\d+$",
        r"^169\.254\.169\.254$",  # AWS/GCP Instance Metadata Service
        r"^0\.0\.0\.0$",
        r"^::1$",
    ]

    DEFAULT_TIMEOUT_SECONDS = 5
    MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB limit

    def execute(self, context: AgentContext) -> AgentResult:
        start_time = time.time()
        input_data = context.input_data or {}

        url = input_data.get("url") or input_data.get("endpoint")
        method = (input_data.get("method") or "GET").upper()
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            method = "GET"

        if not url or not isinstance(url, str):
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error="URL string ('url') parameter is required.",
                execution_duration_ms=duration,
            )

        # 1. SSRF & Domain Security Check
        is_safe_url, domain, ssrf_err = self._validate_ssrf_and_domain(url)
        if not is_safe_url:
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error=ssrf_err or "URL blocked by security policy.",
                execution_duration_ms=duration,
            )

        # 2. Side-Effect Approval Check for POST/PUT/PATCH/DELETE
        from app.security.approval_policy import requires_approval, verify_approval_before_execution

        needs_appr, risk_lvl, appr_reason = requires_approval("http_webhook", method, input_data)

        task_exec_id = None
        if hasattr(context, "metadata") and context.metadata:
            task_exec_id = context.metadata.get("task_execution_id")
        if not task_exec_id and str(context.task_id).isdigit():
            task_exec_id = int(context.task_id)

        is_authorized = verify_approval_before_execution(
            task_execution_id=task_exec_id,
            workflow_execution_id=context.metadata.get("workflow_execution_id") if context.metadata else None,
            agent_type="http_webhook",
            action=method,
            input_data=input_data,
            context_metadata=context.metadata,
        )

        if needs_appr and not is_authorized:
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=True,
                agent_type=self.agent_type,
                task_id=context.task_id,
                output={
                    "method": method,
                    "url": url,
                    "statusCode": 0,
                    "data": None,
                    "durationMs": 0,
                    "status": "awaiting_approval",
                },
                requires_approval=True,
                approval_details={
                    "requested_action": f"Invoke HTTP {method} webhook to {domain}",
                    "explanation": f"Outbound HTTP {method} request to external domain '{domain}' requires human authorization.",
                    "risk_level": risk_lvl,
                },
                execution_duration_ms=duration,
            )

        # 3. Prepare Safe Headers & Payload
        headers = dict(input_data.get("headers") or {})
        headers.setdefault("User-Agent", "Enterprise-MultiAgent-Webhook/1.0")

        # Sanitize sensitive headers in log outputs
        sanitized_headers = {
            k: ("***REDACTED***" if k.lower() in ("authorization", "x-api-key", "api-key", "secret") else v)
            for k, v in headers.items()
        }

        payload = input_data.get("data") or input_data.get("json") or {}
        params = input_data.get("params") or input_data.get("query_params")

        # 4. Dispatch Outbound Request safely with disabled automatic redirects to prevent 3xx SSRF loops
        req_start = time.time()
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=payload if method in ("POST", "PUT", "PATCH") and payload else None,
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
                allow_redirects=False,  # Prevent 3xx redirect SSRF bypasses
            )

            req_duration_ms = int((time.time() - req_start) * 1000)

            # Check for Redirects (3xx) and validate redirect target if any
            if 300 <= resp.status_code < 400 and "Location" in resp.headers:
                redirect_target = resp.headers["Location"]
                is_safe_redirect, _, redirect_err = self._validate_ssrf_and_domain(redirect_target)
                if not is_safe_redirect:
                    duration = int((time.time() - start_time) * 1000)
                    return AgentResult(
                        success=False,
                        agent_type=self.agent_type,
                        task_id=context.task_id,
                        error=f"SSRF Policy Violation: Webhook redirect to '{redirect_target}' was blocked: {redirect_err}",
                        execution_duration_ms=duration,
                    )

            # Check content length limit
            resp_content = getattr(resp, "content", None)
            if resp_content is None and hasattr(resp, "raw") and hasattr(resp.raw, "read"):
                resp_content = resp.raw.read()

            if resp_content is not None and len(resp_content) > self.MAX_RESPONSE_BYTES:
                duration = int((time.time() - start_time) * 1000)
                return AgentResult(
                    success=False,
                    agent_type=self.agent_type,
                    task_id=context.task_id,
                    error=f"Response size exceeded {self.MAX_RESPONSE_BYTES // (1024*1024)}MB limit.",
                    execution_duration_ms=duration,
                )

            # Parse Response JSON exactly once, or preserve raw text
            is_json = False
            resp_data = None
            try:
                resp_data = resp.json()
                is_json = True
            except Exception:
                resp_text = getattr(resp, "text", None)
                if resp_text is None and resp_content is not None:
                    resp_text = resp_content.decode("utf-8", errors="ignore") if isinstance(resp_content, bytes) else str(resp_content)
                elif resp_text is None:
                    resp_text = ""

                try:
                    import json
                    resp_data = json.loads(resp_text)
                    is_json = True
                except Exception:
                    resp_data = resp_text
                    is_json = False

            resp_headers = dict(resp.headers)
            status_code = resp.status_code
            success = 200 <= status_code < 300

        except requests.exceptions.Timeout:
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error=f"HTTP request timed out after {self.DEFAULT_TIMEOUT_SECONDS}s.",
                execution_duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error=f"HTTP Request failed: {str(e)}",
                execution_duration_ms=duration,
            )

        duration = int((time.time() - start_time) * 1000)

        output_payload = {
            "method": method,
            "url": url,
            "statusCode": status_code,
            "status_code": status_code,
            "data": resp_data,
            "body": resp_data,
            "response_body": resp_data,
            "response_headers": resp_headers,
            "headers": resp_headers,
            "is_json": is_json,
            "durationMs": req_duration_ms,
            "duration_ms": req_duration_ms,
            "response_time_ms": req_duration_ms,
            "status": "completed" if success else f"HTTP {status_code}",
            "success": success,
            "warnings": [] if success else [f"HTTP server returned status code {status_code}."],
        }

        return AgentResult(
            success=success,
            agent_type=self.agent_type,
            task_id=context.task_id,
            output=output_payload,
            metadata={
                "domain": domain,
                "status_code": status_code,
                "response_time_ms": req_duration_ms,
                "sanitized_headers": sanitized_headers,
                "is_json": is_json,
            },
            execution_duration_ms=duration,
        )

    def _validate_ssrf_and_domain(self, url: str) -> Tuple[bool, str, Optional[str]]:
        """Parse URL, perform DNS resolution, and enforce SSRF blocklist and optional domain allowlist."""
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False, "", "Only http and https URL schemes are allowed."

            hostname = parsed.hostname or ""
            if not hostname:
                return False, "", "Invalid URL: Missing hostname."

            # 1. SSRF Pattern Check on Hostname
            for pattern in self.BLOCKED_HOST_PATTERNS:
                if re.match(pattern, hostname, re.IGNORECASE):
                    return False, hostname, f"SSRF Security Violation: Access to private/internal host '{hostname}' is prohibited."

            # 2. DNS Resolution IP Check to prevent DNS Rebinding
            import socket
            try:
                resolved_ip = socket.gethostbyname(hostname)
                for pattern in self.BLOCKED_HOST_PATTERNS:
                    if re.match(pattern, resolved_ip):
                        return False, hostname, f"SSRF Security Violation: Host '{hostname}' resolves to private IP '{resolved_ip}'."
            except Exception:
                pass  # If resolution fails during validation, HTTP request will fail naturally

            # 3. Optional Domain Allowlist check from environment variable
            allowed_domains_env = os.getenv("ALLOWED_WEBHOOK_DOMAINS", "")
            if allowed_domains_env:
                allowed_list = [d.strip().lower() for d in allowed_domains_env.split(",") if d.strip()]
                if allowed_list and not any(hostname.lower().endswith(domain) for domain in allowed_list):
                    return False, hostname, f"Domain Security Policy: Host '{hostname}' is not in ALLOWED_WEBHOOK_DOMAINS."

            return True, hostname, None
        except Exception as e:
            return False, "", f"Invalid URL structure: {str(e)}"
