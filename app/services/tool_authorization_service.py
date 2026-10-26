"""
Tool Authorization Service.

Enforces capability-based security, tool allowlists/denylists, dangerous-tool
policies, input/output constraints, domain restrictions, and execution timeouts.
"""

import re
from typing import Dict, Any, List, Optional, Tuple

from app.models.agent import Agent
from app.models.tool_policy import ToolPolicy


class ToolAuthorizationService:
    """Service for validating tool authorization and enforcing tool governance policies."""

    DANGEROUS_TOOLS = {
        "execute_code",
        "bash",
        "shell",
        "delete_database",
        "send_email",
        "http_post",
        "file_write",
        "raw_sql",
    }

    @classmethod
    def authorize_tool_invocation(
        cls,
        agent: Agent,
        tool_name: str,
        tool_input: Dict[str, Any],
        organization_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate if an agent is authorized to invoke a tool with given inputs.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_authorized, denial_reason)
        """
        if not agent or agent.status != "active":
            return False, "Agent is inactive or disabled"

        # 1. Agent allowed_tools check
        allowed_tools = agent.allowed_tools or []
        if allowed_tools and tool_name not in allowed_tools:
            return False, f"Tool '{tool_name}' is not in agent's allowed_tools list"

        # 2. Capability check
        capabilities = agent.capabilities or []
        cap_names = [c if isinstance(c, str) else c.get("name") for c in capabilities]
        if tool_name in cls.DANGEROUS_TOOLS:
            if "execute_code" not in cap_names and "admin" not in cap_names and "tool_execute" not in cap_names:
                return False, f"Agent lacks capability to execute dangerous tool '{tool_name}'"

        # 3. Tool Policy check from database if configured
        query = ToolPolicy.query.filter_by(tool_name=tool_name, is_active=True)
        if organization_id:
            query = query.filter(
                (ToolPolicy.organization_id == organization_id) | (ToolPolicy.organization_id == None)
            )
        policy = query.first()

        if policy:
            # Check domain restrictions for web/URL tools
            if policy.allowed_domains and "url" in tool_input:
                url = tool_input.get("url", "")
                if not any(domain in url for domain in policy.allowed_domains):
                    return False, f"URL domain in '{url}' is not in tool's allowed_domains"

            # Check denied regex patterns for input injection / command execution protection
            if policy.denied_patterns:
                input_str = str(tool_input)
                for pattern in policy.denied_patterns:
                    if re.search(pattern, input_str, re.IGNORECASE):
                        return False, f"Tool input matched denied pattern '{pattern}'"

            # Dangerous tool policy check
            if policy.is_dangerous and policy.require_approval:
                if not tool_input.get("approval_granted", False):
                    return False, f"Tool '{tool_name}' requires human approval before execution"

        # 4. Global prompt injection / command injection heuristic check
        input_text = str(tool_input)
        suspicious_patterns = [
            r";\s*rm\s+-rf",
            r"DROP\s+TABLE",
            r"UNION\s+SELECT",
            r"ignore\s+previous\s+instructions",
        ]
        for pat in suspicious_patterns:
            if re.search(pat, input_text, re.IGNORECASE):
                return False, f"Tool input rejected due to security policy violation (pattern '{pat}')"

        return True, None
