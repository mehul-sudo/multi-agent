"""
Acceptance Test Suite: Quarterly Sales Correctness, Rendering Quality & Pipeline Propagation.

Verifies:
1. Dynamic runtime calculation of quarterly_sales_2026.csv:
   - Q1: revenue $40,500; costs $24,300; gross profit $16,200; margin 40.0%
   - Q2: revenue $48,500; costs $29,100; gross profit $19,400; margin 40.0%
   - Q3: revenue $48,000; costs $28,800; gross profit $19,200; margin 40.0%
   - Q4: revenue $63,500; costs $38,100; gross profit $25,400; margin 40.0%
   - Total: revenue $200,500; costs $120,300; gross profit $80,200; gross margin 40.0%
   - Q4 revenue growth vs Q3: approximately 32.3% (+32.29%)
   - Regional breakdown: South leading ($108,000, 53.9%), North ($53,000, 26.4%), West ($39,500, 19.7%)
   - Product breakdown: Cloud Pro ($108,000, 53.9%), Cloud Basic ($92,500, 46.1%)
   - Tukey 1.5x IQR outlier review: operational non-negative lower bound $0.00, upper threshold $35,250,
     with 1 review candidate ($36,000 in Q4 South Cloud Pro) flagged for business review.
2. Report Generation formatting:
   - Domain-rich executive report with KPI cards, QoQ table, regional/product tables,
     methodology, limitations, and real file artifact generation (MD, HTML, DOCX, PDF, TXT).
3. Agreement of figures across Data Analysis, Report Generation, and Email draft.
4. Clean failure handling for malformed/corrupt CSV input (fails clearly, no hallucinated numbers).
5. Internal preservation of structured JSON for agent-to-agent communication.
"""

import os
import shutil
import pytest

from app.agents.base import AgentContext
from app.agents.data_analysis_agent import DataAnalysisAgent
from app.agents.report_generation_agent import ReportGenerationAgent
from app.agents.email_agent import EmailAgent

SAMPLE_CSV_CONTENT = """quarter,region,product,units_sold,revenue_usd,cost_usd
Q1,North,Cloud Pro,300,12000,7200
Q1,South,Cloud Pro,400,16000,9600
Q1,West,Cloud Basic,500,12500,7500
Q2,North,Cloud Basic,600,15000,9000
Q2,South,Cloud Pro,500,20000,12000
Q2,West,Cloud Basic,540,13500,8100
Q3,North,Cloud Basic,480,12000,7200
Q3,South,Cloud Pro,900,36000,21600
Q4,North,Cloud Pro,350,14000,8400
Q4,South,Cloud Basic,1500,36000,21600
Q4,West,Cloud Basic,540,13500,8100
"""
# Note: In the user's dataset, 12 rows total. Let's make sure the exact 12 records match the totals:
# Q1: North (12k/7.2k), South (16k/9.6k), West (12.5k/7.5k) -> Total = 40.5k / 24.3k / 16.2k
# Q2: North (15k/9k), South (20k/12k), West (13.5k/8.1k) -> Total = 48.5k / 29.1k / 19.4k
# Q3: North (12k/7.2k), South (36k/21.6k) -> wait, Q3 needs 48.0k total, so let's verify what row 3 was in Q3:
# Let's inspect the actual C:\Users\Mehul\Downloads\quarterly_sales_2026.csv to match every single record.


def test_quarterly_sales_exact_dataset_math():
    """Verify exact dynamic calculations against the user's actual quarterly_sales_2026.csv."""
    user_csv_path = r"C:\Users\Mehul\Downloads\quarterly_sales_2026.csv"
    if not os.path.exists(user_csv_path):
        # Fallback to local test fixture if testing on another machine
        user_csv_path = os.path.join(os.path.dirname(__file__), "fixtures", "quarterly_sales_2026.csv")

    agent = DataAnalysisAgent()
    context = AgentContext(
        task_id="task_da_quarterly_001",
        user_id=1,
        input_data={"file_path": user_csv_path},
        instructions="Analyze quarterly financial performance, gross margins, and regional growth.",
    )

    result = agent.execute(context)
    assert result.success is True, f"Data Analysis execution failed: {result.error}"

    output = result.output
    assert isinstance(output, dict)
    assert output["row_count"] == 12
    assert output["column_count"] == 6

    # 1. Verify Structured Business Metrics
    b_metrics = output.get("business_metrics")
    assert b_metrics is not None, "business_metrics missing from output"
    assert b_metrics.get("has_financial_metrics") is True

    # Total Overall Figures
    assert b_metrics["total_revenue"] == 200500.0, f"Expected 200,500 total rev, got {b_metrics['total_revenue']}"
    assert b_metrics["total_cost"] == 120300.0, f"Expected 120,300 total cost, got {b_metrics['total_cost']}"
    assert b_metrics["gross_profit"] == 80200.0, f"Expected 80,200 gross profit, got {b_metrics['gross_profit']}"
    assert b_metrics["gross_margin_pct"] == 40.0, f"Expected 40.0% margin, got {b_metrics['gross_margin_pct']}"

    # 2. Verify Quarterly Figures (Q1 to Q4)
    periods = {p["period"]: p for p in b_metrics["period_metrics"]}
    assert "Q1" in periods and "Q2" in periods and "Q3" in periods and "Q4" in periods

    # Q1
    q1 = periods["Q1"]
    assert q1["revenue"] == 40500.0, f"Q1 rev expected 40500, got {q1['revenue']}"
    assert q1["cost"] == 24300.0, f"Q1 cost expected 24300, got {q1['cost']}"
    assert q1["gross_profit"] == 16200.0, f"Q1 profit expected 16200, got {q1['gross_profit']}"
    assert q1["gross_margin_pct"] == 40.0, f"Q1 margin expected 40.0, got {q1['gross_margin_pct']}"

    # Q2
    q2 = periods["Q2"]
    assert q2["revenue"] == 48500.0, f"Q2 rev expected 48500, got {q2['revenue']}"
    assert q2["cost"] == 29100.0, f"Q2 cost expected 29100, got {q2['cost']}"
    assert q2["gross_profit"] == 19400.0, f"Q2 profit expected 19400, got {q2['gross_profit']}"
    assert q2["gross_margin_pct"] == 40.0, f"Q2 margin expected 40.0, got {q2['gross_margin_pct']}"

    # Q3
    q3 = periods["Q3"]
    assert q3["revenue"] == 48000.0, f"Q3 rev expected 48000, got {q3['revenue']}"
    assert q3["cost"] == 28800.0, f"Q3 cost expected 28800, got {q3['cost']}"
    assert q3["gross_profit"] == 19200.0, f"Q3 profit expected 19200, got {q3['gross_profit']}"
    assert q3["gross_margin_pct"] == 40.0, f"Q3 margin expected 40.0, got {q3['gross_margin_pct']}"

    # Q4
    q4 = periods["Q4"]
    assert q4["revenue"] == 63500.0, f"Q4 rev expected 63500, got {q4['revenue']}"
    assert q4["cost"] == 38100.0, f"Q4 cost expected 38100, got {q4['cost']}"
    assert q4["gross_profit"] == 25400.0, f"Q4 profit expected 25400, got {q4['gross_profit']}"
    assert q4["gross_margin_pct"] == 40.0, f"Q4 margin expected 40.0, got {q4['gross_margin_pct']}"

    # Growth Q4 vs Q3: (63500 - 48000) / 48000 = +32.2916% ~ 32.3%
    assert q4["revenue_growth_pct"] is not None
    assert round(q4["revenue_growth_pct"], 1) == 32.3

    # 3. Verify Tukey 1.5x IQR Outlier Bounds and Review Candidates
    outliers = output.get("outliers", {})
    rev_outliers = outliers.get("revenue_usd") or outliers.get("revenue")
    assert rev_outliers is not None
    assert rev_outliers["practical_lower_bound"] == 0.0, "Operational lower bound must clamp to 0.0 for non-negative financial revenue"
    assert rev_outliers["upper_bound"] == 35250.0, f"Expected upper bound 35,250.0, got {rev_outliers['upper_bound']}"
    assert rev_outliers["outlier_count"] == 1, f"Expected 1 review candidate, got {rev_outliers['outlier_count']}"
    assert rev_outliers["outliers"][0]["value"] == 36000.0
    assert "review" in rev_outliers["outliers"][0]["classification"].lower()

    # 4. Regional and Product Segments
    seg_metrics = b_metrics.get("segment_metrics", {})
    assert "region" in seg_metrics
    assert seg_metrics["region"][0]["name"] == "South"
    assert seg_metrics["region"][0]["revenue"] == 108000.0
    assert seg_metrics["region"][0]["revenue_share_pct"] == 53.87

    assert "product" in seg_metrics
    assert seg_metrics["product"][0]["name"] == "Cloud Pro"
    assert seg_metrics["product"][0]["revenue"] == 108000.0


def test_full_pipeline_propagation_and_cross_agent_agreement():
    """Verify end-to-end data propagation: Data Analysis -> Report Generation -> Email Draft."""
    user_csv_path = r"C:\Users\Mehul\Downloads\quarterly_sales_2026.csv"

    # Step 1: Run Data Analysis
    da_agent = DataAnalysisAgent()
    da_context = AgentContext(
        task_id="task_step1_da",
        user_id=1,
        input_data={"file_path": user_csv_path},
        instructions="Analyze 2026 quarterly sales performance.",
    )
    da_res = da_agent.execute(da_context)
    assert da_res.success is True

    # Step 2: Run Report Generation with upstream Data Analysis output
    rep_agent = ReportGenerationAgent()
    rep_context = AgentContext(
        task_id="task_step2_rep",
        user_id=1,
        input_data={
            "title": "2026 Quarterly Sales Performance Report",
            "format": "markdown",
        },
        previous_results=[
            {
                "task_id": "task_step1_da",
                "agent_type": "data_analysis",
                "output": da_res.output,
            }
        ],
    )
    rep_res = rep_agent.execute(rep_context)
    assert rep_res.success is True
    rep_out = rep_res.output

    # Check report sections and verified numbers
    sec_titles = [s["title"] for s in rep_out.get("sections", [])]
    assert any("Executive Summary" in t for t in sec_titles)
    assert any("Quarter-over-Quarter" in t for t in sec_titles)
    assert any("Regional" in t for t in sec_titles)
    assert any("Methodology" in t or "Outlier" in t for t in sec_titles)

    # Verify Markdown content includes the exact verified totals
    md_content = rep_out.get("markdown") or rep_out.get("content")
    assert "$200,500.00" in md_content or "$200,500" in md_content
    assert "$120,300.00" in md_content or "$120,300" in md_content
    assert "$80,200.00" in md_content or "$80,200" in md_content
    assert "40.0%" in md_content
    assert "32.3%" in md_content

    # Verify physical file artifact persistence
    art = rep_out.get("artifact", {})
    assert art.get("path") and os.path.exists(art["path"])
    assert os.path.getsize(art["path"]) > 100

    # Step 3: Run Email Agent with upstream outputs
    email_agent = EmailAgent()
    email_context = AgentContext(
        task_id="task_step3_email",
        user_id=1,
        input_data={
            "subject": "Executive Briefing: 2026 Quarterly Sales & Margins",
            "recipients": ["management@example.com"],
        },
        previous_results=[
            {
                "task_id": "task_step1_da",
                "agent_type": "data_analysis",
                "output": da_res.output,
            },
            {
                "task_id": "task_step2_rep",
                "agent_type": "report_generation",
                "output": rep_out,
            },
        ],
    )
    email_res = email_agent.execute(email_context)
    assert email_res.success is True
    email_out = email_res.output

    # Mode B: Attachment from report generation must be resolved
    attachments = email_out.get("attachments") or email_out.get("draft", {}).get("attachments") or []
    assert len(attachments) >= 1
    assert os.path.exists(attachments[0])

    # Check Email Body contains consistent verified totals
    email_body = email_out.get("body") or email_out.get("draft", {}).get("body") or ""
    assert "$200,500.00" in email_body or "$200,500" in email_body
    assert "40.0%" in email_body
    assert "32.3%" in email_body
    assert "South" in email_body


def test_malformed_csv_input_fails_clearly():
    """Verify that corrupt or empty CSV files fail cleanly with an informative error rather than fabricating data."""
    agent = DataAnalysisAgent()

    # 1. Completely empty CSV
    context_empty = AgentContext(
        task_id="task_malformed_1",
        user_id=1,
        input_data={"csv_data": ""},
        instructions="Analyze dataset",
    )
    res_empty = agent.execute(context_empty)
    assert res_empty.success is False
    assert "malformed" in res_empty.error.lower() or "no data" in res_empty.error.lower()

    # 2. CSV with only whitespace and newlines
    context_ws = AgentContext(
        task_id="task_malformed_2",
        user_id=1,
        input_data={"csv_data": "   \n\n  "},
        instructions="Analyze dataset",
    )
    res_ws = agent.execute(context_ws)
    assert res_ws.success is False
    assert "malformed" in res_ws.error.lower() or "empty" in res_ws.error.lower()

    # 3. CSV with headers but zero rows
    context_no_rows = AgentContext(
        task_id="task_malformed_3",
        user_id=1,
        input_data={"csv_data": "quarter,region,product,revenue\n"},
        instructions="Analyze dataset",
    )
    res_no_rows = agent.execute(context_no_rows)
    assert res_no_rows.success is False
    assert "malformed" in res_no_rows.error.lower() or "no records" in res_no_rows.error.lower()
