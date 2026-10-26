"""UploadedFile model for unified, secure file uploads."""

import uuid
from datetime import datetime, timezone

from app.extensions import db


class UploadedFile(db.Model):
    """Stores metadata and verified server storage path for user uploaded files."""

    __tablename__ = "uploaded_files"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    filename = db.Column(db.String(255), nullable=False)
    extension = db.Column(db.String(16), nullable=False)
    mime_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    storage_path = db.Column(db.String(512), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    metadata_json = db.Column(db.JSON, nullable=True, default=dict)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    owner = db.relationship("User", backref=db.backref("uploaded_files", lazy="dynamic", cascade="all, delete-orphan"))

    def to_dict(self) -> dict:
        return {
            "file_id": self.public_id,
            "filename": self.filename,
            "extension": self.extension,
            "mime_type": self.mime_type,
            "size": self.size_bytes,
            "owner_id": self.owner_id,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
