"""
Tests for Document Research Agent Accuracy and Response Adaptability.

Verifies:
1. "Explain this PDF" provides natural document explanation without rigid syllabus breakdown headers.
2. Page-targeted queries ("Explain page 2") focus strictly on targeted page.
3. Specific concept queries answer the requested concept with compact citations.
4. Source code files (.py, .ts, .sql) are properly processed and explained.
5. Scanned image-only PDFs return an explicit OCR limitation message.
6. Multi-turn chat correctly classifies "explain this pdf" as INTENT_DOCUMENT_RESEARCH.
"""

import os
import pytest
from app.agents.base import AgentContext
from app.agents.document_research_agent import DocumentResearchAgent
from app.services.file_service import FileService
from app.services.chat_intent_service import classify_chat_intent, INTENT_DOCUMENT_RESEARCH


def test_explain_pdf_generates_natural_synthesis_without_rigid_templates():
    agent = DocumentResearchAgent()
    text = (
        "Introduction to Operating Systems (CS301).\n"
        "Page 1: Operating systems manage computer hardware and provide common services for programs.\n"
        "Key components include the kernel, process management, memory management, and file systems.\n"
        "Page 2: Concurrency and synchronization prevent race conditions when multiple threads share resources.\n"
        "Semaphores and mutex locks are common primitives used to enforce mutual exclusion.\n"
        "Page 3: Virtual memory maps virtual addresses used by programs to physical addresses in RAM.\n"
        "Paging and page replacement algorithms (such as LRU) ensure efficient memory utilization."
    )
    ctx = AgentContext(
        input_data={"text": text, "document_name": "OperatingSystems.pdf", "query": "explain this pdf"}
    )
    result = agent.execute(ctx)
    assert result.success is True
    out = result.output
    assert "answer" in out
    answer = out["answer"]

    # Must NOT contain rigid unwanted headers
    assert "Executive Summary & Document Purpose" not in answer
    assert "Comprehensive Topic / Syllabus / Page Breakdown" not in answer

    # Must explain actual topics
    assert any(term in answer.lower() for term in ("kernel", "operating system", "concurrency", "memory", "virtual memory"))
    assert len(out.get("sources", [])) > 0


def test_targeted_page_query_focuses_on_target_page():
    agent = DocumentResearchAgent()
    docs = [
        {"id": "doc1", "name": "DeepLearningNotes.pdf", "page": 1, "text": "Page 1: Linear algebra fundamentals, vector spaces, and matrix multiplication."},
        {"id": "doc1", "name": "DeepLearningNotes.pdf", "page": 2, "text": "Page 2: Backpropagation calculus, computational graphs, and gradient descent optimization."},
        {"id": "doc1", "name": "DeepLearningNotes.pdf", "page": 3, "text": "Page 3: Convolutional Neural Networks, receptive fields, pooling layers, and filters."},
    ]
    ctx = AgentContext(
        input_data={"documents": docs, "document_name": "DeepLearningNotes.pdf", "query": "Explain page 2"}
    )
    result = agent.execute(ctx)
    assert result.success is True
    out = result.output
    assert out.get("query_target") == "specific_page"
    assert out.get("target_page") == 2

    # Sources should target page 2
    sources = out.get("sources", [])
    assert len(sources) > 0
    assert any(s.get("page") == 2 for s in sources)
    # The answer should discuss gradient descent / backpropagation from page 2
    assert any(term in out["answer"].lower() for term in ("backpropagation", "gradient", "descent", "page 2"))


def test_specific_concept_query_returns_definition():
    agent = DocumentResearchAgent()
    sample_text = (
        "Object Oriented Design Principles:\n"
        "Encapsulation binds data and functions together into a single component.\n"
        "Polymorphism allows objects of different classes to respond to the same method call differently.\n"
        "Abstraction hides internal implementation details and exposes only essential interfaces to users.\n"
        "Inheritance enables new classes to receive properties and behaviors from existing parent classes."
    )
    ctx = AgentContext(
        input_data={"text": sample_text, "document_name": "OOP_Guide.txt", "query": "What is polymorphism?"}
    )
    result = agent.execute(ctx)
    assert result.success is True
    out = result.output
    assert any(term in out["answer"].lower() for term in ("polymorphism", "different", "method", "class"))
    assert len(out.get("sources", [])) > 0


def test_code_file_explanation():
    agent = DocumentResearchAgent()
    python_code = (
        "# User Authentication Service\n"
        "import bcrypt\n"
        "from database import db_session, User\n\n"
        "def authenticate_user(email: str, password: str):\n"
        "    user = db_session.query(User).filter_by(email=email).first()\n"
        "    if not user:\n"
        "        return None\n"
        "    if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):\n"
        "        return user\n"
        "    return None\n"
    )
    ctx = AgentContext(
        input_data={"text": python_code, "document_name": "auth_service.py", "query": "Explain this code and how it works"}
    )
    result = agent.execute(ctx)
    assert result.success is True
    out = result.output
    assert any(term in out["answer"].lower() for term in ("authenticate", "bcrypt", "password", "user", "hash"))
    assert out.get("query_target") == "code_explanation"


def test_scanned_pdf_error_messaging(tmp_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    scanned_pdf = tmp_path / "scanned_doc.pdf"
    c = canvas.Canvas(str(scanned_pdf), pagesize=letter)
    c.showPage()  # Empty page simulating image-only PDF
    c.save()

    agent = DocumentResearchAgent()
    ctx = AgentContext(
        input_data={"file_path": str(scanned_pdf), "query": "Explain this document"}
    )
    result = agent.execute(ctx)
    assert result.success is False
    assert "ocr" in result.error.lower()
    assert "extractable text" in result.error.lower()


def test_chat_intent_routes_explain_pdf_to_document_research():
    context = {"file_id": "file_12345", "filename": "AnnualReport.pdf"}
    intent_meta = classify_chat_intent("explain this pdf", context=context)
    assert intent_meta["intent"] == INTENT_DOCUMENT_RESEARCH
    assert intent_meta["target_agent"] == "document_research"

    intent_page = classify_chat_intent("explain page 14", context=context)
    assert intent_page["intent"] == INTENT_DOCUMENT_RESEARCH
    assert intent_page["target_agent"] == "document_research"
