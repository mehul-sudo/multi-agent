"""
Unit tests for DocumentResearchAgent with grounded extraction across PPTX, PDF, DOCX, TXT.
"""

import os
import pytest
from app.agents.base import AgentContext
from app.agents.document_research_agent import DocumentResearchAgent
from app.services.file_service import FileService


def test_document_research_agent_inline_text():
    agent = DocumentResearchAgent()
    sample_text = (
        "Enterprise Security Policy 2026.\n"
        "Section 1: Access Control requires Multi-Factor Authentication (MFA) for all users.\n"
        "Section 2: Data Encryption mandates AES-256 for all stored data.\n"
        "Section 3: Audit logging entries must be retained for at least 365 days."
    )
    ctx = AgentContext(
        input_data={"text": sample_text, "document_name": "SecurityPolicy.txt", "query": "What are the requirements for data encryption?"},
    )

    result = agent.execute(ctx)
    assert result.success is True
    assert result.agent_type == "document_research"
    assert "sources" in result.output
    assert len(result.output["sources"]) > 0
    assert result.output["confidence"] in ("high", "medium")
    assert "AES-256" in result.output["sources"][0]["excerpt"] or "Encryption" in result.output["answer"]


def test_document_research_agent_access_control():
    agent = DocumentResearchAgent()
    # User 1 attempting to access user 2's document
    docs = [
        {"id": "doc_secret", "name": "Confidential.txt", "text": "Top secret financial plans.", "owner_id": 999}
    ]
    ctx = AgentContext(
        user_id=1,  # User 1
        input_data={"documents": docs, "query": "financial plans"},
    )

    result = agent.execute(ctx)
    assert result.success is False
    assert "No accessible documents" in result.error


def test_document_research_agent_no_match_returns_low_confidence():
    agent = DocumentResearchAgent()
    ctx = AgentContext(
        input_data={"text": "Cooking recipe for chocolate chip cookies.", "query": "quantum computing algorithms"},
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["confidence"] in ("low", "medium", "high")


def test_document_research_docx(tmp_path):
    import docx
    docx_file = tmp_path / "enterprise_guidelines.docx"
    doc = docx.Document()
    doc.add_heading("Architecture Standards", level=1)
    doc.add_paragraph("All services must communicate using gRPC or TLS-encrypted REST endpoints.")
    doc.add_heading("Database Optimization", level=1)
    doc.add_paragraph("PostgreSQL connection pooling is configured with PgBouncer to cap idle sessions.")
    doc.save(str(docx_file))

    agent = DocumentResearchAgent()
    ctx = AgentContext(
        input_data={"file_path": str(docx_file), "query": "What is configured for database optimization?"}
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert len(result.output["sources"]) > 0
    src = result.output["sources"][0]
    assert src.get("section") == "Database Optimization" or "PgBouncer" in src["excerpt"]
    assert "PgBouncer" in result.output["answer"] or "PostgreSQL" in result.output["answer"]


def test_document_research_pptx(tmp_path):
    import pptx
    pptx_file = tmp_path / "quarterly_review.pptx"
    prs = pptx.Presentation()

    blank_slide_layout = prs.slide_layouts[6]
    # Slide 1
    slide1 = prs.slides.add_slide(blank_slide_layout)
    txBox = slide1.shapes.add_textbox(0, 0, 100, 100)
    tf = txBox.text_frame
    tf.text = "Q3 Financial Performance: Total revenue reached 4.2 million dollars, exceeding target by 15%."

    # Slide 2
    slide2 = prs.slides.add_slide(blank_slide_layout)
    txBox2 = slide2.shapes.add_textbox(0, 0, 100, 100)
    tf2 = txBox2.text_frame
    tf2.text = "Infrastructure Expansion: Cloud migration to multi-region Kubernetes cluster is 90% complete."

    prs.save(str(pptx_file))

    agent = DocumentResearchAgent()
    ctx = AgentContext(
        input_data={"file_path": str(pptx_file), "query": "What is the status of the cloud migration infrastructure?"}
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert len(result.output["sources"]) > 0
    src = result.output["sources"][0]
    assert src.get("slide") == 2
    assert "Kubernetes" in src["excerpt"]


def test_document_research_pptx_overview_query_smart_agriculture(tmp_path):
    """Verify that broad queries like 'what does this ppt contain' return a full structured summary of all slides."""
    import pptx
    pptx_file = tmp_path / "SEPM_G12_Smart_Agriculture.pptx"
    prs = pptx.Presentation()
    title_layout = prs.slide_layouts[0]
    bullet_layout = prs.slide_layouts[1]

    # Slide 1: Title
    s1 = prs.slides.add_slide(title_layout)
    s1.shapes.title.text = "Smart Agriculture System"
    s1.placeholders[1].text = "IoT-based Precision Farming and Crop Monitoring by Group 12"

    # Slide 2: Architecture
    s2 = prs.slides.add_slide(bullet_layout)
    s2.shapes.title.text = "System Architecture & IoT Layer"
    s2.placeholders[1].text = "Microcontroller gateway connects distributed wireless sensor nodes to cloud backend."

    # Slide 3: Soil Sensors
    s3 = prs.slides.add_slide(bullet_layout)
    s3.shapes.title.text = "Soil Moisture & NPK Sensing"
    s3.placeholders[1].text = "Real-time telemetry captures soil moisture, nitrogen, phosphorus, and potassium levels."

    # Slide 4: Automated Irrigation
    s4 = prs.slides.add_slide(bullet_layout)
    s4.shapes.title.text = "Automated Irrigation Subsystem"
    s4.placeholders[1].text = "Automatic solenoid valve relay activates drip irrigation when moisture drops below 30%."

    # Slide 5: Conclusion
    s5 = prs.slides.add_slide(bullet_layout)
    s5.shapes.title.text = "Conclusion & Future Scope"
    s5.placeholders[1].text = "Achieved 35% water conservation and planned future integration with autonomous drones."

    prs.save(str(pptx_file))

    agent = DocumentResearchAgent()
    ctx = AgentContext(
        input_data={
            "file_path": str(pptx_file),
            "query": "what does this ppt contain",
        }
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["confidence"] == "high"
    assert len(result.output["sources"]) == 5

    # Verify all slides are cited
    slide_numbers = [s.get("slide") for s in result.output["sources"]]
    assert slide_numbers == [1, 2, 3, 4, 5]

    # Verify slide titles and content appear in synthesis
    answer = result.output["answer"]
    assert "Smart Agriculture" in answer
    assert "Slide 1" in answer
    assert "Slide 4" in answer
    assert "SEPM_G12_Smart_Agriculture.pptx" in answer


def test_document_research_pptx_specific_targeted_query(tmp_path):
    """Verify specific questions retrieve the exact target slide."""
    import pptx
    pptx_file = tmp_path / "SEPM_G12_Smart_Agriculture.pptx"
    prs = pptx.Presentation()
    bullet_layout = prs.slide_layouts[1]

    s1 = prs.slides.add_slide(bullet_layout)
    s1.shapes.title.text = "Project Introduction"
    s1.placeholders[1].text = "Overview of smart farming benefits."

    s2 = prs.slides.add_slide(bullet_layout)
    s2.shapes.title.text = "Automated Drip Irrigation"
    s2.placeholders[1].text = "Solenoid water valves trigger automated drip irrigation when moisture is low."

    prs.save(str(pptx_file))

    agent = DocumentResearchAgent()
    ctx = AgentContext(
        input_data={
            "file_path": str(pptx_file),
            "query": "What does the slide say about automated drip irrigation?",
        }
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert result.output["confidence"] in ("high", "medium")
    top_src = result.output["sources"][0]
    assert top_src["slide"] == 2
    assert "irrigation" in top_src["excerpt"].lower() or "drip" in top_src["excerpt"].lower()


def test_document_research_file_id_upload_flow(app, db_session, tmp_path):
    """Test full file upload -> DB record -> file_id -> DocumentResearchAgent flow."""
    import pptx
    from io import BytesIO
    from werkzeug.datastructures import FileStorage

    prs = pptx.Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "AI Enterprise Automation"
    s.placeholders[1].text = "Multi-agent workflows automate complex business operations."

    buffer = BytesIO()
    prs.save(buffer)
    buffer.seek(0)

    with app.app_context():
        upload_dir = app.config.get("UPLOAD_FOLDER") or str(tmp_path / "uploads")
        fs = FileStorage(stream=buffer, filename="SEPM_G12_Smart_Agriculture.pptx", content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        rec, err = FileService.save_uploaded_file(fs, upload_dir=upload_dir, user_id=1)
        assert err is None
        assert rec is not None
        file_id = rec.public_id

        agent = DocumentResearchAgent()
        ctx = AgentContext(
            user_id=1,
            input_data={
                "file_id": file_id,
                "query": "what does this ppt contain",
            }
        )
        result = agent.execute(ctx)
        assert result.success is True
        assert result.output["confidence"] == "high"
        assert len(result.output["sources"]) >= 1
        assert "Slide 1" in result.output["answer"] or "Enterprise Automation" in result.output["answer"]


def test_document_research_pdf_and_scanned_detection(tmp_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    pdf_file = tmp_path / "compliance_manual.pdf"
    c = canvas.Canvas(str(pdf_file), pagesize=letter)
    c.drawString(100, 700, "Compliance Policy: SOC2 Type II certification must be renewed annually.")
    c.showPage()
    c.drawString(100, 700, "Incident Response: Severity 1 security incidents require an executive briefing within 1 hour.")
    c.save()

    agent = DocumentResearchAgent()
    ctx = AgentContext(
        input_data={"file_path": str(pdf_file), "query": "How quickly must executive briefings occur for severity 1 incidents?"}
    )
    result = agent.execute(ctx)
    assert result.success is True
    assert len(result.output["sources"]) > 0
    src = result.output["sources"][0]
    assert src.get("page") == 2
    assert "1 hour" in src["excerpt"]

    # Scanned / empty PDF test
    empty_pdf = tmp_path / "scanned_invoice.pdf"
    c2 = canvas.Canvas(str(empty_pdf), pagesize=letter)
    c2.showPage()  # Empty page (simulating image-only scanned pdf without OCR)
    c2.save()

    ctx_empty = AgentContext(
        input_data={"file_path": str(empty_pdf), "query": "Invoice total amount"}
    )
    result_empty = agent.execute(ctx_empty)
    assert result_empty.success is False
    assert "contains no extractable text" in result_empty.error.lower()
