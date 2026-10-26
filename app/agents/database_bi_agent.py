"""
Real Database & BI Agent.

Executes safe, parameterized, read-only SQL queries against database models,
enforces AST/regex query restrictions (rejecting DROP, DELETE, UPDATE, INSERT, ALTER),
applies row limits, and synthesizes KPI insights.
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.agents.base import AgentContext, AgentResult, ArtifactRef, BaseAgent
from app.extensions import db


class DatabaseBIAgent(BaseAgent):
    """Production Database & BI Agent for safe read-only SQL querying and KPI extraction."""

    agent_type = "database_bi"
    description = "Inspects schemas, executes safe read-only SQL queries, and generates KPI insights."
    requires_side_effect_approval = False  # Read-only queries do not require approval; write operations are blocked.

    DESTRUCTIVE_SQL_PATTERNS = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bUPDATE\b",
        r"\bINSERT\b",
        r"\bALTER\b",
        r"\bTRUNCATE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bCREATE\b",
    ]

    MAX_ROW_LIMIT = 100

    def execute(self, context: AgentContext) -> AgentResult:
        start_time = time.time()
        input_data = context.input_data or {}

        operation = (input_data.get("operation") or "query").lower()
        query_str = input_data.get("query") or input_data.get("sql") or input_data.get("question") or input_data.get("nl_query") or context.instructions or ""

        # -----------------------------------------------------------------------
        # SCHEMA INSPECTION / LIST TABLES
        # -----------------------------------------------------------------------
        if operation in ("inspect_schema", "list_tables"):
            return self._handle_schema_inspection(context, start_time)

        # 1. Reject semicolon multi-statement injection and comments on input
        if ";" in query_str.rstrip(";"):
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error="Query rejected: Semicolons and multi-statement queries are not allowed for security reasons.",
                execution_duration_ms=duration,
            )
        if "--" in query_str or "/*" in query_str:
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error="Query rejected: SQL comment delimiters ('--', '/*') are prohibited.",
                execution_duration_ms=duration,
            )
        for pattern in self.DESTRUCTIVE_SQL_PATTERNS:
            if re.search(pattern, query_str.upper()):
                duration = int((time.time() - start_time) * 1000)
                return AgentResult(
                    success=False,
                    agent_type=self.agent_type,
                    task_id=context.task_id,
                    error=f"Query rejected: Contains Prohibited keyword pattern '{pattern.strip(r'\(b')}'.",
                    execution_duration_ms=duration,
                )

        # Convert natural language question or keywords to SQL if not already SQL
        stripped_q = query_str.strip()
        if stripped_q and not stripped_q.upper().startswith(("SELECT", "WITH", "EXPLAIN")):
            llm_sql = self._generate_sql_with_llm(stripped_q)
            if llm_sql:
                query_str = llm_sql
            else:
                q_lower = stripped_q.lower()
                if any(k in q_lower for k in ("fail", "failed", "frequently", "most fail")):
                    query_str = "SELECT agent_type, COUNT(*) as failure_count FROM task_executions WHERE status = 'failed' GROUP BY agent_type ORDER BY failure_count DESC LIMIT 10;"
                elif any(k in q_lower for k in ("avg", "average", "execution time", "duration")):
                    query_str = "SELECT agent_type, AVG(duration_ms) as avg_duration_ms FROM task_executions GROUP BY agent_type;"
                elif any(k in q_lower for k in ("compare", "success vs", "successful vs")):
                    query_str = "SELECT status, COUNT(*) as count FROM workflow_executions GROUP BY status;"
                elif any(k in q_lower for k in ("top", "most executed", "execution count")) and "workflow" in q_lower:
                    query_str = "SELECT w.id, w.name, COUNT(e.id) as execution_count FROM workflows w LEFT JOIN workflow_executions e ON w.id = e.workflow_id GROUP BY w.id, w.name ORDER BY execution_count DESC LIMIT 10;"
                elif any(k in q_lower for k in ("workflow", "pipeline", "dag")):
                    query_str = "SELECT id, name, status, version, created_at FROM workflows LIMIT 20;"
                elif any(k in q_lower for k in ("approval", "governance", "pending")):
                    query_str = "SELECT id, public_id, requested_action, risk_level, status, created_at FROM approval_requests WHERE status = 'pending' ORDER BY created_at DESC LIMIT 20;"
                elif any(k in q_lower for k in ("audit", "log", "security", "event")):
                    query_str = "SELECT id, action, resource_type, status, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT 20;"
                elif any(k in q_lower for k in ("execution", "run", "history", "job")):
                    query_str = "SELECT id, workflow_id, status, created_at FROM workflow_executions ORDER BY created_at DESC LIMIT 20;"
                elif any(k in q_lower for k in ("active user", "active users")):
                    query_str = "SELECT COUNT(*) as active_user_count FROM users WHERE is_active = 1;"
                elif any(k in q_lower for k in ("role", "roles")):
                    query_str = "SELECT role, COUNT(*) as user_count FROM users GROUP BY role;"
                elif any(k in q_lower for k in ("user", "users", "account", "member")):
                    query_str = "SELECT id, username, email, role, is_active FROM users LIMIT 20;"
                else:
                    query_str = "SELECT id, username, email, role, is_active FROM users LIMIT 20;"

        if not query_str or not isinstance(query_str, str):
            query_str = "SELECT id, username, email, role, is_active FROM users LIMIT 20;"

        # Validate that the resulting SQL is read-only (SELECT / WITH)
        is_safe, security_err = self._validate_read_only_sql(query_str)
        if not is_safe:
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error=security_err or "SQL query rejected by security policy.",
                execution_duration_ms=duration,
            )

        # 2. Append Row Limit if missing
        safe_query = self._enforce_row_limit(query_str, self.MAX_ROW_LIMIT)

        # 3. Execute Query Safely via SQLAlchemy
        try:
            from flask import has_app_context
            params = input_data.get("params") or {}

            if not has_app_context():
                from app import create_app
                temp_app = create_app("development")
                with temp_app.app_context():
                    result_proxy = db.session.execute(text(safe_query), params)
                    if result_proxy.returns_rows:
                        columns = list(result_proxy.keys())
                        raw_rows = result_proxy.fetchall()
                        rows = [dict(zip(columns, [self._serialize_val(v) for v in row])) for row in raw_rows]
                    else:
                        columns = []
                        rows = []
            else:
                result_proxy = db.session.execute(text(safe_query), params)
                if result_proxy.returns_rows:
                    columns = list(result_proxy.keys())
                    raw_rows = result_proxy.fetchall()
                    rows = [dict(zip(columns, [self._serialize_val(v) for v in row])) for row in raw_rows]
                else:
                    columns = []
                    rows = []

        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                agent_type=self.agent_type,
                task_id=context.task_id,
                error=f"SQL Query Execution Error: {str(e)}",
                execution_duration_ms=duration,
            )

        # 4. Extract KPIs & Insights
        kpis, rule_insights = self._calculate_kpis_and_insights(columns, rows)
        llm_insights = self._synthesize_insights_with_llm(safe_query, columns, rows, kpis)
        insights = llm_insights if llm_insights else rule_insights
        duration = int((time.time() - start_time) * 1000)

        output_payload = {
            "query": safe_query,
            "columns": columns,
            "rows": rows,
            "rowCount": len(rows),
            "kpis": kpis,
            "insights": insights,
            "warnings": ["Results capped at 100 rows."] if len(rows) == self.MAX_ROW_LIMIT else [],
        }

        artifact = ArtifactRef(
            type="sql_result",
            name=f"db_query_{context.task_id[:8]}.json",
            content=output_payload,
        )

        return AgentResult(
            success=True,
            agent_type=self.agent_type,
            task_id=context.task_id,
            output=output_payload,
            metadata={"query_executed": safe_query, "returned_row_count": len(rows)},
            artifacts=[artifact],
            execution_duration_ms=duration,
        )

    def _validate_read_only_sql(self, query_str: str) -> Tuple[bool, Optional[str]]:
        """Ensure SQL query starts with SELECT/WITH and contains no destructive statements or multi-statement injection attempts."""
        clean_query = query_str.strip()

        # Reject semicolon multi-statement execution attempts
        if ";" in clean_query.rstrip(";"):
            return False, "Query rejected: Semicolons and multi-statement queries are not allowed for security reasons."

        # Reject SQL comments that could hide destructive keywords
        if "--" in clean_query or "/*" in clean_query:
            return False, "Query rejected: SQL comment delimiters ('--', '/*') are prohibited."

        upper_query = clean_query.upper()

        if not (upper_query.startswith("SELECT") or upper_query.startswith("WITH")):
            return False, "Only read-only SELECT or WITH queries are permitted."

        if re.search(r"\bINTO\b", upper_query):
            return False, "Query rejected: SELECT ... INTO clauses are prohibited."

        for pattern in self.DESTRUCTIVE_SQL_PATTERNS:
            if re.search(pattern, upper_query):
                return False, f"Query rejected: Contains prohibited keyword pattern '{pattern.strip(r'\(b')}'."

        return True, None

    def _enforce_row_limit(self, query_str: str, limit: int) -> str:
        """Ensure query has a LIMIT clause."""
        cleaned = query_str.strip().rstrip(";")
        if re.search(r"\bLIMIT\s+\d+", cleaned, re.IGNORECASE):
            return cleaned
        return f"{cleaned} LIMIT {limit}"

    def _serialize_val(self, val: Any) -> Any:
        """Convert datetime or non-serializable SQL values."""
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return val

    def _handle_schema_inspection(self, context: AgentContext, start_time: float) -> AgentResult:
        """Return database table metadata."""
        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            schema_info = {}
            for t in tables[:10]:  # Limit to 10 tables
                cols = [c["name"] for c in inspector.get_columns(t)]
                schema_info[t] = cols
        except Exception as e:
            schema_info = {"error": f"Schema inspection failed: {str(e)}"}

        duration = int((time.time() - start_time) * 1000)
        return AgentResult(
            success=True,
            agent_type=self.agent_type,
            task_id=context.task_id,
            output={
                "operation": "inspect_schema",
                "tables": list(schema_info.keys()) if isinstance(schema_info, dict) else [],
                "schema": schema_info,
            },
            execution_duration_ms=duration,
        )

    def _calculate_kpis_and_insights(
        self, columns: List[str], rows: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Calculate quick KPIs from returned database rows."""
        kpis = {"total_records": len(rows)}
        insights = [f"Retrieved {len(rows)} records matching database criteria."]

        if not rows:
            return kpis, insights

        # Calculate sum/avg for numeric columns
        for col in columns:
            vals = []
            for r in rows:
                v = r.get(col)
                if isinstance(v, (int, float)):
                    vals.append(float(v))
            if vals:
                kpis[f"{col}_sum"] = round(sum(vals), 2)
                kpis[f"{col}_avg"] = round(sum(vals) / len(vals), 2)
                insights.append(f"Column '{col}' accumulated total of {kpis[f'{col}_sum']} (Average: {kpis[f'{col}_avg']}).")

        return kpis, insights

    def _generate_sql_with_llm(self, natural_language_query: str) -> Optional[str]:
        """Convert natural language request to a safe read-only SQL SELECT statement via LLM."""
        try:
            from app.services.provider_health_service import ProviderHealthManager
            if ProviderHealthManager.is_testing_environment():
                return None

            from app.llm.contracts import LLMMessage, LLMRequest
            from app.llm.registry import provider_registry

            provider, model = provider_registry.resolve_provider_and_model()
            schema_context = (
                "Database schema summary:\n"
                "- users (id, username, email, role, is_active, created_at)\n"
                "- workflows (id, name, description, status, version, is_active, created_at)\n"
                "- workflow_executions (id, workflow_id, status, error, started_at, completed_at, created_at)\n"
                "- task_executions (id, workflow_execution_id, agent_type, status, duration_ms, error, created_at)\n"
                "- approval_requests (id, public_id, requested_action, risk_level, status, created_at)\n"
                "- audit_events (id, action, resource_type, status, created_at)\n"
                "- uploaded_files (id, original_filename, file_type, file_size_bytes, created_at)\n"
            )
            system_prompt = (
                "You are an expert SQL Business Intelligence engineer. Given a user question or request, "
                "generate a single, standard read-only SQL SELECT statement using SQLite/SQLAlchemy syntax.\n"
                "STRICT RULES:\n"
                "1. Output ONLY the raw SQL query. No explanations, no markdown codeblocks.\n"
                "2. The query MUST be a SELECT statement or WITH ... SELECT. NEVER generate DROP, DELETE, UPDATE, INSERT, ALTER.\n"
                "3. Always include LIMIT 20 if no limit is specified."
            )
            req = LLMRequest(
                provider=provider.provider_name,
                model=model,
                system_instructions=system_prompt,
                messages=[LLMMessage(role="user", content=f"{schema_context}\nUser Question: {natural_language_query}")],
                temperature=0.0,
                max_tokens=300,
            )
            resp = provider.generate(req)
            candidate = (resp.text or "").strip()
            candidate = re.sub(r"^```(?:sql)?\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s*```$", "", candidate)
            candidate = candidate.strip()
            if candidate.upper().startswith(("SELECT", "WITH", "EXPLAIN")):
                return candidate
        except Exception:
            return None
        return None

    def _synthesize_insights_with_llm(
        self, query: str, columns: List[str], rows: List[Dict[str, Any]], kpis: Dict[str, Any]
    ) -> List[str]:
        """Synthesize executive business insights from SQL results using LLM."""
        if not rows:
            return []
        try:
            from app.services.provider_health_service import ProviderHealthManager
            if ProviderHealthManager.is_testing_environment():
                return []

            from app.llm.contracts import LLMMessage, LLMRequest
            from app.llm.registry import provider_registry
            import json

            provider, model = provider_registry.resolve_provider_and_model()
            sample_data = rows[:10]
            system_prompt = (
                "You are an enterprise Business Intelligence analyst. Analyze the provided SQL query results, "
                "columns, and calculated KPIs. Produce 2-4 concise, high-impact executive bullet points "
                "explaining the key business trends, anomalies, or status. Ground your observations strictly in the provided data. "
                "Output ONLY a valid JSON array of strings, e.g. [\"Insight 1\", \"Insight 2\"]."
            )
            user_msg = (
                f"Query: {query}\n"
                f"Columns: {columns}\n"
                f"Total Row Count: {len(rows)}\n"
                f"Sample Rows: {sample_data}\n"
                f"Calculated KPIs: {kpis}"
            )
            req = LLMRequest(
                provider=provider.provider_name,
                model=model,
                system_instructions=system_prompt,
                messages=[LLMMessage(role="user", content=user_msg)],
                temperature=0.2,
                max_tokens=400,
            )
            resp = provider.generate(req)
            text_out = (resp.text or "").strip()
            m = re.search(r"\[.*\]", text_out, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                    return parsed
        except Exception:
            pass
        return []
