"""
Unit tests verifying arbitrary topic and upstream multi-agent context synthesis for ReportGenerationAgent.
"""

import os
from app.agents.base import AgentContext
from app.agents.report_generation_agent import ReportGenerationAgent


def test_report_generation_arbitrary_topic_with_upstream_pipeline_data():
    agent = ReportGenerationAgent()
    
    # Simulate upstream Document Research output and Data Analysis output
    previous_results = [
        {
            "agent_type": "document_research",
            "node_name": "Healthcare AI Literature Review",
            "output": {
                "answer": "Clinical trials indicate generative diagnostic models improve oncology detection accuracy by 18.4% when paired with radiologist oversight.",
                "key_points": [
                    "Oncology detection accuracy increased by 18.4%.",
                    "False-positive biopsies decreased by 12.2% across three clinical trial sites.",
                    "HIPAA-compliant on-premises inference mitigates patient privacy concerns."
                ],
                "sources": [
                    {
                        "documentName": "Clinical_AI_Oncology_Study_2025.pdf",
                        "page": 14,
                        "excerpt": "Diagnostic accuracy reached 96.2% when AI recommendations were verified by attending physicians."
                    }
                ],
                "confidence": "high"
            }
        },
        {
            "agent_type": "data_analysis",
            "node_name": "Hospital Trial Metrics",
            "output": {
                "summary": "Statistical evaluation of 4,200 patient screening records across 6 metropolitan hospitals.",
                "statistics": {
                    "accuracy_score": {
                        "mean": 0.962,
                        "min": 0.912,
                        "max": 0.994,
                        "std": 0.018,
                        "median": 0.965
                    },
                    "processing_time_sec": {
                        "mean": 3.42,
                        "min": 1.2,
                        "max": 8.5,
                        "std": 1.1,
                        "median": 3.1
                    }
                },
                "insights": [
                    "Average diagnostic response time was 3.42 seconds per scan.",
                    "No significant performance degradation observed during peak admission hours."
                ]
            }
        }
    ]

    ctx = AgentContext(
        input_data={
            "topic": "AI in Healthcare: Clinical Diagnostic Adoption",
            "format": "markdown",
        },
        previous_results=previous_results,
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.agent_type == "report_generation"
    assert "AI in Healthcare" in result.output["reportTitle"]
    
    sections = result.output["sections"]
    section_titles = [s["title"] for s in sections]
    assert any("Executive Summary" in t for t in section_titles)
    assert any("Key Findings" in t for t in section_titles)
    assert any("Analysis" in t for t in section_titles)
    
    # Content must reflect the upstream data
    full_text = "\n".join([s["content"] for s in sections])
    assert "18.4%" in full_text
    assert "Clinical_AI_Oncology_Study_2025.pdf" in full_text
    assert "accuracy_score" in full_text or "3.42" in full_text

    # Verify generated artifact exists and is cleaned up
    artifact_path = result.output["artifact"]["path"]
    assert os.path.exists(artifact_path)
    os.remove(artifact_path)
