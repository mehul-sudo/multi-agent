import json
import time
import queue
from datetime import datetime
from flask import Blueprint, Response, request, jsonify
from flask_jwt_extended import decode_token
from app.models.workflow_execution import WorkflowExecution
from app.models.task_execution import TaskExecution
from app.extensions import db

streaming_bp = Blueprint('streaming_bp', __name__)

# Persistent in-memory log history & active subscribers per job_id
# Format: { job_id: {"history": [...], "subscribers": [queue.Queue(), ...]} }
_log_stores = {}


def emit_execution_log(job_id, event_type, data):
    """
    Push a log event to the in-memory buffer and notify all active subscribers.
    Handles message formatting so frontend terminal displays cleanly.
    """
    if not job_id:
        return
    job_key = str(job_id)
    if job_key not in _log_stores:
        _log_stores[job_key] = {"history": [], "subscribers": []}

    # Ensure timestamp and message format
    if isinstance(data, dict):
        if "timestamp" not in data:
            data["timestamp"] = datetime.utcnow().isoformat()
        if "message" not in data:
            if event_type == "task_start":
                data["message"] = f"Starting task: {data.get('task_name', 'Unknown Task')} ({data.get('agent_type', 'agent')})"
            elif event_type == "task_complete":
                data["message"] = f"Task completed successfully: {data.get('task_name', 'Task')} ({data.get('duration', 0)}ms)"
            elif event_type == "task_skipped":
                data["message"] = f"Task skipped by dependency rule: {data.get('task_name', 'Task')}"
            elif event_type == "task_error":
                data["message"] = f"Task error in '{data.get('task_name', 'Task')}': {data.get('error', 'Error')}"
            elif event_type == "execution_paused":
                data["message"] = f"Execution PAUSED: Waiting for human approval on '{data.get('task_name', 'Task')}'"
            elif event_type == "execution_start":
                data["message"] = f"Workflow Execution initiated (Job: {job_key[:12]}...)"
            elif event_type == "execution_complete":
                data["message"] = f"Workflow Execution finished with status: {data.get('status', 'completed')}"

    event_entry = {
        "event": event_type,
        "data": json.dumps(data)
    }
    _log_stores[job_key]["history"].append(event_entry)

    for sub in list(_log_stores[job_key]["subscribers"]):
        try:
            sub.put_nowait(event_entry)
        except Exception:
            pass


@streaming_bp.route('/execution-stream/<job_id>', methods=['GET'])
def execution_stream(job_id):
    """
    SSE endpoint that streams execution logs in real-time.
    Supports token via query parameter ?token= (required for EventSource) or Bearer header.
    Replays full log history for already-completed or in-progress jobs.
    """
    token = request.args.get('token')
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()

    if not token:
        return jsonify({"error": {"code": "TOKEN_MISSING", "message": "Authentication token is required."}}), 401

    try:
        decode_token(token)
    except Exception as e:
        return jsonify({"error": {"code": "TOKEN_INVALID", "message": f"Invalid token: {str(e)}"}}), 401

    job_key = str(job_id)
    if job_key not in _log_stores:
        _log_stores[job_key] = {"history": [], "subscribers": []}

    # REPLAY RECONSTRUCTION: If memory buffer is empty, rebuild history from database execution record
    if not _log_stores[job_key]["history"]:
        execution = None
        if len(job_key) == 36 and "-" in job_key:
            execution = WorkflowExecution.query.filter_by(public_id=job_key).first()
        elif job_key.isdigit():
            execution = WorkflowExecution.query.get(int(job_key))

        if execution:
            emit_execution_log(job_key, "execution_start", {
                "message": f"Execution started for workflow: {execution.workflow.name if execution.workflow else 'Workflow'}",
                "timestamp": execution.started_at.isoformat() if execution.started_at else datetime.utcnow().isoformat()
            })
            for te in execution.task_executions:
                node_name = te.workflow_node.name if te.workflow_node else f"Task #{te.id}"
                agent_type = te.workflow_node.agent.agent_type if (te.workflow_node and te.workflow_node.agent) else "agent"
                emit_execution_log(job_key, "task_start", {
                    "task_name": node_name,
                    "agent_type": agent_type,
                    "timestamp": te.started_at.isoformat() if te.started_at else datetime.utcnow().isoformat()
                })
                if te.status in ("completed", "succeeded"):
                    out_summary = ""
                    if isinstance(te.output_data, dict):
                        out_summary = te.output_data.get("status") or te.output_data.get("summary") or ""
                    emit_execution_log(job_key, "task_complete", {
                        "task_name": node_name,
                        "agent_type": agent_type,
                        "success": True,
                        "duration": te.duration_ms or 120,
                        "message": f"Task '{node_name}' finished successfully. {out_summary}",
                        "timestamp": te.completed_at.isoformat() if te.completed_at else datetime.utcnow().isoformat()
                    })
                elif te.status in ("blocked", "paused"):
                    emit_execution_log(job_key, "execution_paused", {
                        "task_name": node_name,
                        "agent_type": agent_type,
                        "message": f"Task '{node_name}' required human approval before proceeding.",
                        "timestamp": te.started_at.isoformat() if te.started_at else datetime.utcnow().isoformat()
                    })
                elif te.status == "failed":
                    err_text = ""
                    if isinstance(te.error_data, dict):
                        err_text = te.error_data.get("error", "Error")
                    emit_execution_log(job_key, "task_error", {
                        "task_name": node_name,
                        "agent_type": agent_type,
                        "error": err_text or "Task execution failed",
                        "timestamp": te.completed_at.isoformat() if te.completed_at else datetime.utcnow().isoformat()
                    })

            if execution.status in ("completed", "succeeded"):
                emit_execution_log(job_key, "execution_complete", {
                    "status": execution.status,
                    "message": "Workflow Execution completed successfully.",
                    "timestamp": execution.completed_at.isoformat() if execution.completed_at else datetime.utcnow().isoformat()
                })

    def generate():
        client_q = queue.Queue()
        _log_stores[job_key]["subscribers"].append(client_q)

        # 1. Immediately yield all historical log events for this execution
        for item in _log_stores[job_key]["history"]:
            yield f"event: {item['event']}\ndata: {item['data']}\n\n"

        last_heartbeat = time.time()
        try:
            while True:
                try:
                    event_data = client_q.get(timeout=1.0)
                    yield f"event: {event_data['event']}\ndata: {event_data['data']}\n\n"
                except queue.Empty:
                    if time.time() - last_heartbeat > 15:
                        yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"
                        last_heartbeat = time.time()
        except GeneratorExit:
            pass
        finally:
            if client_q in _log_stores[job_key]["subscribers"]:
                _log_stores[job_key]["subscribers"].remove(client_q)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )
