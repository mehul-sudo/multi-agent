"""
Production Security Analysis Agent.

Performs comprehensive, deterministic static vulnerability scanning on source code,
configuration files, Dockerfiles, HTTP requests, and audit logs. Detects SQL Injection,
Cross-Site Scripting (XSS), Command / Remote Code Execution, Insecure Deserialization,
Path Traversal, Hardcoded Secrets / API Keys, Debug Mode in Production, Weak Cryptography,
Insecure CORS, and AI Prompt Injection attempts with traceable line evidence and remediation advice.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base import AgentContext, AgentResult, ArtifactRef, BaseAgent
from app.services.file_service import FileService


class SecurityAnalysisAgent(BaseAgent):
    """Production Security Analysis Agent for static code, config, and audit log vulnerability scanning."""

    agent_type = "security_analysis"
    description = "Scans code, configurations, logs, and files for security vulnerabilities and leaked secrets."
    requires_side_effect_approval = False

    # Comprehensive Static Vulnerability Rules Engine
    SECURITY_RULES = [
        # 1. SQL Injection
        {
            "id": "SEC-SQLI-01",
            "category": "SQL Injection",
            "title": "SQL Injection via Unparameterized Concatenation / Interpolation",
            "pattern": r"(?i)(SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*['\"].*\+|SELECT\s+.*\s+FROM\s+.*\s+WHERE\s+.*\+|f['\"]SELECT\s+.*\s+FROM\s+.*\{|['\"]SELECT\s+.*WHERE.*%s['\"]\s*%|UNION\s+SELECT|OR\s+['\"]?1['\"]?\s*=\s*['\"]?1|;\s*DROP\s+TABLE|;\s*DELETE\s+FROM|cursor\.execute\s*\(\s*f['\"]|cursor\.execute\s*\([^,)]*\+|db\.execute\s*\(\s*['\"]SELECT.*['\"]\s*\+|db\.query\s*\(\s*['\"]SELECT.*['\"]\s*\+|WHERE\s+[\w.]+\s*=\s*['\"]\s*\+)",
            "severity": "critical",
            "impact": "Allows attackers to bypass authentication, execute arbitrary queries, and exfiltrate or modify database records.",
            "remediation": "Use parameterized queries or ORM abstractions (e.g., db.session.execute(text('SELECT * FROM users WHERE id = :id'), {'id': user_id})).",
            "confidence": "high",
        },
        # 2. Hardcoded Secrets - AWS Access Keys
        {
            "id": "SEC-SEC-01",
            "category": "Hardcoded Secret",
            "title": "Hardcoded AWS Access Key ID",
            "pattern": r"(AKIA[0-9A-Z]{16}|AWS_ACCESS_KEY_ID\s*=\s*['\"][^'\"]+['\"])",
            "severity": "critical",
            "impact": "Leaking cloud credentials allows unauthorized administrative access to AWS infrastructure and data.",
            "remediation": "Move credentials to environment variables or a secret management vault (AWS KMS / HashiCorp Vault).",
            "confidence": "high",
        },
        # 3. Hardcoded Secrets - API Tokens & Private Keys
        {
            "id": "SEC-SEC-02",
            "category": "Hardcoded Secret",
            "title": "API Token / Private Key / Credential Leak",
            "pattern": r"(ghp_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{22,}|sk-[0-9a-zA-Z]{20,}|Bearer\s+[a-zA-Z0-9_\-\.]{25,}|-----BEGIN (RSA|OPENSSH|EC|DSA|PRIVATE) KEY-----|secret_key\s*=\s*['\"][^'\"]{6,}['\"]|api_key\s*=\s*['\"][^'\"]{6,}['\"]|JWT_SECRET\s*=\s*['\"][^'\"]{6,}['\"])",
            "severity": "critical",
            "impact": "Exposes sensitive OAuth tokens, private keys, or API credentials enabling unauthorized system access.",
            "remediation": "Revoke compromised tokens immediately and load secrets strictly from runtime environment variables.",
            "confidence": "high",
        },
        # 4. Command Injection & Arbitrary Code Execution
        {
            "id": "SEC-CMD-01",
            "category": "Command Injection",
            "title": "OS Command / Process Injection Risk",
            "pattern": r"(os\.system\s*\(|os\.popen\s*\(|subprocess\.(Popen|call|run|check_output)\s*\(.*shell\s*=\s*True|subprocess\.(Popen|call|run|check_output)\s*\([^,)]*\+|;\s*rm\s+-rf|;\s*cat\s+/etc/passwd|\$\(whoami\)|eval\s*\(|exec\s*\()",
            "severity": "critical",
            "impact": "Allows attackers to execute arbitrary system shell commands with the privileges of the web application.",
            "remediation": "Avoid invoking shell processes with user inputs; use strict parameter lists with shell=False and input validation.",
            "confidence": "high",
        },
        # 5. Cross-Site Scripting (XSS)
        {
            "id": "SEC-XSS-01",
            "category": "Cross-Site Scripting (XSS)",
            "title": "Unsanitized HTML Output / DOM XSS Vector",
            "pattern": r"(<script[^>]*>|javascript:|document\.getElementById\([^)]*\)\.innerHTML\s*=|dangerouslySetInnerHTML|document\.write\s*\(|return\s+['\"]<[^>]+>['\"]\s*\+|render_template_string\s*\(|onerror\s*=|onload\s*=|\.innerHTML\s*=)",
            "severity": "high",
            "impact": "Allows attackers to execute malicious JavaScript in user browsers, leading to session hijacking and credential theft.",
            "remediation": "Sanitize and contextual HTML-encode all user-supplied outputs; use template engines with automatic escaping enabled.",
            "confidence": "high",
        },
        # 6. Insecure Deserialization
        {
            "id": "SEC-DESER-01",
            "category": "Insecure Deserialization",
            "title": "Insecure Object Deserialization",
            "pattern": r"(pickle\.loads?\s*\(|yaml\.load\s*\(.*Loader\s*=\s*yaml\.Loader|yaml\.unsafe_load\s*\(|marshal\.loads?\s*\()",
            "severity": "critical",
            "impact": "Deserializing untrusted byte streams leads directly to arbitrary remote code execution.",
            "remediation": "Replace pickle/marshal with safe serialization formats (JSON, Protocol Buffers) and use yaml.safe_load().",
            "confidence": "high",
        },
        # 7. Path Traversal
        {
            "id": "SEC-PATH-01",
            "category": "Path Traversal",
            "title": "Directory / Path Traversal Sequence",
            "pattern": r"(\.\./\.\./|\.\.\\\.\.\\|/etc/shadow|/etc/passwd|windows/system32|open\s*\([^,)]*\+\s*)",
            "severity": "high",
            "impact": "Allows unauthorized arbitrary reads of server filesystem secrets, system binaries, and configuration files.",
            "remediation": "Sanitize user-provided file paths with werkzeug.utils.secure_filename() and verify paths remain within root.",
            "confidence": "high",
        },
        # 8. Flask Debug Mode Enabled in Production
        {
            "id": "SEC-CONFIG-01",
            "category": "Insecure Configuration",
            "title": "Interactive Debugger / Debug Mode Enabled",
            "pattern": r"(app\.run\s*\(.*debug\s*=\s*True|DEBUG\s*=\s*True)",
            "severity": "high",
            "impact": "Enabling debug mode in production exposes the interactive Werkzeug console pin, enabling remote code execution.",
            "remediation": "Disable debug mode in production environments (set DEBUG=False and use production WSGI servers like Gunicorn).",
            "confidence": "high",
        },
        # 9. Weak Cryptography
        {
            "id": "SEC-CRYPTO-01",
            "category": "Weak Cryptography",
            "title": "Broken or Deprecated Cryptographic Algorithm",
            "pattern": r"(hashlib\.md5\s*\(|hashlib\.sha1\s*\(|Crypto\.Cipher\.DES|DES\.new)",
            "severity": "medium",
            "impact": "MD5 and SHA-1 suffer from proven collision attacks and cannot guarantee data integrity or password security.",
            "remediation": "Upgrade hashing algorithms to SHA-256, SHA-3, or bcrypt/Argon2 for credential verification.",
            "confidence": "high",
        },
        # 10. SSRF / Cloud Metadata
        {
            "id": "SEC-SSRF-01",
            "category": "SSRF",
            "title": "SSRF Target / Cloud Metadata IP",
            "pattern": r"(http://169\.254\.169\.254|http://localhost|http://127\.0\.0\.1)",
            "severity": "high",
            "impact": "Exposes cloud instance metadata tokens and internal intranet services to external callers.",
            "remediation": "Enforce URL hostname allowlists and restrict private IP routing in HTTP client adapters.",
            "confidence": "high",
        },
        # 11. Insecure CORS
        {
            "id": "SEC-CORS-01",
            "category": "Insecure CORS Policy",
            "title": "Overly Permissive Wildcard CORS Header",
            "pattern": r"(Access-Control-Allow-Origin['\"]?\s*:\s*['\"]?\*|CORS\s*\(.*origins\s*=\s*['\"]?\*)",
            "severity": "medium",
            "impact": "Allows unauthorized cross-origin web domains to read response payloads containing sensitive credentials.",
            "remediation": "Restrict Access-Control-Allow-Origin to explicit trusted domain origins.",
            "confidence": "medium",
        },
        # 12. AI Prompt Injection
        {
            "id": "SEC-AI-01",
            "category": "AI Prompt Injection",
            "title": "LLM Jailbreak & Prompt Injection Attempt",
            "pattern": r"(?i)(ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts|rules)|reveal\s+(the\s+)?(system\s+prompt|password|secret|key)|bypass\s+(safety|guardrails|security)|you\s+are\s+now\s+in\s+developer\s+mode|dan\s+mode|disregard\s+all\s+prior)",
            "severity": "critical",
            "impact": "Bypasses AI guardrails, attempts to leak system prompts or override safety policies.",
            "remediation": "Deploy input sanitization guardrails (NeMo Guardrails / Llama Guard) and isolate system instructions.",
            "confidence": "high",
        },
    ]

    def execute(self, context: AgentContext) -> AgentResult:
        start_time = time.time()
        input_data = context.input_data or {}

        scan_type = (input_data.get("scanType") or input_data.get("type") or "static").lower()

        # Load content from file_id, file_path, or content/code parameter
        content, target_name, load_err = self._load_scan_content(input_data, context.user_id)
        if load_err or not content or len(content.strip()) == 0:
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error=load_err or "Source code or configuration is required.",
                execution_duration_ms=duration,
            )

        target = target_name or input_data.get("target") or "User-Provided Source Code"

        # 1. Run Deterministic Static Vulnerability Rule Engine
        findings = self._scan_content(content)

        # 2. Synthesize Security Audit Summary
        summary = self._generate_security_summary(findings, target, scan_type, content)
        duration = int((time.time() - start_time) * 1000)

        critical_count = sum(1 for f in findings if f["severity"] == "critical")
        high_count = sum(1 for f in findings if f["severity"] == "high")
        medium_count = sum(1 for f in findings if f["severity"] == "medium")
        low_count = sum(1 for f in findings if f["severity"] == "low")

        lines_list = content.splitlines()

        output_payload = {
            "scannedTarget": target,
            "target": target,
            "scanType": scan_type,
            "inputSource": "Uploaded File" if input_data.get("file_id") else "User-Provided Source Code",
            "charactersScanned": len(content),
            "linesScanned": len(lines_list),
            "rulesExecuted": len(self.SECURITY_RULES),
            "findingsCount": len(findings),
            "findings": findings,
            "findings_by_severity": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
            },
            "security_score": max(0, 100 - (critical_count * 30 + high_count * 15 + medium_count * 5)),
            "recommendations": [f["remediation"] for f in findings] if findings else ["Maintain standard automated static security testing in CI/CD pipeline."],
            "summary": summary,
            "warnings": [] if findings else ["No static vulnerability patterns detected."],
        }

        artifact = ArtifactRef(
            type="security_audit",
            name=f"security_audit_{context.task_id[:8]}.json",
            content=output_payload,
        )

        return AgentResult(
            success=True,
            agent_type=self.agent_type,
            task_id=context.task_id,
            output=output_payload,
            metadata={
                "critical_count": critical_count,
                "high_count": high_count,
                "medium_count": medium_count,
                "total_findings": len(findings),
                "risk_rating": "CRITICAL" if critical_count > 0 else ("HIGH" if high_count > 0 else ("MEDIUM" if medium_count > 0 else "LOW")),
                "input_source": output_payload["inputSource"],
                "lines_scanned": len(lines_list),
            },
            artifacts=[artifact],
            execution_duration_ms=duration,
        )

    def _load_scan_content(
        self, input_data: Dict[str, Any], user_id: Optional[int]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Resolve scan content from file_id, file_path, or direct string without falling back to sample code."""
        # 1. file_id
        file_id = input_data.get("file_id")
        if file_id:
            file_record, err = FileService.get_file_by_id(file_id, user_id=user_id)
            if err or not file_record:
                return None, None, err or f"File '{file_id}' not found."
            try:
                with open(file_record.storage_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(), file_record.filename, None
            except Exception as e:
                return None, None, f"Failed to read file: {str(e)}"

        # 2. file_path
        file_path = input_data.get("file_path")
        if file_path and isinstance(file_path, str):
            if not os.path.exists(file_path):
                return None, None, f"File path '{file_path}' does not exist."
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(), os.path.basename(file_path), None
            except Exception as e:
                return None, None, f"Failed to read file: {str(e)}"

        # 3. Direct content / code / source parameter
        raw = (
            input_data.get("content")
            or input_data.get("source_code")
            or input_data.get("code_snippet")
            or input_data.get("source")
            or input_data.get("code")
            or input_data.get("text")
            or input_data.get("payload")
            or input_data.get("instructions")
            or input_data.get("prompt")
        )
        if raw and isinstance(raw, str) and raw.strip():
            target_label = input_data.get("target") or "User-Provided Source Code"
            return raw, target_label, None

        if isinstance(raw, dict) and raw:
            import json
            target_label = input_data.get("target") or "User-Provided Configuration"
            return json.dumps(raw, indent=2), target_label, None

        return None, None, "Source code or configuration is required."

    def _scan_content(self, content: str) -> List[Dict[str, Any]]:
        """Match rules line-by-line and across full content, extracting exact line numbers and genuine evidence."""
        findings: List[Dict[str, Any]] = []
        matched_rule_ids = set()
        lines = content.splitlines()

        # Step 1: Scan line by line for precise line numbering and exact evidence
        for line_idx, line_text in enumerate(lines, start=1):
            for rule in self.SECURITY_RULES:
                rule_id = rule["id"]
                if re.search(rule["pattern"], line_text, re.IGNORECASE):
                    # Mask secrets in evidence output for safety
                    evidence_display = line_text.strip()
                    if "Secret" in rule["category"]:
                        evidence_display = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA****MASKED", evidence_display)
                        evidence_display = re.sub(r"ghp_[0-9a-zA-Z]{36}", "ghp_****MASKED", evidence_display)
                        evidence_display = re.sub(r"sk-[0-9a-zA-Z]{20,}", "sk-****MASKED", evidence_display)

                    findings.append({
                        "id": rule_id,
                        "title": rule["title"],
                        "severity": rule["severity"],
                        "category": rule["category"],
                        "line": line_idx,
                        "evidence": evidence_display,
                        "impact": rule["impact"],
                        "remediation": rule["remediation"],
                        "confidence": rule["confidence"],
                    })
                    matched_rule_ids.add(rule_id)

        # Step 2: Scan full multiline content for patterns that span across lines
        for rule in self.SECURITY_RULES:
            rule_id = rule["id"]
            if rule_id in matched_rule_ids:
                continue

            match = re.search(rule["pattern"], content, re.IGNORECASE | re.DOTALL)
            if match:
                start_char = match.start()
                line_no = content[:start_char].count("\n") + 1
                matched_line = lines[line_no - 1] if line_no <= len(lines) else match.group(0)[:80]
                evidence_display = matched_line.strip()
                if "Secret" in rule["category"]:
                    evidence_display = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA****MASKED", evidence_display)
                    evidence_display = re.sub(r"ghp_[0-9a-zA-Z]{36}", "ghp_****MASKED", evidence_display)

                findings.append({
                    "id": rule_id,
                    "title": rule["title"],
                    "severity": rule["severity"],
                    "category": rule["category"],
                    "line": line_no,
                    "evidence": evidence_display,
                    "impact": rule["impact"],
                    "remediation": rule["remediation"],
                    "confidence": rule["confidence"],
                })
                matched_rule_ids.add(rule_id)

        return findings

    def _generate_security_summary(self, findings: List[Dict[str, Any]], target: str, scan_type: str, content: str) -> str:
        """Construct audit conclusion string with deterministic adherence to findings."""
        line_count = len(content.splitlines())
        if not findings:
            return f"Static security scan of '{target}' ({scan_type}) completed cleanly. Zero vulnerability patterns detected across {line_count} line(s) scanned."

        sev_counts = {}
        for f in findings:
            s = f["severity"]
            sev_counts[s] = sev_counts.get(s, 0) + 1

        counts_str = ", ".join([f"{count} {sev.upper()}" for sev, count in sev_counts.items()])
        rule_summary = f"Static security audit identified {len(findings)} vulnerability finding(s) on target '{target}': {counts_str}."
        llm_summary = self._synthesize_with_llm(findings, target, scan_type)
        return llm_summary if llm_summary else rule_summary

    def _synthesize_with_llm(self, findings: List[Dict[str, Any]], target: str, scan_type: str) -> Optional[str]:
        """Generate executive security narrative and prioritized remediation plan via real LLM."""
        try:
            from app.services.provider_health_service import ProviderHealthManager
            if ProviderHealthManager.is_testing_environment():
                return None

            from app.llm.contracts import LLMMessage, LLMRequest
            from app.llm.registry import provider_registry
            import json

            provider, model = provider_registry.resolve_provider_and_model()
            system_prompt = (
                "You are an enterprise AppSec Lead and Penetration Testing specialist. "
                "Analyze the verified static security scanner findings for the target asset. "
                "Provide an Executive Risk Assessment, Threat Exposure Analysis, and a Prioritized Remediation Roadmap.\n\n"
                "STRICT GROUNDING RULES:\n"
                "1. Base your assessment ONLY on the actual findings provided. Do NOT hallucinate fake CVEs, "
                "fabricated vulnerabilities, or unrelated issues not present in the scan.\n"
                "2. Provide concrete, actionable secure coding examples for remediating each detected finding.\n"
                "3. Format cleanly using GitHub Markdown."
            )
            findings_data = [
                {
                    "id": f["id"],
                    "title": f["title"],
                    "severity": f["severity"],
                    "category": f["category"],
                    "line": f["line"],
                    "evidence": f["evidence"],
                    "impact": f["impact"],
                    "remediation": f["remediation"],
                }
                for f in findings
            ]
            user_msg = (
                f"Target Asset: {target}\n"
                f"Scan Type: {scan_type}\n"
                f"Verified Findings ({len(findings)} detected):\n"
                f"{json.dumps(findings_data, indent=2)}"
            )
            req = LLMRequest(
                provider=provider.provider_name,
                model=model,
                system_instructions=system_prompt,
                messages=[LLMMessage(role="user", content=user_msg)],
                temperature=0.2,
                max_tokens=1000,
            )
            resp = provider.generate(req)
            if resp.text and len(resp.text.strip()) > 50:
                return resp.text.strip()
        except Exception:
            return None
        return None
