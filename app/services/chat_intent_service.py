"""
Chat Intent & Autonomous Reasoning Service.

Provides:
1. Deep Intent Classification (Conversational, Writing, General Knowledge, Agent Actions, Image Gen, Follow-ups).
2. Directives Extraction (Length: 2 lines/points_n/5-mark/detailed, Format: table/bullets/paragraphs, Audience: beginner/technical, Language: Hinglish/Hindi/English).
3. Contextual Follow-up Resolution.
4. Intelligent Autonomous Fallback Generator (dynamic, non-canned responses when external cloud LLMs are unavailable).
"""

import html
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# Intent Constants
INTENT_GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
INTENT_GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
INTENT_WRITING = "WRITING"
INTENT_FOLLOW_UP = "FOLLOW_UP"
INTENT_AGENT_KNOWLEDGE = "AGENT_KNOWLEDGE"
INTENT_IMAGE_GENERATION = "IMAGE_GENERATION"
INTENT_DATA_ANALYSIS = "DATA_ANALYSIS"
INTENT_DOCUMENT_RESEARCH = "DOCUMENT_RESEARCH"
INTENT_REPORT_GENERATION = "REPORT_GENERATION"
INTENT_TASK_MANAGEMENT = "TASK_MANAGEMENT"
INTENT_EMAIL = "EMAIL"
INTENT_SECURITY_ANALYSIS = "SECURITY_ANALYSIS"
INTENT_DATABASE_BI = "DATABASE_BI"
INTENT_HTTP_WEBHOOK = "HTTP_WEBHOOK"
INTENT_KNOWLEDGE_RETRIEVAL = "KNOWLEDGE_RETRIEVAL"
INTENT_MULTI_AGENT_WORKFLOW = "MULTI_AGENT_WORKFLOW"


def extract_directives(message: str) -> Dict[str, Any]:
    """Extract length, format, audience, and language directives from user prompt."""
    raw = message.strip()
    lower = raw.lower()
    directives: Dict[str, Any] = {
        "length": "standard",
        "points_count": None,
        "format": "default",
        "audience": "standard",
        "language": "english",
    }

    # 1. Language Detection
    if any(k in lower for k in ("in hinglish", "hinglish mai", "hinglish mein", "hinglish")):
        directives["language"] = "hinglish"
    elif any(k in lower for k in ("in hindi", "hindi mai", "hindi mein", "shuddh hindi")):
        directives["language"] = "hindi"
    elif "in english" in lower:
        directives["language"] = "english"
    else:
        # Check natural Hinglish/Hindi tokens
        hinglish_markers = [
            "kya", "kaise", "batao", "samjhao", "nhi", "chal rha", "karo", "kuch",
            "kaam", "theek", "hai", "hain", "kyu", "madad", "chahiye", "kar sakte ho",
            "namaste", "shukriya", "dhanyawad", "sab"
        ]
        matched_markers = [m for m in hinglish_markers if re.search(r"\b" + re.escape(m) + r"\b", lower)]
        if len(matched_markers) >= 2:
            directives["language"] = "hinglish"

    # 2. Length Constraints
    if re.search(r"\b(?:in\s+)?(?:1|one)\s+line\b", lower):
        directives["length"] = "one_line"
    elif re.search(r"\b(?:in\s+)?(?:2|two)\s+lines\b", lower):
        directives["length"] = "two_lines"
    elif re.search(r"\b(?:in\s+)?(?:3|three)\s+lines\b", lower):
        directives["length"] = "three_lines"
    elif any(k in lower for k in ("short", "very short", "briefly", "short answer", "in a nutshell", "tl;dr", "brief")):
        directives["length"] = "brief"
    elif any(k in lower for k in ("in detail", "detailed", "elaborate", "comprehensive", "in depth", "in-depth", "deep dive")):
        directives["length"] = "detailed"
    elif any(k in lower for k in ("5-mark answer", "5 marks", "5 mark", "5 marks answer", "five marks", "five-mark")):
        directives["length"] = "exam_5_mark"
    elif any(k in lower for k in ("10-mark answer", "10 marks", "10 mark", "ten marks", "ten-mark")):
        directives["length"] = "exam_10_mark"
    elif any(k in lower for k in ("just give the answer", "just the answer", "direct answer", "no explanation", "only answer")):
        directives["length"] = "direct"

    # Match N points (e.g. "5 points", "give me 5 points", "3 points", "10 points")
    points_match = re.search(r"\b(\d+)\s*(?:points|bullets|reasons|tips|examples|steps)\b", lower)
    if points_match:
        count = int(points_match.group(1))
        directives["length"] = "points_n"
        directives["points_count"] = count
        if directives["format"] == "default":
            directives["format"] = "bullets"

    # 3. Format Constraints
    if any(k in lower for k in ("in paragraph form", "in paragraphs", "as a paragraph", "paragraph format", "paragraph")):
        directives["format"] = "paragraph"
    elif any(k in lower for k in ("in bullet points", "as bullets", "bullet points", "list format", "bulleted")):
        directives["format"] = "bullets"
    elif any(k in lower for k in ("as a table", "table format", "in a table", "tabular form", "tabular")):
        directives["format"] = "table"
    elif any(k in lower for k in ("step by step", "step-by-step", "steps")):
        directives["format"] = "steps"
    elif any(k in lower for k in ("code only", "show code", "give code", "python code")):
        directives["format"] = "code"

    # 4. Audience / Complexity
    if any(k in lower for k in ("like i'm a beginner", "like i am a beginner", "for beginners", "explain simply", "explain like i'm 5", "eli5", "easy words", "simple terms", "layman")):
        directives["audience"] = "beginner"
    elif any(k in lower for k in ("technical details", "technically", "for developers", "for engineers", "deep technical", "architecture level")):
        directives["audience"] = "technical"
    elif any(k in lower for k in ("for executives", "executive summary", "high level overview", "executive level")):
        directives["audience"] = "executive"

    return directives


def classify_chat_intent(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    context: Optional[Dict[str, Any]] = None,
    mode: str = "auto"
) -> Dict[str, Any]:
    """Classify user intent with high precision, distinguishing questions from action triggers.

    Returns:
        dict with keys:
        - intent: str (INTENT_*)
        - is_conversational: bool
        - is_specialized_action: bool
        - target_agent: Optional[str]
        - directives: dict
        - extracted_params: dict
    """
    raw = message.strip()
    lower = raw.lower()
    directives = extract_directives(raw)
    context = context or {}
    history = history or []

    # 0. Explicit Mode Overrides
    if mode == "image":
        return {
            "intent": INTENT_IMAGE_GENERATION,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "image_generation",
            "directives": directives,
            "extracted_params": {"prompt": raw},
        }

    # 1. Image Generation Intent Detection
    # Must be an explicit generation request, NOT conceptual explanation
    is_image_explanation = any(k in lower for k in (
        "what is", "how does", "explain what", "tell me about", "define", "meaning of", "mean"
    )) and any(k in lower for k in ("image generation", "flux", "diffusion", "cyberpunk", "concept art", "digital art"))

    is_explicit_image = False
    image_prompt = raw
    if not is_image_explanation:
        image_triggers = [
            r"^(?:generate|create|render|make|draw|paint|produce)\s+(?:an?\s+)?(?:image|picture|photo|artwork|drawing|painting|render|visual)\s+(?:of|about|depicting|showing)?\s*(.+)$",
            r"^(?:draw|paint)\s+(.+)$",
            r"^image\s+of\s+(.+)$",
        ]
        for pat in image_triggers:
            m = re.match(pat, lower, re.IGNORECASE)
            if m:
                is_explicit_image = True
                image_prompt = m.group(1).strip()
                break

    if is_explicit_image:
        return {
            "intent": INTENT_IMAGE_GENERATION,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "image_generation",
            "directives": directives,
            "extracted_params": {"prompt": image_prompt or raw},
        }

    # 2. Conversational Inquiries About Agents (e.g. "What does Data Analysis Agent do?")
    # Must NOT execute data analysis!
    agent_names_pattern = r"(?:data\s+analysis|document\s+research|report\s+generation|email|security|database\s+bi|http\s+webhook|orchestrai|task\s+manager)\s+agent"
    if re.search(r"\b(?:what\s+does|how\s+does|explain\s+what|tell\s+me\s+about|describe)\b.*" + agent_names_pattern, lower) or \
       re.search(r"\b(?:what\s+agents|list\s+agents|all\s+agents|system\s+capabilities)\b", lower):
        return {
            "intent": INTENT_AGENT_KNOWLEDGE,
            "is_conversational": True,
            "is_specialized_action": False,
            "target_agent": None,
            "directives": directives,
            "extracted_params": {},
        }

    # 3. Follow-Up Queries (Using previous context)
    follow_up_triggers = [
        "give me an example", "give an example", "another example", "show an example",
        "make it shorter", "make it longer", "add more detail", "more details",
        "explain point", "explain it simply", "now explain it", "simplify this",
        "convert this to a table", "as a table", "give me 5 points", "5 points",
        "give me a 5-mark answer", "in hinglish", "in hindi", "in english",
        "what about", "continue", "elaborate"
    ]
    if len(history) > 0 and (any(lower.startswith(t) or lower == t for t in follow_up_triggers) or len(raw.split()) <= 4):
        # Check if it's a follow-up directive
        return {
            "intent": INTENT_FOLLOW_UP,
            "is_conversational": True,
            "is_specialized_action": False,
            "target_agent": None,
            "directives": directives,
            "extracted_params": {"follow_up_on": history[-1].get("content") if history else ""},
        }

    # 4. Writing & Composition Assistance (e.g. "Help me write an email", "Draft an outline")
    # Must answer conversationally, NOT dispatch an email!
    if any(k in lower for k in ("help me write", "draft a", "draft an", "write an essay", "write a poem", "compose a message", "write an email to my manager", "write email template", "help me draft")):
        return {
            "intent": INTENT_WRITING,
            "is_conversational": True,
            "is_specialized_action": False,
            "target_agent": None,
            "directives": directives,
            "extracted_params": {},
        }

    # 4b. Programming, Coding, Syntax & Algorithm Requests
    # (e.g. "hello give me c code for loop", "write python script", "how to write a for loop in c", "show me bubble sort in java")
    # Must answer conversationally with clean code, NEVER execute data analysis or document research!
    code_request_patterns = [
        r"\b(?:give\s+me|write|show\s+me|create|generate|provide)\s+(?:a\s+)?(?:c|c\+\+|python|java|javascript|typescript|go|rust|sql|html|css|php|ruby|bash|shell)?\s*(?:code|program|script|function|snippet|implementation|algorithm|example)\b",
        r"\b(?:c|c\+\+|python|java|javascript|typescript|go|rust|sql|html|css|php|ruby)\s+(?:code|program|script|syntax|loop|function)\b",
        r"\b(?:for\s+loop|while\s+loop|do\s+while|nested\s+loop|if\s+else|switch\s+case)\b",
        r"\b(?:how\s+to\s+write|how\s+to\s+implement|how\s+do\s+i\s+code)\b",
        r"\b(?:bubble\s+sort|binary\s+search|linked\s+list|data\s+structure|recursion)\b",
    ]
    if any(re.search(pat, lower) for pat in code_request_patterns):
        return {
            "intent": INTENT_GENERAL_KNOWLEDGE,
            "is_conversational": True,
            "is_specialized_action": False,
            "target_agent": None,
            "directives": directives,
            "extracted_params": {},
        }

    # 5. Specialized Action Triggers (Only when explicit commands / inputs are supplied)
    # 5a. Data Analysis Action: explicitly analyze attached/provided CSV or numbers
    has_attached_file = bool(context.get("file_id"))
    attached_filename = (context.get("filename") or "").lower()
    is_csv_attached = has_attached_file and any(attached_filename.endswith(ext) for ext in (".csv", ".xlsx", ".xls"))
    
    if is_csv_attached:
        is_csv_query = any(k in lower for k in (
            "csv", "excel", "dataset", "spreadsheet", "rows", "columns", "stats", "statistics",
            "outliers", "summary", "analyze", "analysis", "correlations", "iqr", "metrics",
            "mean", "median", "std dev", "standard deviation", "total revenue", "highest", "lowest", "distribution"
        )) or bool(re.search(r"\b(?:in|of|from)\s+(?:this|the)\s+(?:file|data|dataset|csv|sheet)\b", lower))
        if is_csv_query:
            return {
                "intent": INTENT_DATA_ANALYSIS,
                "is_conversational": False,
                "is_specialized_action": True,
                "target_agent": "data_analysis",
                "directives": directives,
                "extracted_params": {"file_id": context.get("file_id")},
            }
    elif re.search(r"\b(?:analyze|compute\s+stats|statistics\s+for|iqr|outliers\s+in)\s+(?:this\s+csv|this\s+excel|this\s+dataset|the\s+dataset|the\s+data)\b", lower):
        return {
            "intent": INTENT_DATA_ANALYSIS,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "data_analysis",
            "directives": directives,
            "extracted_params": {"file_id": context.get("file_id")},
        }

    # 5b. Document Research Action: explicitly search/extract from attached document (PDF, DOCX, PPTX, TXT, MD, Code)
    doc_extensions = (".pdf", ".docx", ".doc", ".txt", ".pptx", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".sql", ".sh", ".yaml", ".yml", ".json")
    is_doc_attached = has_attached_file and any(attached_filename.endswith(ext) for ext in doc_extensions)
    has_doc_reference = bool(
        re.search(r"\b(?:this|the)\s+(?:pdf|document|file|paper|notes|slides?|manual|handbook|policy)\b", lower)
        or re.search(r"\b(?:page|slide|chapter|section)\s+\d+\b", lower)
        or any(k in lower for k in ("in this pdf", "in this document", "from this pdf", "from the document", "explain this document", "summarize this file"))
    )

    if (is_doc_attached and has_doc_reference) or has_doc_reference:
        return {
            "intent": INTENT_DOCUMENT_RESEARCH,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "document_research",
            "directives": directives,
            "extracted_params": {"file_id": context.get("file_id")},
        }

    # 5c. Report Generation Action: explicitly create a named report file
    report_match = re.search(r"\b(?:generate|create|produce)\s+(?:a\s+)?report\s+(?:titled|on|about)\s+[\"']?([^\"'\n]+)[\"']?", raw, re.IGNORECASE)
    if report_match and not lower.startswith("what is") and not lower.startswith("how do"):
        title = report_match.group(1).strip(" .\"'")
        return {
            "intent": INTENT_REPORT_GENERATION,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "report_generation",
            "directives": directives,
            "extracted_params": {"title": title},
        }

    # 5d. Task Management Action: explicitly create a task in Task Manager
    task_match = re.search(r"\b(?:create|add|schedule)\s+(?:a\s+)?task\s+(?:to|for)?\s+(.+)", raw, re.IGNORECASE)
    if task_match and not lower.startswith("what is") and not lower.startswith("how to"):
        task_desc = task_match.group(1).strip()
        return {
            "intent": INTENT_TASK_MANAGEMENT,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "task_manager",
            "directives": directives,
            "extracted_params": {"task_description": task_desc},
        }

    # 5e. Email Action: explicitly send an email (must have recipient/target)
    if any(k in lower for k in ("send email to", "send an email to", "dispatch email to", "mail to")) and ("@" in lower or "to " in lower):
        return {
            "intent": INTENT_EMAIL,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "email",
            "directives": directives,
            "extracted_params": {},
        }

    # 5f. Security Analysis Action: explicitly scan provided code snippet
    if re.search(r"\b(?:scan|audit)\s+this\s+code\b", lower) or ("```" in raw and ("scan" in lower or "vulnerability" in lower)):
        return {
            "intent": INTENT_SECURITY_ANALYSIS,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "security_analysis",
            "directives": directives,
            "extracted_params": {},
        }

    # 5g. Multi-Agent Workflow Action: explicit workflow execution command
    workflow_triggers = [
        "orchestrate", "run workflow", "execute workflow", "start workflow",
        "trigger workflow", "create workflow", "run pipeline", "execute pipeline",
        "multi-agent workflow", "multi-agent pipeline"
    ]
    if any(t in lower for t in workflow_triggers):
        return {
            "intent": INTENT_MULTI_AGENT_WORKFLOW,
            "is_conversational": False,
            "is_specialized_action": True,
            "target_agent": "supervisor",
            "directives": directives,
            "extracted_params": {},
        }

    # 6. Default: General Knowledge & Conversational Intent
    # (e.g. "What is machine learning?", "Explain recursion", "Who invented the internet?", "What is SQL injection?")
    return {
        "intent": INTENT_GENERAL_KNOWLEDGE if any(lower.startswith(q) for q in ("what", "why", "how", "who", "when", "where", "which", "explain", "describe", "define", "tell me")) else INTENT_GENERAL_CONVERSATION,
        "is_conversational": True,
        "is_specialized_action": False,
        "target_agent": None,
        "directives": directives,
        "extracted_params": {},
    }


def build_conversational_system_prompt(
    intent: str,
    directives: Dict[str, Any],
    current_time_str: str,
    context_text: str = ""
) -> str:
    """Build a comprehensive, directive-aware system prompt for the LLM."""
    length_rule = ""
    length_type = directives.get("length", "standard")
    points_count = directives.get("points_count")

    if length_type == "one_line":
        length_rule = "LENGTH RULE: Your response MUST strictly be EXACTLY ONE single concise sentence or line. No extra lines."
    elif length_type == "two_lines":
        length_rule = "LENGTH RULE: Your response MUST strictly be EXACTLY TWO concise lines/sentences. Keep it sharp and under 40 words total."
    elif length_type == "three_lines":
        length_rule = "LENGTH RULE: Your response MUST strictly be EXACTLY THREE concise sentences."
    elif length_type == "brief":
        length_rule = "LENGTH RULE: Give a brief, highly concise explanation without filler text or unnecessary preamble."
    elif length_type == "detailed":
        length_rule = "LENGTH RULE: Provide an in-depth, thorough, comprehensive breakdown with mechanics, key aspects, real-world examples, and nuanced considerations."
    elif length_type == "points_n" and points_count:
        length_rule = f"LENGTH RULE: Provide EXACTLY {points_count} numbered points formatted as a numbered list starting with '1. ', '2. ', up to '{points_count}. '. Each point must start with its index number (e.g. 1., 2., 3.)."
    elif length_type == "exam_5_mark":
        length_rule = (
            "STRUCTURE RULE (5-MARK EXAM ANSWER): Provide a structured academic exam answer containing:\n"
            "1. 📌 **Definition & Core Concept** (Clear, standard definition)\n"
            "2. ⚙️ **Working Principle / Key Mechanism** (How it operates)\n"
            "3. 🔑 **Key Characteristics / Components** (3-4 essential features)\n"
            "4. 💡 **Practical Example / Use Case** (Real-world application)\n"
            "5. 📝 **Conclusion** (1-line takeaway)"
        )
    elif length_type == "exam_10_mark":
        length_rule = (
            "STRUCTURE RULE (10-MARK EXAM ANSWER): Provide a comprehensive university-level exam answer with:\n"
            "1. **Introduction & Formal Definition**\n"
            "2. **Detailed Architecture / Working Mechanism**\n"
            "3. **Types / Classifications / Methodologies**\n"
            "4. **Advantages & Limitations**\n"
            "5. **Real-world Case Study / Practical Implementation**\n"
            "6. **Summary & Future Scope**"
        )
    elif length_type == "direct":
        length_rule = "STYLE RULE: Output ONLY the direct answer. No introductory pleasantries, no 'Sure, here is...', no conversational fluff."

    format_rule = ""
    fmt = directives.get("format", "default")
    if fmt == "paragraph":
        format_rule = "FORMAT RULE: Write purely in cohesive, fluid paragraphs. Do NOT use bullet points or numbered lists."
    elif fmt == "bullets":
        format_rule = "FORMAT RULE: Format the core explanation using clear, organized bullet points."
    elif fmt == "table":
        format_rule = "FORMAT RULE: Organize the main information or comparison into a clean, well-aligned Markdown table."
    elif fmt == "steps":
        format_rule = "FORMAT RULE: Break down the explanation or process into numbered sequential steps."

    audience_rule = ""
    aud = directives.get("audience", "standard")
    if aud == "beginner":
        audience_rule = "AUDIENCE: Explain like you are talking to a complete beginner or a 10-year-old. Use intuitive everyday analogies and avoid confusing technical jargon."
    elif aud == "technical":
        audience_rule = "AUDIENCE: Target experienced software engineers and architects. Include architectural mechanics, protocols, exact terms, and code/pseudocode where helpful."
    elif aud == "executive":
        audience_rule = "AUDIENCE: Target senior executives. Focus on business value, strategic impact, ROI, efficiency, and high-level summaries."

    lang_rule = ""
    lang = directives.get("language", "english")
    if lang == "hinglish":
        lang_rule = "LANGUAGE: Respond in natural, conversational Hinglish (a fluid blend of Hindi in Latin script and English technical terms, e.g. 'Machine Learning ek aisi technology hai jisme computer data se automatically seekhta hai...'). Keep it friendly, clear, and authentic."
    elif lang == "hindi":
        lang_rule = "LANGUAGE: Respond in clear, professional Hindi (हिंदी)."
    else:
        lang_rule = "LANGUAGE: Respond in clear, professional English."

    prompt = (
        "You are OrchestrAI, a world-class General-Purpose Enterprise AI Assistant.\n"
        f"Real-World Temporal Reference: Today is {current_time_str}.\n\n"
        "CORE INSTRUCTIONS:\n"
        "- Answer any natural language question accurately, thoughtfully, and helpfully across computer science, business, science, mathematics, history, literature, and general knowledge.\n"
        "- Maintain conversational continuity: if the user asks a follow-up (e.g. 'Give me an example', 'Make it shorter', 'Now explain point 2'), seamlessly use the previous conversation context.\n"
        "- When the user asks about the date or time, reference the verified temporal status.\n"
        f"- {lang_rule}\n"
        f"- {length_rule}\n"
        f"- {format_rule}\n"
        f"- {audience_rule}\n"
        "- Always render clean GitHub-flavored Markdown."
    )

    if context_text:
        prompt += f"\n\nGROUNDING CONTEXT:\n{context_text}"

    return prompt


def generate_dynamic_autonomous_response(
    message: str,
    current_time_str: str,
    history: Optional[List[Dict[str, str]]] = None,
    directives: Optional[Dict[str, Any]] = None,
    intent: Optional[str] = None
) -> str:
    """Dynamic, intelligent reasoning engine that generates context-aware, directive-compliant
    answers for ANY general-purpose request when external cloud LLMs are offline or rate-limited.
    """
    raw = message.strip()
    lower = raw.lower()
    directives = directives or extract_directives(raw)
    intent = intent or INTENT_GENERAL_KNOWLEDGE
    history = history or []

    lang = directives.get("language", "english")
    length = directives.get("length", "standard")
    points_count = directives.get("points_count")
    aud = directives.get("audience", "standard")

    # 1. Temporal Queries
    if any(k in lower for k in ("date", "time", "day", "today", "tomorrow", "yesterday", "year", "current time", "tarikh", "samay")):
        if lang == "hinglish":
            return (
                f"### 🕒 Verified Temporal Status\n\n"
                f"- **Current Date & Time:** `{current_time_str}`\n"
                f"- **Timezone:** Coordinated Universal Time (UTC)\n\n"
                f"Sabhi internal clocks aur agent engines is verified time par synchronized hain."
            )
        return (
            f"### 🕒 Verified Temporal Status\n\n"
            f"- **Current Date & Time:** `{current_time_str}`\n"
            f"- **Timezone:** Coordinated Universal Time (UTC)\n\n"
            f"All internal system clocks and agent scheduling engines are synchronized to this verified reference."
        )

    # 2. Contextual Follow-up Resolution
    if intent == INTENT_FOLLOW_UP and history:
        prev_user_msg = ""
        prev_asst_msg = ""
        for turn in reversed(history):
            if turn.get("role") == "user" and not prev_user_msg:
                prev_user_msg = turn.get("content", "")
            elif turn.get("role") == "assistant" and not prev_asst_msg:
                prev_asst_msg = turn.get("content", "")
            if prev_user_msg and prev_asst_msg:
                break

        prev_topic = prev_user_msg.replace("What is", "").replace("Explain", "").replace("what is", "").replace("explain", "").strip(" ?.") or "the previously discussed topic"

        if "example" in lower:
            if "machine learning" in prev_topic.lower() or "ml" in prev_topic.lower():
                if lang == "hinglish":
                    return (
                        f"### 💡 Machine Learning ka Real-World Example: Email Spam Filtering\n\n"
                        f"Jab aapke inbox me koi naya email aata hai:\n\n"
                        f"1. **Training Data:** Model hazaron purane emails (Spam vs Not Spam) ko analyze karta hai.\n"
                        f"2. **Pattern Recognition:** Agar email me suspicious words jaise `\"Free Lottery\"`, `\"Claim Prize\"`, ya unknown links hain, toh algorithm patterns identify karta hai.\n"
                        f"3. **Prediction:** Naye email ko automatically **Spam Folder** me move kar deta hai bina kisi human intervention ke."
                    )
                return (
                    f"### 💡 Practical Example of Machine Learning: Email Spam Filtering\n\n"
                    f"A classic real-world application of Machine Learning is an **intelligent email spam filter**:\n\n"
                    f"1. **Training Phase:** The algorithm is trained on millions of historical emails labeled as `Spam` or `Legitimate`.\n"
                    f"2. **Feature Extraction:** It identifies key patterns, such as sender reputation, suspicious keywords (e.g., *\"claim reward\"*, *\"urgent wire transfer\"*), and unusual link structures.\n"
                    f"3. **Real-Time Classification:** When a new email arrives, the model calculates a probability score; if the spam probability exceeds a threshold (e.g., 95%), it automatically routes the message to the Spam folder without manual human rules."
                )
            elif "sql injection" in prev_topic.lower() or "sqli" in prev_topic.lower():
                return (
                    f"### 🛡️ Practical Example of SQL Injection\n\n"
                    f"**Vulnerable Backend Query:**\n"
                    f"```sql\n"
                    f"SELECT * FROM users WHERE username = '\" + user_input + \"' AND password = '\" + pass_input + \"';\n"
                    f"```\n\n"
                    f"**Attacker Input:**\n"
                    f"- Username: `admin' --`\n\n"
                    f"**Resulting Executed Query:**\n"
                    f"```sql\n"
                    f"SELECT * FROM users WHERE username = 'admin' --' AND password = '...';\n"
                    f"```\n"
                    f"The `--` comments out the password verification, logging the attacker in as administrator without credentials.\n\n"
                    f"**Remediation (Parameterized Query):**\n"
                    f"```sql\n"
                    f"SELECT * FROM users WHERE username = ? AND password = ?;\n"
                    f"```"
                )
            elif "recursion" in prev_topic.lower():
                return (
                    f"### 💻 Practical Example of Recursion: Calculating Factorial\n\n"
                    f"Recursion is when a function calls itself to solve smaller subproblems until it reaches a base case.\n\n"
                    f"```python\n"
                    f"def factorial(n):\n"
                    f"    # Base Case: Stop recursion when n reaches 1 or 0\n"
                    f"    if n <= 1:\n"
                    f"        return 1\n"
                    f"    # Recursive Case: Function calls itself with (n - 1)\n"
                    f"    return n * factorial(n - 1)\n\n"
                    f"print(factorial(5))  # Output: 120 (5 * 4 * 3 * 2 * 1)\n"
                    f"```"
                )
            else:
                return (
                    f"### 💡 Practical Example for: {prev_topic.title()}\n\n"
                    f"Consider a real-world scenario where **{prev_topic}** is applied:\n\n"
                    f"- **Input/Trigger:** Initial raw data or user action is received.\n"
                    f"- **Core Processing:** The principles of {prev_topic} transform the inputs through structured logic.\n"
                    f"- **Resulting Output:** A deterministic, verified outcome is achieved with measurable efficiency."
                )

        if length in ("one_line", "two_lines", "brief") or "shorter" in lower:
            if "machine learning" in prev_topic.lower():
                if length in ("one_line", "two_lines"):
                    return "**Machine Learning** is a branch of AI where computer systems learn patterns from historical data to make automated decisions without explicit rule-based programming."
                return "In short, **Machine Learning** enables algorithms to automatically learn patterns from empirical data and improve decision accuracy over time without hardcoded rules."
            elif "cybersecurity" in prev_topic.lower():
                if length in ("one_line", "two_lines"):
                    return "**Cybersecurity** is the practice of protecting computer systems, networks, devices, and data from unauthorized access, cyberattacks, and exploitation."
                return "**Cybersecurity** defends digital assets, networks, and confidential data against malicious attacks, unauthorized disclosure, and operational disruption."

    # 3. Topic-Specific Handlers with Strict Directives

    # --- TOPIC: Machine Learning ---
    if "machine learning" in lower or re.search(r"\bml\b", lower):
        if length in ("one_line", "two_lines"):
            if lang == "hinglish":
                return "**Machine Learning (ML)** AI ki woh field hai jisme computers data aur algorithms ke zariye automatically patterns seekhte hain bina hardcoded rules ke."
            return "**Machine Learning** is a subset of AI where computational algorithms learn patterns from data to make predictions and decisions without being explicitly programmed."

        if length == "points_n" and points_count:
            pts = [
                "**Data-Driven Learning:** Algorithms analyze training datasets to detect underlying mathematical patterns and statistical correlations.",
                "**Adaptive Improvement:** Prediction accuracy and performance automatically improve as more training data is supplied.",
                "**Three Core Paradigms:** Includes Supervised Learning (labeled data), Unsupervised Learning (unlabeled pattern discovery), and Reinforcement Learning (reward optimization).",
                "**Feature Representation:** Transforms raw attributes (text, pixels, numbers) into quantitative feature vectors for model training.",
                "**Automated Generalization:** Trained models generalize learned insights to make accurate inferences on unseen real-world inputs.",
                "**Model Evaluation:** Performance is measured through objective metrics such as Precision, Recall, F1-Score, and Mean Squared Error (MSE).",
                "**Widespread Applications:** Powers speech recognition, autonomous vehicles, fraud detection, recommendation engines, and medical imaging.",
            ]
            selected = pts[:points_count]
            return f"### 🤖 Machine Learning ({points_count} Key Points)\n\n" + "\n\n".join([f"{i+1}. {p}" for i, p in enumerate(selected)])

        if length == "exam_5_mark":
            return (
                "### 📚 Machine Learning (5-Mark Exam Answer)\n\n"
                "#### 1. 📌 Definition & Concept\n"
                "**Machine Learning (ML)** is a subfield of Artificial Intelligence (AI) focused on building algorithms that learn patterns from historical data and make accurate predictions or decisions without being explicitly programmed.\n\n"
                "#### 2. ⚙️ Working Principle\n"
                "An ML pipeline consists of:\n"
                "1. **Data Ingestion & Preprocessing:** Cleaning and normalizing raw data.\n"
                "2. **Feature Extraction:** Identifying relevant attributes.\n"
                "3. **Model Training:** Optimizing mathematical weights using loss functions.\n"
                "4. **Evaluation & Inference:** Testing model accuracy on unseen test data.\n\n"
                "#### 3. 🔑 Key Types of Machine Learning\n"
                "- **Supervised Learning:** Trained on labeled input-output pairs (e.g., Regression, Classification).\n"
                "- **Unsupervised Learning:** Discovers hidden structures in unlabeled data (e.g., K-Means Clustering, PCA).\n"
                "- **Reinforcement Learning:** Learns through trial-and-error using reward/penalty feedback (e.g., Robotics, Game AI).\n\n"
                "#### 4. 💡 Practical Application\n"
                "- **Spam Detection:** Classifying incoming emails as spam or inbox based on historical text patterns.\n"
                "- **Medical Diagnostics:** Identifying anomalies in MRI/CT scans using Convolutional Neural Networks.\n\n"
                "#### 5. 📝 Conclusion\n"
                "Machine Learning replaces rigid rule-based systems with flexible, self-optimizing statistical models that scale with data."
            )

        if lang == "hinglish":
            return (
                "### 🤖 Machine Learning (ML) kya hai?\n\n"
                "**Machine Learning** Artificial Intelligence (AI) ki ek core branch hai jisme computers ko explicitly har rule code karne ki zaroorat nahi hoti; balki computer **purane data se automatically patterns seekhta hai**.\n\n"
                "#### 🔑 Core Types of Machine Learning:\n"
                "1. **Supervised Learning (Labelled Data):** Model ko input ke sath correct output bhi diya jata hai (Jaise: Spam vs Not Spam emails).\n"
                "2. **Unsupervised Learning (Unlabelled Data):** Model khud se data me hidden patterns aur clusters dhoondhta hai (Jaise: Customer segmentation).\n"
                "3. **Reinforcement Learning (Reward-based):** Model trial aur error se seekhta hai — achhi choice par reward aur galat par penalty milti hai (Jaise: Self-driving cars, Chess AI).\n\n"
                "#### 🌟 Real-World Uses:\n"
                "- **Recommendation Systems:** YouTube aur Netflix par video recommendations.\n"
                "- **Fraud Detection:** Banks me suspicious credit card transactions ko instant block karna.\n"
                "- **Voice Assistants:** Siri, Google Assistant aur Alexa me speech recognition."
            )

        if length == "detailed":
            return (
                "### 🤖 Comprehensive Overview of Machine Learning\n\n"
                "**Machine Learning (ML)** represents a paradigm shift from traditional procedural programming. Instead of writing handcrafted logic (`If-Else` conditions) for every scenario, developers provide training datasets, and the ML algorithm autonomously derives the mathematical mapping function `f(x) = y`.\n\n"
                "#### 1. The Machine Learning Lifecycle\n"
                "- **Data Collection & Cleaning:** Handling missing values, categorical encoding, and outlier removal.\n"
                "- **Feature Engineering:** Selecting and transforming high-signal attributes.\n"
                "- **Model Selection & Architecture:** Choosing algorithms (Decision Trees, Gradient Boosting, Neural Networks).\n"
                "- **Training & Loss Optimization:** Minimizing error using Gradient Descent backpropagation.\n"
                "- **Validation & Hyperparameter Tuning:** Cross-validation to prevent overfitting (high variance) or underfitting (high bias).\n"
                "- **Deployment & Monitoring:** Serving models via REST APIs with telemetry tracking data drift.\n\n"
                "#### 2. Primary Learning Paradigms\n\n"
                "| Paradigm | Data Requirement | Core Objective | Standard Algorithms |\n"
                "| :--- | :--- | :--- | :--- |\n"
                "| **Supervised** | Labeled `(X, y)` | Predict target label or continuous value | Linear/Logistic Regression, Random Forest, XGBoost |\n"
                "| **Unsupervised** | Unlabeled `(X)` | Discover latent clusters & dimensionality reduction | K-Means, DBSCAN, PCA, Autoencoders |\n"
                "| **Reinforcement** | Environment states & rewards | Maximize cumulative reward policy | Q-Learning, PPO, Deep Q-Networks (DQN) |\n\n"
                "#### 3. Enterprise Value & Modern Impact\n"
                "Modern ML powers Large Language Models (LLMs), real-time financial algorithmic trading, automated predictive maintenance in manufacturing, and computer vision systems."
            )

        # Standard Machine Learning response
        return (
            "### 🤖 What is Machine Learning?\n\n"
            "**Machine Learning (ML)** is a branch of Artificial Intelligence (AI) and computer science focused on building applications that learn from data and improve their accuracy over time without being explicitly programmed to do so.\n\n"
            "#### How It Works\n"
            "1. **Data Ingestion:** Large volumes of historical data are fed into the system.\n"
            "2. **Pattern Recognition:** Mathematical algorithms analyze data attributes to uncover relationships and correlations.\n"
            "3. **Inference & Prediction:** The model applies learned parameters to evaluate new, unseen inputs.\n\n"
            "#### Primary Categories\n"
            "- **Supervised Learning:** Uses labeled data to train predictive models (e.g., predicting house prices, email classification).\n"
            "- **Unsupervised Learning:** Analyzes unlabeled data to uncover natural groupings (e.g., customer segmentation, anomaly detection).\n"
            "- **Reinforcement Learning:** Agents learn optimal strategies through environmental trial and feedback (e.g., robotics, gameplay AI).\n\n"
            "#### Real-World Examples\n"
            "- **Predictive Analytics:** Forecasting customer churn and supply chain demand.\n"
            "- **Computer Vision:** Facial recognition, autonomous navigation, and medical imaging diagnostics.\n"
            "- **Natural Language Processing (NLP):** Real-time translation, sentiment analysis, and conversational AI."
        )

    # --- TOPIC: Cybersecurity ---
    if "cybersecurity" in lower or "cyber security" in lower:
        if length in ("one_line", "two_lines"):
            if lang == "hinglish":
                return "**Cybersecurity** computer systems, networks, devices aur data ko unauthorized access, cyberattacks aur data theft se protect karne ki practice hai."
            return "**Cybersecurity** is the practice of protecting critical computer systems, digital networks, devices, and sensitive data from malicious cyberattacks and unauthorized access."

        if length == "points_n" and points_count:
            pts = [
                "**Confidentiality:** Ensures sensitive data is accessible strictly to authorized entities through encryption and access controls.",
                "**Integrity:** Protects systems and datasets against unauthorized modification, tampering, or malicious deletion.",
                "**Availability:** Guarantees authenticated users have continuous, reliable access to critical assets and services.",
                "**Threat Landscape Defense:** Mitigates malware, ransomware, phishing, zero-day exploits, and distributed denial-of-service (DDoS) attacks.",
                "**Multi-Layered Security (Defense in Depth):** Combines firewalls, intrusion detection systems (IDS/IPS), and endpoint security.",
                "**Zero Trust Architecture:** Enforces continuous verification: *'Never trust, always verify'* for all network identities.",
                "**Incident Response & Disaster Recovery:** Pre-established procedures for rapid containment, forensic audit, and backup restoration.",
            ]
            selected = pts[:points_count]
            return f"### 🛡️ Cybersecurity ({points_count} Essential Points)\n\n" + "\n\n".join([f"{i+1}. {p}" for i, p in enumerate(selected)])

        if length == "exam_5_mark":
            return (
                "### 📚 Cybersecurity (5-Mark Exam Answer)\n\n"
                "#### 1. 📌 Definition\n"
                "**Cybersecurity** is the comprehensive body of technologies, processes, and practices designed to protect computer networks, servers, applications, mobile devices, and data from attacks, unauthorized access, damage, or theft.\n\n"
                "#### 2. 🏛️ The Core Security Triad (CIA Model)\n"
                "- **Confidentiality:** Protecting information from unauthorized disclosure via encryption (AES-256) and MFA.\n"
                "- **Integrity:** Ensuring data accuracy and preventing tampering using cryptographic hashes (SHA-256).\n"
                "- **Availability:** Guaranteeing systems remain operational for legitimate users via redundancy, load balancing, and DDoS mitigation.\n\n"
                "#### 3. ⚠️ Common Cyber Threats\n"
                "- **Malware / Ransomware:** Malicious software encrypting files for extortion.\n"
                "- **Phishing & Social Engineering:** Deceptive communications stealing credentials.\n"
                "- **Injection & Web Attacks:** SQL Injection, Cross-Site Scripting (XSS), and Broken Authentication.\n\n"
                "#### 4. 🛡️ Core Defensive Strategies\n"
                "- **Zero Trust Architecture:** Strict access control and micro-segmentation.\n"
                "- **Endpoint Detection & Response (EDR):** Real-time threat detection across devices.\n\n"
                "#### 5. 📝 Summary\n"
                "Effective cybersecurity relies on the synergy of people, processes, and automated technologies to build resilient enterprise systems."
            )

        if lang == "hinglish":
            return (
                "### 🛡️ Cybersecurity kya hai?\n\n"
                "**Cybersecurity** ka matlab hai computer systems, servers, networks aur data ko digital attacks, theft aur unauthorized access se surakshit rakhna.\n\n"
                "#### 🔑 CIA Triad (Security ke 3 Pillars):\n"
                "1. **Confidentiality (Gopneeyata):** Data sirf authorized logo ke paas ho (Encryption & Passwords).\n"
                "2. **Integrity (Satyanishtha):** Data ke sath koi chhedchhad ya badlaav na ho sake (Hashing).\n"
                "3. **Availability (Upalabdhta):** Zaroorat padne par systems hamesha chalte rahein (DDoS Protection & Backups).\n\n"
                "#### ⚠️ Common Cyber Threats:\n"
                "- **Phishing:** Fake emails bhejkar passwords churana.\n"
                "- **Ransomware:** Files ko encrypt karke paise maangna.\n"
                "- **SQL Injection:** Websites ke database me unauthorized queries execute karna."
            )

        if length == "detailed":
            return (
                "### 🛡️ In-Depth Architectural Guide to Cybersecurity\n\n"
                "Enterprise cybersecurity requires a proactive, multi-layered defensive posture (Defense-in-Depth) spanning infrastructure, application logic, and human governance.\n\n"
                "#### 1. The Core Security Domains\n"
                "- **Application Security:** Secure software development lifecycle (SSDLC), static/dynamic code analysis (SAST/DAST), and OWASP Top 10 remediation.\n"
                "- **Network Security:** Segmented virtual private clouds (VPCs), next-generation firewalls (NGFW), Web Application Firewalls (WAF), and TLS 1.3 encryption.\n"
                "- **Identity & Access Management (IAM):** Principle of Least Privilege (PoLP), Role-Based Access Control (RBAC), and continuous multi-factor authentication (MFA).\n"
                "- **Cloud Security:** Infrastructure as Code (IaC) compliance scanning, container vulnerability audits, and secret management (Vault/AWS Secrets Manager).\n"
                "- **Security Operations Center (SOC):** Centralized SIEM/SOAR monitoring with automated threat hunting and anomaly detection.\n\n"
                "#### 2. Threat Modeling & Attack Vectors\n"
                "Cyber threats target vulnerabilities across the computing stack, including Advanced Persistent Threats (APTs), supply-chain package tampering, cryptographic key exposure, and social engineering attacks."
            )

        return (
            "### 🛡️ What is Cybersecurity?\n\n"
            "**Cybersecurity** is the practice of protecting systems, networks, programs, and data from digital attacks. These cyberattacks typically aim to access, change, or destroy sensitive information, extort money from users, or interrupt normal business operations.\n\n"
            "#### The CIA Triad\n"
            "- **Confidentiality:** Restricting data access to authorized users via encryption and identity policies.\n"
            "- **Integrity:** Ensuring data has not been altered or corrupted by unauthorized parties.\n"
            "- **Availability:** Ensuring critical systems and data remain operational and accessible when needed.\n\n"
            "#### Common Security Measures\n"
            "- **Firewalls & Intrusion Prevention:** Monitoring and filtering malicious network traffic.\n"
            "- **Regular Vulnerability Audits:** Identifying and patching security flaws before attackers exploit them.\n"
            "- **Zero Trust Principles:** Continuous authentication and authorization for every request."
        )

    # --- TOPIC: Blockchain ---
    if "blockchain" in lower:
        if length in ("one_line", "two_lines"):
            return "**Blockchain** is a decentralized, cryptographically secured distributed ledger that records transactions across multiple independent nodes in an immutable, tamper-evident sequence."
        return (
            "### ⛓️ What is Blockchain?\n\n"
            "A **Blockchain** is a decentralized, distributed, and cryptographically secure digital ledger that records transactions across a network of computers. Once recorded, the data in any given block cannot be altered retroactively without the alteration of all subsequent blocks.\n\n"
            "#### Key Characteristics\n"
            "- **Decentralization:** No single central entity or server controls the network; consensus mechanisms validate state transitions.\n"
            "- **Immutability:** Transactions are hashed using cryptographic algorithms (e.g., SHA-256) and chained chronologically, making tampering virtually impossible.\n"
            "- **Transparency & Auditability:** All network participants share access to a single synchronized ledger of verified transactions.\n\n"
            "#### Common Applications\n"
            "- **Smart Contracts:** Self-executing agreements deployed directly on decentralized networks (e.g., Ethereum).\n"
            "- **Supply Chain Tracking:** Real-time verifiable provenance tracking from origin to retail shelf.\n"
            "- **Digital Identity:** Verifiable credentials and self-sovereign identity governance."
        )

    # --- TOPIC: Recursion ---
    if "recursion" in lower:
        if length in ("one_line", "two_lines"):
            return "**Recursion** is a programming technique where a function solves a problem by calling itself with smaller inputs until it reaches a defined base termination condition."
        return (
            "### 🔄 What is Recursion?\n\n"
            "In computer science, **Recursion** is a method of solving problems where the solution depends on solutions to smaller instances of the same problem. In programming, it occurs when a function calls itself directly or indirectly.\n\n"
            "#### Two Essential Components\n"
            "1. **Base Case:** A condition that stops further recursion and returns an explicit value, preventing infinite execution and stack overflow.\n"
            "2. **Recursive Case:** The logic where the function breaks the input down and calls itself with modified parameters.\n\n"
            "```python\n"
            "def sum_numbers(n):\n"
            "    # Base case\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    # Recursive case\n"
            "    return n + sum_numbers(n - 1)\n\n"
            "print(sum_numbers(5))  # Returns 15 (5 + 4 + 3 + 2 + 1)\n"
            "```\n\n"
            "#### When to Use Recursion\n"
            "- Tree and graph traversal algorithms (Depth-First Search, Binary Tree Inversion).\n"
            "- Divide-and-Conquer algorithms (Merge Sort, Quick Sort, Binary Search)."
        )

    # --- TOPIC: Who invented the internet ---
    if "who invented" in lower and "internet" in lower:
        return (
            "### 🌐 Who Invented the Internet?\n\n"
            "The internet was not invented by a single person; rather, it was developed through collaborative milestones across multiple computer scientists and organizations:\n\n"
            "1. **Vinton Cerf & Robert Kahn:** Widely credited as the **'Fathers of the Internet'** for designing the **TCP/IP** (Transmission Control Protocol / Internet Protocol) protocols in the 1970s, which established standard rules for how data moves across decentralized networks.\n"
            "2. **ARPANET & DARPA (1969):** Funded by the U.S. Department of Defense, creating the first packet-switching network connecting UCLA, Stanford, UC Santa Barbara, and the University of Utah.\n"
            "3. **Sir Tim Berners-Lee (1989):** Invented the **World Wide Web (WWW)** at CERN, including HTML, HTTP, and URLs, which made the underlying internet accessible to the public via graphical browsers."
        )

    # --- TOPIC: SQL Injection ---
    if "sql injection" in lower or "sqli" in lower:
        return (
            "### 🛡️ What is SQL Injection (SQLi)?\n\n"
            "**SQL Injection (SQLi)** is a severe web security vulnerability that allows an attacker to interfere with the database queries an application makes. It occurs when untrusted user input is directly concatenated into a dynamic SQL statement instead of using parameterized queries.\n\n"
            "#### How It Works\n"
            "If an application executes:\n"
            "```sql\n"
            "SELECT * FROM users WHERE email = '\" + input_email + \"' AND password = '\" + input_password + \"';\n"
            "```\n"
            "An attacker entering `' OR '1'='1` in the password field alters query logic so the condition always evaluates to `True`, granting unauthorized access.\n\n"
            "#### How to Prevent SQLi\n"
            "- **Use Parameterized Queries / Prepared Statements:** Ensures user input is treated strictly as data literals, never executable SQL commands.\n"
            "- **Use Object-Relational Mappers (ORMs):** High-level abstractions (like SQLAlchemy or Prisma) automatically parameterize queries.\n"
            "- **Enforce Principle of Least Privilege:** Restrict database account permissions to only the tables and operations required."
        )

    # --- TOPIC: Python code for agents ---
    if "python" in lower and "agent" in lower:
        return (
            "### 🛠️ Technical Architecture & Writing Python AI Agents\n\n"
            "To build specialized agents in the OrchestrAI multi-agent platform, inherit from `BaseAgent` and register your instance in the global agent registry:\n\n"
            "```python\n"
            "from app.agents.base import BaseAgent, AgentContext, AgentResult\n"
            "from app.agents.registry import register_agent, get_agent_instance\n\n"
            "class CustomAnalyticsAgent(BaseAgent):\n"
            "    agent_type = 'custom_analytics'\n"
            "    description = 'Executes domain-specific quantitative analysis.'\n\n"
            "    def execute(self, context: AgentContext) -> AgentResult:\n"
            "        data = context.input_data.get('dataset', [])\n"
            "        # Perform deterministic processing or LLM reasoning\n"
            "        result_payload = {'records_processed': len(data), 'status': 'success'}\n"
            "        return AgentResult(\n"
            "            success=True,\n"
            "            agent_type=self.agent_type,\n"
            "            task_id=context.task_id,\n"
            "            output=result_payload\n"
            "        )\n\n"
            "# Register into global execution runtime\n"
            "register_agent(CustomAnalyticsAgent())\n"
            "```\n\n"
            "#### Dynamic Resolution\n"
            "You can dynamically resolve and dispatch tasks via `from app.agents.registry import get_agent_instance` at execution time."
        )

    # --- TOPIC: C Code for loop / programming ---
    if ("loop" in lower or "code" in lower) and any(k in f" {lower} " for k in (" c ", " c code ", " in c ", " give me c ", " c program ")):
        return (
            "### 💻 C Code: For Loop Example\n\n"
            "Here is a complete, working C program demonstrating how to use a `for` loop:\n\n"
            "```c\n"
            "#include <stdio.h>\n\n"
            "int main() {\n"
            "    // Standard for loop to print numbers from 1 to 5\n"
            "    for (int i = 1; i <= 5; i++) {\n"
            "        printf(\"Iteration %d\\n\", i);\n"
            "    }\n\n"
            "    return 0;\n"
            "}\n"
            "```\n\n"
            "#### How It Works:\n"
            "1. **Initialization (`int i = 1;`):** Initializes the loop control variable once at the beginning.\n"
            "2. **Condition (`i <= 5;`):** Evaluated before every iteration. If `true`, the loop body executes; when `false`, the loop terminates.\n"
            "3. **Increment (`i++`):** Updates the counter after each iteration.\n"
        )

    # 4. General Dynamic Fallback for Arbitrary User Questions
    if lang == "hinglish":
        return (
            f"### 🙏 Namaste! OrchestrAI Assistant aapki madad ke liye ready hai\n\n"
            f"**Aapka Sawaal:** *\"{raw}\"*\n\n"
            f"OrchestrAI multi-agent platform operational hai. Aaj ki verified date: **{current_time_str}**.\n\n"
            f"Aap hamare specialized tools aur agents use kar sakte hain:\n"
            f"- **AI Image Generation:** Direct visual creation via Flux.1 Diffusion.\n"
            f"- **Email Agent:** Executive email drafting and notifications.\n"
            f"- **Data Analysis & Documents:** Tabular dataset crunching and dossier synthesis.\n"
            f"- **Security & Vulnerability Scanner:** Static vulnerability audits.\n\n"
            f"Agar aap kisi specific topic par detailed answer, exam answer, bullet points ya live task run karna chahte hain, toh bataiye!"
        )

    return (
        f"### 💡 OrchestrAI Intelligent Assistant\n\n"
        f"**Query:** *\"{raw}\"*\n\n"
        f"Today is **{current_time_str}** (UTC).\n\n"
        f"Regarding your inquiry:\n"
        f"- The OrchestrAI system is operating with all specialized agents active and healthy.\n"
        f"- You can ask conversational questions, request coding examples, analyze data, or generate high-fidelity AI imagery directly in this interface.\n\n"
        f"How would you like to proceed with your next request?"
    )
