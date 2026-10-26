"""
Unit tests for SecurityAnalysisAgent.
"""

import pytest
from app.agents.base import AgentContext
from app.agents.security_analysis_agent import SecurityAnalysisAgent


def test_security_analysis_agent_mandatory_sqli_test():
    """Mandatory SQL Injection test with exact user input."""
    agent = SecurityAnalysisAgent()
    vulnerable_code = (
        'username = request.args.get("username")\n'
        'query = "SELECT * FROM users WHERE username = \'" + username + "\'"\n'
    )
    ctx = AgentContext(
        input_data={"content": vulnerable_code, "target": "auth.py"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.agent_type == "security_analysis"
    assert len(result.output["findings"]) >= 1

    sqli = [f for f in result.output["findings"] if f["category"] == "SQL Injection"][0]
    assert sqli["severity"] == "critical"
    assert sqli["line"] == 2
    assert "query =" in sqli["evidence"]
    assert "remediation" in sqli


def test_security_analysis_agent_mandatory_hardcoded_secret():
    """Mandatory Hardcoded Secret test with fake AWS key."""
    agent = SecurityAnalysisAgent()
    secret_code = 'AWS_ACCESS_KEY_ID = "AKIAEXAMPLE1234567890"\n'
    ctx = AgentContext(
        input_data={"content": secret_code, "target": "config.py"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert len(result.output["findings"]) >= 1

    sec_finding = [f for f in result.output["findings"] if f["category"] == "Hardcoded Secret"][0]
    assert sec_finding["severity"] == "critical"
    assert sec_finding["line"] == 1
    assert "AKIA****MASKED" in sec_finding["evidence"] or "AWS_ACCESS_KEY_ID" in sec_finding["evidence"]


def test_security_analysis_agent_mandatory_command_injection():
    """Mandatory Command Injection test."""
    agent = SecurityAnalysisAgent()
    cmd_code = (
        'import os\n'
        'os.system("ping " + user_input)\n'
    )
    ctx = AgentContext(
        input_data={"content": cmd_code, "target": "network_tool.py"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert len(result.output["findings"]) >= 1

    cmd_finding = [f for f in result.output["findings"] if f["category"] == "Command Injection"][0]
    assert cmd_finding["severity"] == "critical"
    assert cmd_finding["line"] == 2
    assert "os.system" in cmd_finding["evidence"]


def test_security_analysis_agent_mandatory_xss():
    """Mandatory Cross-Site Scripting (XSS) test."""
    agent = SecurityAnalysisAgent()
    xss_code = 'return "<div>" + user_input + "</div>"\n'
    ctx = AgentContext(
        input_data={"content": xss_code, "target": "views.py"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert len(result.output["findings"]) >= 1

    xss_finding = [f for f in result.output["findings"] if f["category"] == "Cross-Site Scripting (XSS)"][0]
    assert xss_finding["severity"] == "high"
    assert xss_finding["line"] == 1


def test_security_analysis_agent_flask_debug_mode():
    """Detect Flask Debug Mode in production."""
    agent = SecurityAnalysisAgent()
    debug_code = (
        'from flask import Flask\n'
        'app = Flask(__name__)\n'
        'app.run(debug=True)\n'
    )
    ctx = AgentContext(
        input_data={"content": debug_code, "target": "app.py"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert len(result.output["findings"]) >= 1

    debug_finding = [f for f in result.output["findings"] if f["category"] == "Insecure Configuration"][0]
    assert debug_finding["severity"] == "high"
    assert debug_finding["line"] == 3


def test_security_analysis_agent_clean_code_zero_findings():
    """Safe code must result in 0 findings and clean summary."""
    agent = SecurityAnalysisAgent()
    clean_code = (
        'def add(a, b):\n'
        '    return a + b\n'
    )
    ctx = AgentContext(
        input_data={"content": clean_code, "target": "math_utils.py"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert len(result.output["findings"]) == 0
    assert "Zero vulnerability patterns detected" in result.output["summary"]
    assert result.output["findingsCount"] == 0
    assert result.output["scannedTarget"] == "math_utils.py"


def test_security_analysis_agent_empty_input_fails_validation():
    """Empty or missing input must return validation error and not scan sample code."""
    agent = SecurityAnalysisAgent()
    ctx = AgentContext(input_data={})
    result = agent.execute(ctx)
    assert result.success is False
    assert "Source code or configuration is required" in result.error


def test_security_analysis_agent_whitespace_only_fails_validation():
    """Whitespace-only input must fail validation."""
    agent = SecurityAnalysisAgent()
    ctx = AgentContext(input_data={"content": "   \n\t  \n "})
    result = agent.execute(ctx)
    assert result.success is False
    assert "Source code or configuration is required" in result.error


def test_security_analysis_agent_technical_metadata():
    """Technical details metadata must be accurately populated."""
    agent = SecurityAnalysisAgent()
    code = "x = 1\ny = 2\nz = x + y\n"
    ctx = AgentContext(input_data={"content": code, "target": "calc.py"})
    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["charactersScanned"] == len(code)
    assert result.output["linesScanned"] == 3
    assert result.output["rulesExecuted"] >= 10
    assert result.output["inputSource"] == "User-Provided Source Code"
