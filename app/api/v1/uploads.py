import os
from flask import Blueprint, request, current_app, jsonify, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models.user import User
from app.models.uploaded_file import UploadedFile
from app.services.file_service import FileService

uploads_bp = Blueprint('uploads_bp', __name__)


def _get_current_user():
    try:
        public_id = get_jwt_identity()
        if public_id:
            return User.query.filter_by(public_id=public_id).first()
    except Exception:
        pass
    return None


@uploads_bp.route('/uploads', methods=['POST'])
@jwt_required(optional=True)
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    user = _get_current_user()
    user_id = user.id if user else None

    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    uploaded, err = FileService.save_uploaded_file(file, upload_dir, user_id=user_id)

    if err or not uploaded:
        return jsonify({"error": err or "Failed to upload file"}), 400

    return jsonify({
        "file_id": uploaded.public_id,
        "filename": uploaded.filename,
        "size": uploaded.size_bytes,
        "content_type": uploaded.mime_type,
        "preview": (uploaded.metadata_json or {}).get("preview"),
        "upload_url": f"/api/v1/uploads/download/{uploaded.public_id}",
        "created_at": uploaded.created_at.isoformat() if uploaded.created_at else None,
    }), 201


@uploads_bp.route('/uploads', methods=['GET'])
@jwt_required()
def list_user_uploads():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401

    files = UploadedFile.query.filter_by(owner_id=user.id).order_by(UploadedFile.created_at.desc()).limit(50).all()
    return jsonify({
        "files": [f.to_dict() for f in files]
    }), 200


@uploads_bp.route('/uploads/info/<file_id>', methods=['GET'])
@jwt_required()
def get_upload_info(file_id):
    user = _get_current_user()
    file_record, err = FileService.get_file_by_id(file_id, user_id=user.id if user else None)
    if err or not file_record:
        return jsonify({"error": err or "File not found"}), 404

    return jsonify(file_record.to_dict()), 200


@uploads_bp.route('/uploads/download/<file_id>', methods=['GET'])
@jwt_required()
def download_file_by_id(file_id):
    user = _get_current_user()
    file_record, err = FileService.get_file_by_id(file_id, user_id=user.id if user else None)
    if err or not file_record:
        return jsonify({"error": err or "File not found"}), 404

    return send_file(file_record.storage_path, download_name=file_record.filename, as_attachment=True)


@uploads_bp.route('/uploads/<filename>', methods=['GET'])
def download_upload_legacy(filename):
    # Support backward-compatible direct filename download if within uploads dir
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    safe_path = os.path.abspath(os.path.join(upload_dir, filename))
    if not safe_path.startswith(os.path.abspath(upload_dir)) or not os.path.exists(safe_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(safe_path)


@uploads_bp.route('/reports/download/<filename>', methods=['GET', 'OPTIONS'])
def download_report(filename):
    if request.method == 'OPTIONS':
        resp = jsonify({"status": "ok"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "*"
        return resp

    import urllib.parse
    cleaned_fn = urllib.parse.unquote(filename).strip()
    cleaned_fn = os.path.basename(cleaned_fn)

    reports_dir = os.path.join(current_app.instance_path, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    safe_path = os.path.abspath(os.path.join(reports_dir, cleaned_fn))
    if not safe_path.startswith(os.path.abspath(reports_dir)) or not os.path.exists(safe_path):
        return jsonify({"error": f"Report file '{cleaned_fn}' not found"}), 404

    ext = os.path.splitext(safe_path)[1].lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".html": "text/html; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }
    mimetype = mime_map.get(ext, "application/octet-stream")

    resp = send_file(
        safe_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=os.path.basename(safe_path),
    )
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    resp.headers["Content-Disposition"] = f'attachment; filename="{os.path.basename(safe_path)}"'
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

