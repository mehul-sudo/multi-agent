"""
Unit tests for DataAnalysisAgent.
"""

import pytest
from app.agents.base import AgentContext
from app.agents.data_analysis_agent import DataAnalysisAgent


def test_data_analysis_agent_with_rows():
    agent = DataAnalysisAgent()
    ctx = AgentContext(
        input_data={
            "rows": [
                {"category": "Electronics", "sales": 100, "profit": 20},
                {"category": "Electronics", "sales": 200, "profit": 50},
                {"category": "Apparel", "sales": 150, "profit": 30},
                {"category": "Apparel", "sales": 50, "profit": 10},
            ],
            "groupby": "category",
            "aggregate_column": "sales",
        },
        instructions="Analyze quarterly sales figures.",
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.agent_type == "data_analysis"
    assert "statistics" in result.output
    assert "sales" in result.output["statistics"]
    assert result.output["statistics"]["sales"]["mean"] == 125.0
    assert result.output["statistics"]["sales"]["sum"] == 500.0
    assert "dataQuality" in result.output
    assert result.output["dataQuality"]["total_rows"] == 4
    assert len(result.artifacts) == 1


def test_data_analysis_agent_with_csv_string():
    agent = DataAnalysisAgent()
    csv_content = "item,price,quantity\nLaptop,1200,5\nMouse,25,20\nKeyboard,75,10\n"
    ctx = AgentContext(
        input_data={"csv_data": csv_content},
        instructions="Audit inventory data.",
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["dataQuality"]["total_rows"] == 3
    assert "price" in result.output["statistics"]
    assert result.output["statistics"]["price"]["min"] == 25.0
    assert result.output["statistics"]["price"]["max"] == 1200.0

def test_data_analysis_agent_empty_data_fails_gracefully():
    agent = DataAnalysisAgent()
    ctx = AgentContext(input_data={"rows": []})
    result = agent.execute(ctx)
    assert result.success is False
    assert "No data rows" in result.error


def test_data_analysis_agent_percentiles_and_outliers():
    agent = DataAnalysisAgent()
    # Values with intentional outlier (1000)
    data = [10, 12, 14, 15, 16, 18, 20, 22, 1000]
    ctx = AgentContext(input_data={"numbers": data}, instructions="Find anomalies in metrics")
    result = agent.execute(ctx)
    assert result.success is True
    stats = result.output["statistics"]["value"]
    assert stats["count"] == 9
    assert stats["min"] == 10.0
    assert stats["max"] == 1000.0
    assert stats["iqr"] > 0
    assert "outliers" in result.output
    outliers = result.output["outliers"]["value"]
    assert outliers["outlier_count"] >= 1
    assert any(o["value"] == 1000.0 for o in outliers["outliers"])


def test_data_analysis_agent_correlation_and_categorical():
    agent = DataAnalysisAgent()
    rows = [
        {"dept": "Sales", "spend": 100, "revenue": 300},
        {"dept": "Sales", "spend": 200, "revenue": 600},
        {"dept": "Marketing", "spend": 300, "revenue": 900},
        {"dept": "Engineering", "spend": 400, "revenue": 1200},
    ]
    ctx = AgentContext(input_data={"rows": rows})
    result = agent.execute(ctx)
    assert result.success is True
    # Perfect linear correlation between spend and revenue
    corrs = result.output["correlations"]
    assert "spend" in corrs and "revenue" in corrs
    assert round(corrs["spend"]["revenue"], 2) == 1.0
    # Categorical distribution
    cat_dist = result.output["categoricalDistributions"]
    assert "dept" in cat_dist
    assert cat_dist["dept"]["cardinality"] == 3
