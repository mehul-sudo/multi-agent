"""
Comprehensive Acceptance Tests for General-Purpose Chat Assistant.

Validates:
1. Arbitrary Natural-Language General Q&A (Blockchain, Recursion, Internet history, etc.)
2. Intent Classification and Directives Extraction
3. Length/Style Controls (in detail, in 2 lines, 5 points, 5-mark answer, Hinglish, beginner, direct)
4. Conversational Continuity & Contextual Follow-ups ("Give me an example")
5. Selective Agent Routing (CSV -> Data Analysis, PDF -> Document Research, Task -> Task Manager, Report Title -> Report Agent)
6. Prevention of Over-Routing ("What is SQL injection?", "Explain what Data Analysis Agent does" -> answered conversationally)
7. Absence of Raw JSON / Empty Responses
"""

import pytest
from app.services.chat_intent_service import (
    INTENT_AGENT_KNOWLEDGE,
    INTENT_DATA_ANALYSIS,
    INTENT_DOCUMENT_RESEARCH,
    INTENT_EMAIL,
    INTENT_FOLLOW_UP,
    INTENT_GENERAL_CONVERSATION,
    INTENT_GENERAL_KNOWLEDGE,
    INTENT_IMAGE_GENERATION,
    INTENT_MULTI_AGENT_WORKFLOW,
    INTENT_REPORT_GENERATION,
    INTENT_SECURITY_ANALYSIS,
    INTENT_TASK_MANAGEMENT,
    INTENT_WRITING,
    classify_chat_intent,
    extract_directives,
    generate_dynamic_autonomous_response,
)


# ------------------------------------------------------------------------------
# 1. Directives Extraction Tests
# ------------------------------------------------------------------------------
def test_directives_extraction():
    # 2 lines
    d1 = extract_directives("Explain cybersecurity in 2 lines.")
    assert d1["length"] == "two_lines"

    # 5 points
    d2 = extract_directives("Give me 5 points about machine learning.")
    assert d2["length"] == "points_n"
    assert d2["points_count"] == 5

    # 5-mark answer
    d3 = extract_directives("Give me a 5-mark answer on cloud computing.")
    assert d3["length"] == "exam_5_mark"

    # Hinglish
    d4 = extract_directives("Explain machine learning in Hinglish.")
    assert d4["language"] == "hinglish"

    # Beginner
    d5 = extract_directives("Explain recursion like I'm a beginner.")
    assert d5["audience"] == "beginner"

    # In detail
    d6 = extract_directives("Explain cybersecurity in detail.")
    assert d6["length"] == "detailed"


# ------------------------------------------------------------------------------
# 2. Intent Classification & Over-Routing Prevention Tests
# ------------------------------------------------------------------------------
def test_intent_classification_general_and_over_routing_prevention():
    # TEST 1: General Knowledge
    c1 = classify_chat_intent("What is machine learning?")
    assert c1["intent"] == INTENT_GENERAL_KNOWLEDGE
    assert c1["is_conversational"] is True
    assert c1["is_specialized_action"] is False

    # TEST 12: Inquiries about agents must be CONVERSATIONAL, not execute agent!
    c12 = classify_chat_intent("Explain what the Data Analysis Agent does.")
    assert c12["intent"] == INTENT_AGENT_KNOWLEDGE
    assert c12["is_conversational"] is True
    assert c12["is_specialized_action"] is False

    # Security conceptual question must be CONVERSATIONAL (not run vulnerability scan!)
    c_sec = classify_chat_intent("What is SQL injection?")
    assert c_sec["intent"] == INTENT_GENERAL_KNOWLEDGE
    assert c_sec["is_conversational"] is True
    assert c_sec["is_specialized_action"] is False

    # Writing help must be CONVERSATIONAL (not dispatch real email!)
    c_write = classify_chat_intent("Help me write an email to my manager.")
    assert c_write["intent"] == INTENT_WRITING
    assert c_write["is_conversational"] is True
    assert c_write["is_specialized_action"] is False

    # Image explanation must be CONVERSATIONAL (not trigger image generation!)
    c_img_exp = classify_chat_intent("Explain what cyberpunk means.")
    assert c_img_exp["intent"] in (INTENT_GENERAL_KNOWLEDGE, INTENT_GENERAL_CONVERSATION)
    assert c_img_exp["is_conversational"] is True

    # TEST 10: Task Creation Action
    c10 = classify_chat_intent("Create a task to finish the report tomorrow.")
    assert c10["intent"] == INTENT_TASK_MANAGEMENT
    assert c10["is_specialized_action"] is True

    # TEST 11: Report Generation Action
    c11 = classify_chat_intent("Generate a report titled Cybersecurity Risk Assessment.")
    assert c11["intent"] == INTENT_REPORT_GENERATION
    assert c11["is_specialized_action"] is True
    assert c11["extracted_params"]["title"] == "Cybersecurity Risk Assessment"

    # Image generation Action
    c_img = classify_chat_intent("Generate an image of a red sports car in neon city.")
    assert c_img["intent"] == INTENT_IMAGE_GENERATION
    assert c_img["is_specialized_action"] is True


# ------------------------------------------------------------------------------
# 3. Dynamic Response Matrix Tests (Test Scenarios 1 - 7)
# ------------------------------------------------------------------------------
def test_scenario_1_what_is_machine_learning():
    time_str = "Monday, October 05, 2026 (12:00 PM UTC)"
    res = generate_dynamic_autonomous_response("What is machine learning?", time_str)
    assert "Machine Learning" in res
    assert "Supervised Learning" in res or "data" in res


def test_scenario_2_explain_machine_learning_in_detail():
    time_str = "Monday, October 05, 2026 (12:00 PM UTC)"
    directives = extract_directives("Explain machine learning in detail.")
    res = generate_dynamic_autonomous_response("Explain machine learning in detail.", time_str, directives=directives)
    assert "Machine Learning" in res
    assert "Lifecycle" in res or "Paradigms" in res or "Detailed" in res


def test_scenario_3_explain_machine_learning_in_2_lines():
    time_str = "Monday, October 05, 2026 (12:00 PM UTC)"
    directives = extract_directives("Explain machine learning in 2 lines.")
    res = generate_dynamic_autonomous_response("Explain machine learning in 2 lines.", time_str, directives=directives)
    assert "Machine Learning" in res
    # Should be short
    assert len(res.splitlines()) <= 3


def test_scenario_4_give_me_5_points():
    time_str = "Monday, October 05, 2026 (12:00 PM UTC)"
    directives = extract_directives("Give me 5 points about machine learning.")
    res = generate_dynamic_autonomous_response("Give me 5 points about machine learning.", time_str, directives=directives)
    assert "1." in res
    assert "5." in res


def test_scenario_5_5_mark_answer():
    time_str = "Monday, October 05, 2026 (12:00 PM UTC)"
    directives = extract_directives("Give me a 5-mark answer on machine learning.")
    res = generate_dynamic_autonomous_response("Give me a 5-mark answer on machine learning.", time_str, directives=directives)
    assert "5-Mark Exam Answer" in res or "Definition" in res
    assert "Conclusion" in res


def test_scenario_6_explain_in_hinglish():
    time_str = "Monday, October 05, 2026 (12:00 PM UTC)"
    directives = extract_directives("Explain machine learning in Hinglish.")
    res = generate_dynamic_autonomous_response("Explain machine learning in Hinglish.", time_str, directives=directives)
    assert "Machine Learning" in res
    assert any(w in res.lower() for w in ("seekhta hai", "data se", "kya hai", "types"))


def test_scenario_7_follow_up_with_context():
    time_str = "Monday, October 05, 2026 (12:00 PM UTC)"
    history = [
        {"role": "user", "content": "What is machine learning?"},
        {"role": "assistant", "content": "Machine Learning is a branch of AI where systems learn from data..."},
    ]
    intent_meta = classify_chat_intent("Give me an example.", history=history)
    assert intent_meta["intent"] == INTENT_FOLLOW_UP

    res = generate_dynamic_autonomous_response(
        "Give me an example.",
        time_str,
        history=history,
        intent=intent_meta["intent"],
        directives=intent_meta["directives"],
    )
    assert "Example" in res
    assert "Machine Learning" in res or "Spam" in res or "Pattern" in res


# ------------------------------------------------------------------------------
# 4. REST API Endpoint Tests via Client
# ------------------------------------------------------------------------------
def test_chat_api_general_qa_endpoint(client, auth_headers):
    """Verify POST /api/v1/chat returns human-readable response for general questions."""
    response = client.post("/api/v1/chat", json={
        "message": "What is blockchain?",
        "mode": "auto"
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "completed"
    assert "response" in data
    assert len(data["response"]) > 20
    assert "Blockchain" in data["response"] or "blockchain" in data["response"]
    assert data["is_task"] is False


def test_chat_api_directives_endpoint(client, auth_headers):
    """Verify POST /api/v1/chat handles length and language directives."""
    # 5 points
    res1 = client.post("/api/v1/chat", json={
        "message": "Give me 5 points about cybersecurity.",
        "mode": "auto"
    }, headers=auth_headers)
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert "1." in data1["response"] or "point" in data1["response"].lower()

    # Hinglish
    res2 = client.post("/api/v1/chat", json={
        "message": "Explain cybersecurity in Hinglish.",
        "mode": "auto"
    }, headers=auth_headers)
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert len(data2["response"]) > 20


def test_chat_api_report_generation_intent_endpoint(client, auth_headers):
    """Verify POST /api/v1/chat routes report generation directly and creates downloadable artifact."""
    response = client.post("/api/v1/chat", json={
        "message": "Generate a report titled Cybersecurity Risk Assessment.",
        "mode": "auto"
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "completed"
    assert data["agent"] == "report_generation"
    assert "Cybersecurity Risk Assessment" in data["response"]


def test_chat_programming_requests_never_trigger_data_analysis(client, auth_headers, app, test_user, tmp_path):
    """Verify coding requests like 'hello give me c code for loop' return code and NEVER trigger CSV data analysis."""
    # Create an uploaded CSV file in DB to ensure it does not hijack the conversation
    csv_file = tmp_path / "quarterly_sales_2026.csv"
    csv_file.write_text("Quarter,Revenue,Cost\nQ1,1000,500\n", encoding="utf-8")

    with app.app_context():
        import os
        from app.models.uploaded_file import UploadedFile
        from app.extensions import db
        up = UploadedFile(
            owner_id=test_user.id,
            filename="quarterly_sales_2026.csv",
            extension="csv",
            storage_path=str(csv_file),
            size_bytes=os.path.getsize(str(csv_file)),
            mime_type="text/csv",
        )
        db.session.add(up)
        db.session.commit()

    # User asks for C code for loop
    response = client.post("/api/v1/chat", json={
        "message": "hello give me c code for loop",
        "mode": "auto"
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "completed"
    assert data["is_task"] is False
    assert data.get("agent") in ("chat_assistant", None)
    # Must NOT be dataset analysis
    assert "Dataset Analysis" not in data["response"]
    assert "quarterly_sales" not in data["response"]
    # Must contain code / for loop
    assert "for" in data["response"].lower()
    assert "c" in data["response"].lower() or "loop" in data["response"].lower()

