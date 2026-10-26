"""
Agents Package.

Registers all 7 specialized enterprise agents into global AGENT_REGISTRY:
- DataAnalysisAgent ('data_analysis')
- DocumentResearchAgent ('document_research')
- ReportGenerationAgent ('report_generation')
- EmailAgent ('email')
- DatabaseBIAgent ('database_bi')
- HttpWebhookAgent ('http_webhook')
- SecurityAnalysisAgent ('security_analysis')
"""

from app.agents.base import AgentContext, AgentResult, ArtifactRef, BaseAgent
from app.agents.data_analysis_agent import DataAnalysisAgent
from app.agents.database_bi_agent import DatabaseBIAgent
from app.agents.document_research_agent import DocumentResearchAgent
from app.agents.email_agent import EmailAgent
from app.agents.http_webhook_agent import HttpWebhookAgent
from app.agents.registry import (
    get_agent_instance,
    is_agent_registered,
    list_registered_agent_types,
    register_agent,
)
from app.agents.report_generation_agent import ReportGenerationAgent
from app.agents.security_analysis_agent import SecurityAnalysisAgent
from app.agents.content_generation_agent import ContentGenerationAgent

# Automatically register instances of specialized agents
register_agent(DataAnalysisAgent())
register_agent(DocumentResearchAgent())
register_agent(ReportGenerationAgent())
register_agent(EmailAgent())
register_agent(DatabaseBIAgent())
register_agent(HttpWebhookAgent())
register_agent(SecurityAnalysisAgent())
register_agent(ContentGenerationAgent())

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResult",
    "ArtifactRef",
    "register_agent",
    "get_agent_instance",
    "list_registered_agent_types",
    "is_agent_registered",
    "DataAnalysisAgent",
    "DocumentResearchAgent",
    "ReportGenerationAgent",
    "EmailAgent",
    "DatabaseBIAgent",
    "HttpWebhookAgent",
    "SecurityAnalysisAgent",
    "ContentGenerationAgent",
]
