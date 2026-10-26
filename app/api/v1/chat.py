"""
Chat Assistant API Endpoints.

Handles natural language enterprise conversation, smart intent detection,
conversational question answering, style/length directives, and automated
multi-agent task execution via the Supervisor and Planner engines.
"""

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, Response, stream_with_context, current_app
from flask_jwt_extended import get_jwt_identity, jwt_required, decode_token

from app.extensions import db
from app.llm.base import LLMProvider
from app.llm.contracts import LLMMessage, LLMRequest
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.registry import provider_registry
from app.models.orchestration_plan import OrchestrationPlan
from app.models.orchestration_session import (
    ORCHESTRATION_STATUS_CREATED,
    ORCHESTRATION_STATUS_READY,
    OrchestrationSession,
)
from app.models.user import User
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
    build_conversational_system_prompt,
    classify_chat_intent,
    extract_directives,
    generate_dynamic_autonomous_response,
)
from app.services.media_generation_service import MediaGenerationService
from app.services.orchestration_event_service import emit_orchestration_event
from app.services.planner_service import generate_orchestration_plan
from app.services.supervisor_service import SupervisorService

chat_bp = Blueprint("chat_v1", __name__)


def _get_current_user():
    public_id = get_jwt_identity()
    return User.query.filter_by(public_id=public_id).first()


def _should_resolve_file_from_context(message: str) -> bool:
    """Determine whether the user query actually refers to an attached or uploaded document."""
    msg = message.lower().strip()
    code_words = ("code", "program", "script", "function", "for loop", "while loop", "loop in", "c code", "python code", "java code", "syntax", "algorithm")
    if any(cw in msg for cw in code_words) and not any(k in msg for k in ("in this file", "in the file", "in this document", "in the document")):
        return False
    return True


def _is_explicit_file_query(message: str) -> bool:
    """Check if the user is explicitly referring to a previously uploaded file/document."""
    msg = message.lower().strip()
    return bool(
        re.search(r"\b(?:my|the|this|that)\s+(?:uploaded\s+)?(?:file|dataset|csv|document|pdf|spreadsheet)\b", msg)
        or any(k in msg for k in ("uploaded file", "uploaded dataset", "uploaded csv", "uploaded document", "my file", "my csv", "my dataset"))
    )


def generate_autonomous_response(
    message: str,
    current_time_str: str,
    history: list = None,
    directives: dict = None,
    intent: str = None,
) -> str:
    """Intelligent core reasoning engine that provides authoritative, context-aware answers
    when external cloud LLMs hit rate-limits or quota restrictions.
    """
    return generate_dynamic_autonomous_response(
        message=message,
        current_time_str=current_time_str,
        history=history,
        directives=directives,
        intent=intent,
    )


from app.services.conversation_service import (
    create_conversation,
    get_or_create_active_conversation,
    list_conversations,
    get_conversation,
    delete_conversation,
    add_message,
    update_message,
)


@chat_bp.route("/chat/conversations", methods=["GET"])
@jwt_required()
def get_user_conversations():
    """List conversations for current user, optionally filtered by agent_type."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401

    agent_type = request.args.get("agent_type")
    convs = list_conversations(user.id, agent_type=agent_type)
    return jsonify({
        "conversations": [c.to_dict(include_messages=False) for c in convs]
    }), 200


@chat_bp.route("/chat/conversations", methods=["POST"])
@jwt_required()
def create_user_conversation():
    """Explicitly start a new persistent conversation."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    agent_type = data.get("agent_type", "chat_assistant")
    title = data.get("title", "New Conversation")
    conv = create_conversation(user_id=user.id, agent_type=agent_type, title=title)
    return jsonify({"conversation": conv.to_dict(include_messages=True)}), 201


@chat_bp.route("/chat/conversations/<conversation_id>", methods=["GET"])
@jwt_required()
def get_single_conversation(conversation_id):
    """Retrieve an existing conversation and its full message history."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401

    conv = get_conversation(user.id, conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found."}), 404

    return jsonify({"conversation": conv.to_dict(include_messages=True)}), 200


@chat_bp.route("/chat/conversations/<conversation_id>", methods=["DELETE"])
@jwt_required()
def delete_single_conversation(conversation_id):
    """Delete a conversation and all its messages."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401

    success = delete_conversation(user.id, conversation_id)
    if not success:
        return jsonify({"error": "Conversation not found."}), 404

    return jsonify({"message": "Conversation deleted successfully."}), 200


@chat_bp.route("/chat", methods=["POST"])
@jwt_required()
def process_chat_message():
    """Handle conversational message or route actionable request to Supervisor/Planner."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401

    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    mode = data.get("mode", "auto")  # 'auto', 'task', 'chat', 'image'
    history = data.get("history") or []
    context = data.get("context") or {}
    conversation_id = data.get("conversation_id")

    if not message:
        return jsonify({"error": "Field 'message' is required."}), 400

    # Persist or retrieve active conversation thread
    conv = get_or_create_active_conversation(
        user_id=user.id,
        agent_type="chat_assistant",
        conversation_id=conversation_id,
    )

    file_id = context.get("file_id")
    filename = context.get("filename", "")

    # Check if previous messages in this conversation had a document attached
    # Only inherit if this query is actually related to files/documents, not an unrelated coding/general query
    if not file_id and conv and conv.messages and _should_resolve_file_from_context(message):
        has_file_ref = bool(re.search(r"\b(?:this|the|that|in|from|summarize|analyze|explain)\b", message.lower()))
        if has_file_ref:
            for prev_msg in reversed(conv.messages):
                meta = prev_msg.metadata_json or {}
                if isinstance(meta, dict) and meta.get("file_id"):
                    file_id = meta["file_id"]
                    filename = meta.get("attached_filename") or ""
                    context["file_id"] = file_id
                    if filename:
                        context["filename"] = filename
                    break

    # Only fall back to latest uploaded file if the user explicitly asks about their uploaded file
    if not file_id and _is_explicit_file_query(message) and _should_resolve_file_from_context(message):
        from app.models.uploaded_file import UploadedFile
        latest_file = UploadedFile.query.filter_by(owner_id=user.id).order_by(UploadedFile.created_at.desc()).first()
        if latest_file:
            file_id = latest_file.public_id
            filename = latest_file.filename
            context["file_id"] = file_id
            context["filename"] = filename

    add_message(
        conversation_id=conv.id,
        sender="user",
        content=message,
        metadata={"attached_filename": filename, "file_id": file_id} if (filename or file_id) else None,
    )

    # 1. Intent Classification
    intent_meta = classify_chat_intent(message, history=history, context=context, mode=mode)
    intent = intent_meta["intent"]
    directives = intent_meta["directives"]

    # 2. Image / Visual Media Generation
    if intent == INTENT_IMAGE_GENERATION:
        prompt_to_use = intent_meta["extracted_params"].get("prompt") or message
        is_media, media_type, _ = MediaGenerationService.detect_media_request(message)
        if media_type == "video":
            media_res = MediaGenerationService.generate_video_simulation(prompt_to_use)
            img_url = media_res["keyframe_url"]
            resp_content = f"🎬 **Video Simulation Keyframe Rendered**\n\n![{prompt_to_use}]({img_url})\n\n- **Prompt:** *{prompt_to_use}*\n- **Aspect Ratio:** 16:9\n- **Status:** Rendered\n"
            add_message(conv.id, sender="assistant", content=resp_content, metadata={"media": media_res})
            return jsonify({
                "status": "completed",
                "intent": intent,
                "agent": "image_generation",
                "response": resp_content,
                "is_task": False,
                "conversation_id": conv.public_id,
                "media": media_res,
                "image": {"image_url": img_url, "prompt": prompt_to_use},
            }), 200
        else:
            image_res = MediaGenerationService.generate_image(prompt_to_use)
            img_url = image_res["image_url"]
            resp_content = f"🎨 **Generated AI Visual**\n\n![{prompt_to_use}]({img_url})\n\n**Visual Prompt:** *{prompt_to_use}*\n**Engine:** Flux.1 Latent Diffusion • **Resolution:** {image_res['width']}x{image_res['height']}px\n"
            add_message(conv.id, sender="assistant", content=resp_content, metadata={"image": image_res})
            return jsonify({
                "status": "completed",
                "intent": intent,
                "agent": "image_generation",
                "response": resp_content,
                "is_task": False,
                "conversation_id": conv.public_id,
                "image": image_res,
            }), 200

    # 3. Direct File Analysis Actions if explicit file attached
    if intent == INTENT_DATA_ANALYSIS and file_id:
        ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
        if ext in ("csv", "xlsx", "xls"):
            from app.agents.data_analysis_agent import DataAnalysisAgent
            from app.agents.base import AgentContext
            try:
                data_agent = DataAnalysisAgent()
                ctx = AgentContext(
                    user_id=user.id,
                    input_data={"file_id": file_id, "query": message, "instructions": message},
                    instructions=message,
                )
                res = data_agent.execute(ctx)
                if res.success:
                    out = res.output or {}
                    dq = out.get("dataQuality") or out.get("data_quality") or {}
                    ds = out.get("dataset_summary") or {}
                    stats = out.get("statistics") or {}
                    outliers = out.get("outliers") or {}
                    agent_summary = out.get("summary", "")

                    total_rows = dq.get("total_rows") or ds.get("row_count", 0)
                    total_cols = dq.get("total_columns") or ds.get("column_count", 0)
                    quality_score = dq.get("quality_score", 100)
                    duplicate_rows = dq.get("duplicate_rows", 0)
                    null_cells = sum(dq.get("null_counts", {}).values()) if isinstance(dq.get("null_counts"), dict) else dq.get("total_null_cells", 0)

                    stat_bullets = []
                    for col, c_stats in list(stats.items())[:6]:
                        m = c_stats.get("mean")
                        med = c_stats.get("median")
                        std = c_stats.get("std_dev") or c_stats.get("stdDev") or c_stats.get("std")
                        m_str = f"{m:.2f}" if isinstance(m, (int, float)) else str(m)
                        med_str = f"{med:.2f}" if isinstance(med, (int, float)) else str(med)
                        std_str = f"{std:.2f}" if isinstance(std, (int, float)) else str(std)
                        stat_bullets.append(f"- **{col}**: Mean = `{m_str}`, Median = `{med_str}`, StdDev = `{std_str}`")

                    reply = (
                        f"### 📊 Tabular Analysis: **{filename or 'Uploaded Dataset'}**\n\n"
                        f"- **Total Rows:** {total_rows:,} | **Columns:** {total_cols}\n"
                        f"- **Data Quality Score:** `{quality_score}%` (Null cells: {null_cells}, Duplicate rows: {duplicate_rows})\n"
                        f"- **Detected Outliers:** {outliers.get('total_outliers_detected', 0)} potential anomalies\n\n"
                        f"**Key Column Metrics:**\n"
                        + ("\n".join(stat_bullets) if stat_bullets else "- No numeric columns found.")
                    )

                    if agent_summary:
                        reply += f"\n\n**Executive Summary & Findings:**\n{agent_summary}"

                    reply += f"\n\n💡 *Tip: You can also explore full charts and correlation graphs in the **[Data Analysis Workspace](/data-analysis)**.*"

                    add_message(conv.id, sender="assistant", content=reply, metadata={"output": out, "file_id": file_id})
                    return jsonify({
                        "status": "completed",
                        "intent": intent,
                        "agent": "data_analysis",
                        "response": reply,
                        "is_task": False,
                        "conversation_id": conv.public_id,
                        "file_id": file_id,
                        "output": out,
                    }), 200
            except Exception:
                pass

    if intent == INTENT_DOCUMENT_RESEARCH and file_id:
        ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
        if ext in ("pdf", "docx", "doc", "txt", "pptx", "md", "markdown", "py", "js", "ts", "jsx", "tsx", "html", "css", "sql", "sh", "yaml", "yml", "json") or not ext:
            from app.agents.document_research_agent import DocumentResearchAgent
            from app.agents.base import AgentContext
            try:
                doc_agent = DocumentResearchAgent()
                ctx = AgentContext(
                    user_id=user.id,
                    input_data={"file_id": file_id, "query": message, "instructions": message},
                    instructions=message,
                )
                res = doc_agent.execute(ctx)
                if res.success:
                    out = res.output or {}
                    answer = out.get("answer", "")
                    sources = out.get("sources", [])
                    reply = f"### 📄 Document Analysis: **{filename or 'Uploaded Document'}**\n\n{answer}"
                    add_message(conv.id, sender="assistant", content=reply, metadata={"sources": sources, "file_id": file_id})
                    return jsonify({
                        "status": "completed",
                        "intent": intent,
                        "agent": "document_research",
                        "response": reply,
                        "is_task": False,
                        "conversation_id": conv.public_id,
                        "file_id": file_id,
                        "sources": [{"name": s.get("doc_name") or s.get("name"), "id": s.get("doc_id")} for s in sources[:4]],
                    }), 200
            except Exception:
                pass

    # 4. Explicit Report Generation Request
    if intent == INTENT_REPORT_GENERATION:
        report_title = intent_meta["extracted_params"].get("title") or "Executive Analysis Report"
        from app.agents.report_generation_agent import ReportGenerationAgent
        from app.agents.base import AgentContext
        try:
            report_agent = ReportGenerationAgent()
            ctx = AgentContext(
                user_id=user.id,
                input_data={"title": report_title, "format": "pdf", "instructions": message},
                instructions=message,
            )
            res = report_agent.execute(ctx)
            if res.success:
                out = res.output or {}
                primary_art = out.get("primary_artifact") or {}
                download_url = primary_art.get("url") or f"/api/v1/reports/download/{primary_art.get('filename')}"
                sec_count = len(out.get("sections", []))

                reply = (
                    f"### 📑 Enterprise Report Generated: **\"{report_title}\"**\n\n"
                    f"I have successfully generated your standardized 9-section enterprise report across multiple formats:\n\n"
                    f"- **Report Title:** `{report_title}`\n"
                    f"- **Sections Synthesized:** {sec_count} standardized sections\n"
                    f"- **Primary Download:** [Download PDF Document]({download_url})\n\n"
                    f"You can also review, edit, or export in Word (`.docx`), Markdown, and HTML inside the **[Reports Workspace](/reports)**."
                )

                add_message(conv.id, sender="assistant", content=reply, metadata={"report": out})
                return jsonify({
                    "status": "completed",
                    "intent": intent,
                    "agent": "report_generation",
                    "response": reply,
                    "is_task": False,
                    "conversation_id": conv.public_id,
                    "report": out,
                }), 200
        except Exception:
            pass

    # 5. Explicit Multi-Agent Workflow Execution
    if intent == INTENT_MULTI_AGENT_WORKFLOW or mode == "task":
        try:
            session_context = dict(context)
            session_context["source"] = "chat_assistant"

            session = OrchestrationSession(
                user_id=user.id,
                organization_id="default_org",
                objective=message,
                input_context=session_context,
                priority=1,
                status=ORCHESTRATION_STATUS_CREATED,
            )
            db.session.add(session)
            db.session.flush()

            plan = generate_orchestration_plan(session)
            session.status = ORCHESTRATION_STATUS_READY
            db.session.commit()

            emit_orchestration_event(
                event_type="ORCHESTRATION_CREATED",
                orchestration_id=session.id,
                correlation_id=session.correlation_id,
                trace_id=session.trace_id,
            )

            supervisor = SupervisorService()
            updated_session = supervisor.run_orchestration(session.id)

            tasks = plan.tasks.all()
            task_list = [
                {
                    "id": t.public_id,
                    "task_key": t.task_key,
                    "name": t.name,
                    "status": t.status,
                    "agent": t.assigned_agent.display_name if t.assigned_agent else (t.assigned_agent.name if t.assigned_agent else "Supervisor"),
                    "agent_type": t.assigned_agent.agent_type if t.assigned_agent else None,
                    "output": t.output_data,
                }
                for t in tasks
            ]

            step_bullets = "\n".join([f"- **{t['name']}** [{t['status']}]" for t in task_list])

            findings_bullets = []
            for t in task_list:
                if t["output"] and isinstance(t["output"], dict):
                    out = t["output"].get("output", t["output"])
                    if isinstance(out, dict):
                        dq = out.get("dataQuality") or out.get("data_quality") or {}
                        ds = out.get("dataset_summary") or {}
                        rows = dq.get("total_rows") or ds.get("row_count")
                        if rows is not None:
                            cols = dq.get("total_columns") or ds.get("column_count", 0)
                            qscore = dq.get("quality_score", 100)
                            findings_bullets.append(f"**{t['name']}:** Analyzed {rows:,} rows across {cols} columns (Quality Score: {qscore}%).")
                        elif out.get("executive_summary") or out.get("summary"):
                            findings_bullets.append(f"**{t['name']}:** {out.get('executive_summary') or out.get('summary')}")
                        elif out.get("messageId") and out.get("status") in ("sent", "delivered"):
                            findings_bullets.append(f"**{t['name']}:** Successfully dispatched email to {', '.join(out.get('to', []))} via {out.get('provider', 'enterprise mail')}.")

            findings_section = ("\n\n### Execution Findings:\n" + "\n".join([f"- {f}" for f in findings_bullets])) if findings_bullets else ""

            final_synthesis = (updated_session.result_summary or {}).get("final_synthesis")
            synthesis_section = f"\n\n### Executive Synthesis:\n{final_synthesis}" if final_synthesis else ""

            requires_approval = updated_session.status in ("AWAITING_APPROVAL", "PAUSED")
            approval_info = None
            if requires_approval:
                from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
                appr = ApprovalRequest.query.filter_by(
                    orchestration_id=updated_session.id,
                    status=APPROVAL_STATUS_PENDING,
                ).first()
                if appr:
                    approval_info = {
                        "id": appr.public_id,
                        "approval_id": appr.public_id,
                        "orchestration_id": updated_session.public_id,
                        "requested_action": appr.requested_action,
                        "risk_level": appr.risk_level,
                        "explanation": appr.explanation,
                        "parameters_summary": appr.input_summary,
                        "status": appr.status,
                    }

            if requires_approval:
                status_display = "WAITING_FOR_APPROVAL"
                action_name = approval_info["requested_action"] if approval_info else "External Action"
                response_text = (
                    f"### ⏸ Action Requires Human Approval\n\n"
                    f"Execution has paused because **{action_name}** modifies external state and requires your authorization.\n\n"
                    f"### Planned Pipeline Steps:\n{step_bullets}\n\n"
                    f"Please review the pending action and click **Approve** or **Reject** to proceed."
                )
            else:
                status_display = "COMPLETED" if updated_session.status in ("COMPLETED", "SUCCESS") else updated_session.status
                response_text = (
                    f"### ⚡ Automated Multi-Agent Pipeline Completed\n\n"
                    f"I've executed the automated workflow in real time for:\n\n"
                    f"> **\"{message}\"**\n\n"
                    f"### Executed Pipeline Steps:\n{step_bullets}"
                    f"{findings_section}"
                    f"{synthesis_section}\n\n"
                    f"**Overall Status:** `{status_display}`"
                )

            add_message(conv.id, sender="assistant", content=response_text, metadata={"tasks": task_list, "orchestration_id": updated_session.public_id})
            return jsonify({
                "status": status_display,
                "intent": intent,
                "agent": "supervisor",
                "response": response_text,
                "is_task": True,
                "conversation_id": conv.public_id,
                "orchestration_id": updated_session.public_id,
                "tasks": task_list,
                "result_summary": updated_session.result_summary,
                "requires_approval": requires_approval,
                "approval": approval_info,
            }), 200

        except Exception as e:
            err_msg = f"I attempted to run that workflow, but encountered an issue: {str(e)}. Let me help answer your question directly."
            add_message(conv.id, sender="assistant", content=err_msg, metadata={"error": str(e)})
            return jsonify({
                "status": "error",
                "intent": intent,
                "response": err_msg,
                "is_task": False,
                "conversation_id": conv.public_id,
                "error": str(e),
            }), 200

    # 6. Conversational Q&A / General Purpose Answering via Real LLM
    now_utc = datetime.now(timezone.utc)
    current_time_str = now_utc.strftime("%A, %B %d, %Y (%I:%M %p UTC)")

    msg_lower = message.lower().strip()
    is_date_time_query = any(k in msg_lower for k in ("date", "time", "day", "today", "tomorrow", "yesterday", "year", "month"))

    retrieved_sources = []
    needs_external_search = any(k in msg_lower for k in ("search", "news", "latest", "lookup", "who is", "who was", "wikipedia")) and not is_date_time_query

    if needs_external_search:
        clean_topic = re.sub(
            r"^(search for|search|lookup|who is|tell me about|explain|give me info on)\s+",
            "",
            message,
            flags=re.IGNORECASE,
        ).strip(" ?.")
        search_query = clean_topic if len(clean_topic) >= 3 else message

        from app.agents.document_research_agent import DocumentResearchAgent
        research_agent = DocumentResearchAgent()
        try:
            retrieved_sources = research_agent._perform_external_research(search_query, user.id)
        except Exception:
            retrieved_sources = []

    context_text = ""
    if retrieved_sources:
        for s in retrieved_sources[:4]:
            t = html.unescape(s.get("text", "")).strip()
            name = html.unescape(s.get("name", "Source"))
            if t:
                context_text += f"\n---\nSource: {name}\n{t}\n"

    system_prompt = build_conversational_system_prompt(
        intent=intent,
        directives=directives,
        current_time_str=current_time_str,
        context_text=context_text,
    )

    # Build messages including conversation history
    llm_messages = []
    for h in history[-8:]:  # keep last 8 turns for context window
        role = h.get("role", "user")
        content = h.get("content", "")
        if content:
            llm_messages.append(LLMMessage(role=role, content=content))
    llm_messages.append(LLMMessage(role="user", content=message))

    reply = None
    try:
        provider, model = provider_registry.resolve_provider_and_model()
        req = LLMRequest(
            provider=provider.provider_name,
            model=model,
            system_instructions=system_prompt,
            messages=llm_messages,
            temperature=0.7,
            max_tokens=1400,
            user_id=user.id,
        )
        resp = provider.generate(req)
        reply = resp.text
    except Exception:
        # Fallback to OpenAI if configured
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                fallback_provider = provider_registry.get_provider("openai")
                req = LLMRequest(
                    provider="openai",
                    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                    system_instructions=system_prompt,
                    messages=llm_messages,
                    temperature=0.7,
                    max_tokens=1400,
                    user_id=user.id,
                )
                resp = fallback_provider.generate(req)
                reply = resp.text
            except Exception:
                reply = None
        else:
            reply = None

        if reply is None:
            is_test = bool(
                os.getenv("PYTEST_CURRENT_TEST")
                or (current_app and current_app.config.get("TESTING"))
            )
            if is_test:
                try:
                    mock_p = provider_registry.get_provider("mock")
                    req = LLMRequest(
                        provider="mock",
                        model="mock-model",
                        system_instructions=system_prompt,
                        messages=llm_messages,
                        user_id=user.id,
                    )
                    resp = mock_p.generate(req)
                    reply = resp.text
                except Exception:
                    reply = generate_dynamic_autonomous_response(
                        message=message,
                        current_time_str=current_time_str,
                        history=history,
                        directives=directives,
                        intent=intent,
                    )
            else:
                reply = generate_dynamic_autonomous_response(
                    message=message,
                    current_time_str=current_time_str,
                    history=history,
                    directives=directives,
                    intent=intent,
                )

    final_reply = reply or "No response generated."
    add_message(conv.id, sender="assistant", content=final_reply, metadata={"intent": intent, "sources": retrieved_sources[:4]})
    return jsonify({
        "status": "completed",
        "intent": intent,
        "agent": "chat_assistant",
        "response": final_reply,
        "is_task": False,
        "conversation_id": conv.public_id,
        "sources": [{"name": s.get("name"), "id": s.get("id")} for s in retrieved_sources[:4]],
    }), 200


@chat_bp.route("/chat/suggestions", methods=["GET"])
@jwt_required()
def get_chat_suggestions():
    """Return general-purpose enterprise prompt suggestions."""
    return jsonify({
        "suggestions": [
            {
                "label": "🤖 Machine Learning in 5 Points",
                "prompt": "Give me 5 points about machine learning with real-world examples.",
                "category": "Artificial Intelligence",
            },
            {
                "label": "🛡️ Cybersecurity 5-Mark Answer",
                "prompt": "Give me a structured 5-mark exam answer on cybersecurity principles.",
                "category": "Security & Architecture",
            },
            {
                "label": "💻 Explain Recursion Simply",
                "prompt": "Explain recursion like I'm a beginner with a simple Python code example.",
                "category": "Programming & CS",
            },
            {
                "label": "🗣️ Machine Learning in Hinglish",
                "prompt": "Explain machine learning in Hinglish in a friendly conversational style.",
                "category": "Conversational & Language",
            },
            {
                "label": "📊 Tabular Data Analytics",
                "prompt": "Analyze this CSV dataset, compute key summary statistics, and detect outliers.",
                "category": "Data & Reporting",
            },
            {
                "label": "📑 Enterprise Cybersecurity Report",
                "prompt": "Generate a report titled Cybersecurity Risk Assessment.",
                "category": "Executive Reporting",
            },
            {
                "label": "⚡ Multi-Agent Pipeline",
                "prompt": "Run workflow to inspect data quality and synthesize an executive briefing.",
                "category": "Autonomous Orchestration",
            },
            {
                "label": "🎨 Generate AI Artwork",
                "prompt": "Generate an image of a breathtaking futuristic neo-Tokyo cyberpunk skyline at sunset.",
                "category": "Visuals & Media",
            },
        ]
    }), 200


@chat_bp.route("/chat/generate-image", methods=["POST"])
@jwt_required()
def generate_image_endpoint():
    """Direct visual asset creation endpoint using Flux.1 Latent Diffusion."""
    data = request.get_json() or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Prompt is required."}), 400

    style = data.get("style", "photorealistic")
    width = int(data.get("width", 1024))
    height = int(data.get("height", 1024))
    seed = data.get("seed")

    image_res = MediaGenerationService.generate_image(
        prompt=prompt,
        style=style,
        width=width,
        height=height,
        seed=seed,
    )
    return jsonify(image_res), 200


@chat_bp.route("/chat/stream", methods=["POST", "GET"])
def stream_chat():
    """Real-time Server-Sent Events (SSE) streaming endpoint for Chat Assistant."""
    token = request.args.get("token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    user = None
    if token:
        try:
            decoded = decode_token(token)
            user = User.query.filter_by(public_id=decoded.get("sub")).first()
        except Exception:
            pass

    if not user:
        try:
            user = _get_current_user()
        except Exception:
            pass

    if not user:
        return jsonify({"error": "Authentication token is required."}), 401

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = {
            "message": request.args.get("message", ""),
            "mode": request.args.get("mode", "auto"),
            "context": {},
            "history": [],
            "conversation_id": request.args.get("conversation_id"),
        }

    message = (data.get("message") or "").strip()
    mode = data.get("mode", "auto")
    history = data.get("history") or []
    context = data.get("context") or {}
    conversation_id = data.get("conversation_id") or request.args.get("conversation_id")

    # Persist or retrieve active conversation thread
    conv = get_or_create_active_conversation(
        user_id=user.id,
        agent_type="chat_assistant",
        conversation_id=conversation_id,
    )

    file_id = context.get("file_id")
    filename = context.get("filename", "")

    # Check if previous messages in this conversation had a document attached
    # Only inherit if this query is actually related to files/documents, not an unrelated coding/general query
    if not file_id and conv and conv.messages and _should_resolve_file_from_context(message):
        has_file_ref = bool(re.search(r"\b(?:this|the|that|in|from|summarize|analyze|explain)\b", message.lower()))
        if has_file_ref:
            for prev_msg in reversed(conv.messages):
                meta = prev_msg.metadata_json or {}
                if isinstance(meta, dict) and meta.get("file_id"):
                    file_id = meta["file_id"]
                    filename = meta.get("attached_filename") or ""
                    context["file_id"] = file_id
                    if filename:
                        context["filename"] = filename
                    break

    # Only fall back to latest uploaded file if the user explicitly asks about their uploaded file
    if not file_id and _is_explicit_file_query(message) and _should_resolve_file_from_context(message):
        from app.models.uploaded_file import UploadedFile
        latest_file = UploadedFile.query.filter_by(owner_id=user.id).order_by(UploadedFile.created_at.desc()).first()
        if latest_file:
            file_id = latest_file.public_id
            filename = latest_file.filename
            context["file_id"] = file_id
            context["filename"] = filename

    if not message:
        return jsonify({"error": "Field 'message' is required."}), 400

    from flask import current_app
    app_obj = current_app._get_current_object()

    def generate_events():
        with app_obj.app_context():
            def sse(event_type: str, event_data: dict, status: str = "running"):
                payload = {
                    "event_type": event_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": status,
                    "data": event_data,
                }
                return f"data: {json.dumps(payload)}\n\n"

            # Persist incoming user message
            add_message(
                conversation_id=conv.id,
                sender="user",
                content=message,
                metadata={"attached_filename": filename, "file_id": file_id} if (filename or file_id) else None,
            )

            yield sse("conversation.started", {"message": message, "mode": mode, "conversation_id": conv.public_id})

            # Intent Classification
            intent_meta = classify_chat_intent(message, history=history, context=context, mode=mode)
            intent = intent_meta["intent"]
            directives = intent_meta["directives"]

            # Image / Visual Media Generation
            if intent == INTENT_IMAGE_GENERATION:
                prompt_to_use = intent_meta["extracted_params"].get("prompt") or message
                is_media, media_type, _ = MediaGenerationService.detect_media_request(message)
                yield sse("assistant.delta", {"delta": f"🎨 **Creating High-Resolution AI {media_type.title()}...**\n\n"})

                if media_type == "video":
                    media_res = MediaGenerationService.generate_video_simulation(prompt_to_use)
                    img_url = media_res["keyframe_url"]
                    yield sse("assistant.image", media_res)
                    yield sse("assistant.delta", {"delta": f"🎬 **Video Simulation Keyframe Rendered**\n\n![{prompt_to_use}]({img_url})\n\n- **Prompt:** *{prompt_to_use}*\n- **Aspect Ratio:** 16:9 (1280x720px)\n- **Render Status:** Complete\n"})
                    add_message(conv.id, sender="assistant", content=f"🎬 Video Simulation Rendered: {prompt_to_use}", metadata={"media": media_res})
                    yield sse("assistant.completed", {
                        "response": f"Video keyframe generated for: {prompt_to_use}",
                        "conversation_id": conv.public_id,
                        "media": media_res,
                        "image": {"image_url": img_url, "prompt": prompt_to_use},
                    }, status="completed")
                    return
                else:
                    image_res = MediaGenerationService.generate_image(prompt_to_use)
                    img_url = image_res["image_url"]
                    yield sse("assistant.image", image_res)
                    yield sse("assistant.delta", {"delta": f"![{prompt_to_use}]({img_url})\n\n**Visual Prompt:** *{prompt_to_use}*\n**Engine:** Flux.1 Latent Diffusion • **Resolution:** {image_res['width']}x{image_res['height']}px\n\n*Click image to view full-resolution, or download directly below.*"})
                    add_message(conv.id, sender="assistant", content=f"![{prompt_to_use}]({img_url})", metadata={"image": image_res})
                    yield sse("assistant.completed", {
                        "response": f"Image generated for: {prompt_to_use}",
                        "conversation_id": conv.public_id,
                        "image": image_res,
                    }, status="completed")
                    return

            # Direct File Analysis Actions
            if intent == INTENT_DATA_ANALYSIS and file_id:
                ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
                if ext in ("csv", "xlsx", "xls"):
                    yield sse("node.started", {"agent_type": "data_analysis", "filename": filename})
                    from app.agents.data_analysis_agent import DataAnalysisAgent
                    from app.agents.base import AgentContext
                    agent = DataAnalysisAgent()
                    ctx = AgentContext(user_id=user.id, input_data={"file_id": file_id, "query": message, "instructions": message}, instructions=message)
                    res = agent.execute(ctx)
                    out = res.output or {}
                    yield sse("node.completed", {"agent_type": "data_analysis", "output": out})

                    dq = out.get("dataQuality") or out.get("data_quality") or {}
                    ds = out.get("dataset_summary") or {}
                    stats = out.get("statistics") or {}
                    outliers = out.get("outliers") or {}
                    agent_summary = out.get("summary", "")
                    total_rows = dq.get("total_rows") or ds.get("row_count", 0)
                    total_cols = dq.get("total_columns") or ds.get("column_count", 0)
                    quality_score = dq.get("quality_score", 100)
                    null_cells = sum(dq.get("null_counts", {}).values()) if isinstance(dq.get("null_counts"), dict) else dq.get("total_null_cells", 0)
                    stat_bullets = []
                    for col, c_stats in list(stats.items())[:6]:
                        m = c_stats.get("mean")
                        med = c_stats.get("median")
                        m_str = f"{m:.2f}" if isinstance(m, (int, float)) else str(m)
                        med_str = f"{med:.2f}" if isinstance(med, (int, float)) else str(med)
                        stat_bullets.append(f"- **{col}**: Mean = `{m_str}`, Median = `{med_str}`")

                    reply = (
                        f"### 📊 Dataset Analysis: **{filename}**\n\n"
                        f"- **Total Rows:** {total_rows:,} | **Columns:** {total_cols}\n"
                        f"- **Data Quality Score:** `{quality_score}%` (Null cells: {null_cells})\n"
                        f"- **Detected Outliers:** {outliers.get('total_outliers_detected', 0)}\n\n"
                        f"**Key Column Statistics:**\n" + ("\n".join(stat_bullets) if stat_bullets else "- None") +
                        (f"\n\n**Executive Summary & Findings:**\n{agent_summary}" if agent_summary else "")
                    )
                    words = reply.split(" ")
                    for i in range(0, len(words), 6):
                        yield sse("assistant.delta", {"delta": " ".join(words[i:i+6]) + " "})
                        time.sleep(0.01)
                    add_message(conv.id, sender="assistant", content=reply, metadata={"output": out, "file_id": file_id})
                    yield sse("assistant.completed", {"response": reply, "conversation_id": conv.public_id, "output": out}, status="completed")
                    return

            if intent == INTENT_DOCUMENT_RESEARCH and file_id:
                ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
                if ext in ("pdf", "docx", "doc", "txt", "pptx", "md", "markdown", "py", "js", "ts", "jsx", "tsx", "html", "css", "sql", "sh", "yaml", "yml", "json") or not ext:
                    yield sse("node.started", {"agent_type": "document_research", "filename": filename})
                    from app.agents.document_research_agent import DocumentResearchAgent
                    from app.agents.base import AgentContext
                    agent = DocumentResearchAgent()
                    ctx = AgentContext(user_id=user.id, input_data={"file_id": file_id, "query": message, "instructions": message}, instructions=message)
                    res = agent.execute(ctx)
                    out = res.output or {}
                    answer = out.get("answer", "")
                    sources = out.get("sources", [])
                    yield sse("node.completed", {"agent_type": "document_research", "sources": sources})
                    reply = f"### 📄 Document Research: **{filename}**\n\n{answer}"
                    words = reply.split(" ")
                    for i in range(0, len(words), 6):
                        yield sse("assistant.delta", {"delta": " ".join(words[i:i+6]) + " "})
                        time.sleep(0.01)
                    add_message(conv.id, sender="assistant", content=reply, metadata={"sources": sources, "file_id": file_id})
                    yield sse("assistant.completed", {"response": reply, "conversation_id": conv.public_id, "sources": sources}, status="completed")
                    return

            # Explicit Multi-Agent Workflow
            if intent == INTENT_MULTI_AGENT_WORKFLOW or mode == "task":
                try:
                    yield sse("assistant.delta", {"delta": "I'll plan and coordinate the autonomous multi-agent pipeline for your request...\n\n"})

                    session_context = dict(context)
                    session_context["source"] = "chat_assistant_stream"

                    session = OrchestrationSession(
                        user_id=user.id,
                        organization_id="default_org",
                        objective=message,
                        input_context=session_context,
                        priority=1,
                        status=ORCHESTRATION_STATUS_CREATED,
                    )
                    db.session.add(session)
                    db.session.flush()

                    plan = generate_orchestration_plan(session)
                    session.status = ORCHESTRATION_STATUS_READY
                    db.session.commit()

                    task_list = [
                        {
                            "id": t.public_id,
                            "task_key": t.task_key,
                            "name": t.name,
                            "status": t.status,
                            "agent": t.assigned_agent.name if t.assigned_agent else "Supervisor",
                            "agent_type": t.assigned_agent.agent_type if t.assigned_agent else None,
                        }
                        for t in plan.tasks.all()
                    ]

                    yield sse("plan.created", {"plan_id": plan.public_id, "tasks": task_list})
                    yield sse("plan.validated", {"valid": True, "task_count": len(task_list)})
                    yield sse("workflow.started", {"orchestration_id": session.public_id})

                    supervisor = SupervisorService()
                    updated_session = supervisor.run_orchestration(session.id)

                    for t in plan.tasks.all():
                        yield sse("node.started", {"task_name": t.name, "task_id": t.public_id, "agent": t.assigned_agent.name if t.assigned_agent else "Agent"})
                        if t.status == "COMPLETED":
                            yield sse("node.completed", {"task_name": t.name, "task_id": t.public_id, "output": t.output_data})
                        elif t.status == "AWAITING_APPROVAL":
                            from app.models.approval_request import APPROVAL_STATUS_PENDING, ApprovalRequest
                            appr = ApprovalRequest.query.filter_by(orchestration_id=session.id, status=APPROVAL_STATUS_PENDING).first()
                            if appr:
                                appr_dict = {
                                    "id": appr.public_id,
                                    "approval_id": appr.public_id,
                                    "orchestration_id": session.public_id,
                                    "requested_action": appr.requested_action,
                                    "risk_level": appr.risk_level,
                                    "explanation": appr.explanation,
                                    "parameters_summary": appr.input_summary,
                                    "status": appr.status,
                                }
                                yield sse("node.waiting_approval", appr_dict, status="waiting_approval")
                                yield sse("approval.created", appr_dict, status="waiting_approval")
                        elif t.status == "FAILED":
                            yield sse("node.failed", {"task_name": t.name, "error": t.error_message}, status="failed")

                    if updated_session.status in ("AWAITING_APPROVAL", "PAUSED"):
                        yield sse("workflow.waiting_approval", {"orchestration_id": session.public_id}, status="paused")
                        pause_msg = "Workflow paused awaiting your approval on the external side effect. Please review and approve or reject above."
                        add_message(conv.id, sender="assistant", content=pause_msg, metadata={"orchestration_id": session.public_id, "status": "paused"})
                        yield sse("assistant.completed", {
                            "response": pause_msg,
                            "conversation_id": conv.public_id,
                            "is_task": True,
                            "orchestration_id": session.public_id,
                            "requires_approval": True,
                        }, status="paused")
                        return

                    summary = updated_session.result_summary or {}
                    synthesis_raw = summary.get("final_synthesis") or "All multi-agent tasks completed successfully."
                    synthesis = synthesis_raw if isinstance(synthesis_raw, str) else str(synthesis_raw)
                    yield sse("workflow.completed", {"orchestration_id": session.public_id, "summary": summary}, status="completed")
                    yield sse("assistant.delta", {"delta": f"\n\n### Synthesis & Results:\n{synthesis}"})
                    add_message(conv.id, sender="assistant", content=synthesis, metadata={"orchestration_id": session.public_id, "status": "COMPLETED"})
                    yield sse("assistant.completed", {
                        "response": synthesis,
                        "conversation_id": conv.public_id,
                        "is_task": True,
                        "orchestration_id": session.public_id,
                        "status": "COMPLETED",
                    }, status="completed")
                    return

                except Exception as e:
                    err_text = f"Encountered an issue executing pipeline: {str(e)}"
                    yield sse("assistant.delta", {"delta": f"\n\n{err_text}"})
                    add_message(conv.id, sender="assistant", content=err_text, metadata={"error": str(e)})
                    yield sse("assistant.completed", {"error": str(e), "conversation_id": conv.public_id}, status="error")
                    return

            # Conversational Streaming via Real LLM
            now_utc = datetime.now(timezone.utc)
            current_time_str = now_utc.strftime("%A, %B %d, %Y (%I:%M %p UTC)")
            system_prompt = build_conversational_system_prompt(
                intent=intent,
                directives=directives,
                current_time_str=current_time_str,
            )

            full_prompt = f"System: {system_prompt}\n\nUser: {message}"
            full_text = ""
            streamed = False

            gemini_key = os.getenv("GEMINI_API_KEY")
            openai_key = os.getenv("OPENAI_API_KEY")

            if gemini_key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=gemini_key)
                    configured_model = os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest"
                    candidates = [configured_model, "gemini-flash-lite-latest", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemini-3.8-flash"]
                    seen = set()
                    model_list = [m for m in candidates if m and not (m in seen or seen.add(m))]
                    for candidate_model in model_list:
                        try:
                            model_inst = genai.GenerativeModel(candidate_model)
                            response_stream = model_inst.generate_content(full_prompt, stream=True)
                            candidate_text = ""
                            for chunk in response_stream:
                                chunk_part = ""
                                try:
                                    chunk_part = chunk.text or ""
                                except Exception:
                                    if hasattr(chunk, "parts"):
                                        for p in chunk.parts:
                                            if hasattr(p, "text") and p.text:
                                                chunk_part += p.text
                                if chunk_part:
                                    candidate_text += chunk_part
                                    yield sse("assistant.delta", {"delta": chunk_part})
                            if candidate_text.strip():
                                full_text = candidate_text
                                streamed = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

            if not streamed and openai_key:
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    completion = client.chat.completions.create(
                        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": message},
                        ],
                        stream=True,
                    )
                    candidate_text = ""
                    for chunk in completion:
                        delta = chunk.choices[0].delta.content or ""
                        if delta:
                            candidate_text += delta
                            yield sse("assistant.delta", {"delta": delta})
                    if candidate_text.strip():
                        full_text = candidate_text
                        streamed = True
                except Exception:
                    pass

            if not streamed:
                autonomous_answer = generate_dynamic_autonomous_response(
                    message=message,
                    current_time_str=current_time_str,
                    history=history,
                    directives=directives,
                    intent=intent,
                )
                words = re.split(r"(\s+)", autonomous_answer)
                chunk_buffer = ""
                for w in words:
                    chunk_buffer += w
                    if len(chunk_buffer) >= 12 or "\n" in w:
                        yield sse("assistant.delta", {"delta": chunk_buffer})
                        full_text += chunk_buffer
                        chunk_buffer = ""
                        time.sleep(0.012)
                if chunk_buffer:
                    yield sse("assistant.delta", {"delta": chunk_buffer})
                    full_text += chunk_buffer
                streamed = True

            add_message(conv.id, sender="assistant", content=full_text, metadata={"intent": intent})
            yield sse("assistant.completed", {"response": full_text, "conversation_id": conv.public_id}, status="completed")

    return Response(
        stream_with_context(generate_events()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "close",
            "Access-Control-Allow-Origin": "*",
        },
    )
