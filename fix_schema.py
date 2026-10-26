"""
Recreate approval_requests table matching the SQLAlchemy model exactly.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.extensions import db
from app.models.approval_request import ApprovalRequest

def fix_schema():
    app = create_app("development")
    with app.app_context():
        # Drop and recreate approval_requests using db.metadata
        ApprovalRequest.__table__.drop(db.engine, checkfirst=True)
        ApprovalRequest.__table__.create(db.engine)
        print("Successfully recreated approval_requests table matching model!")

if __name__ == "__main__":
    fix_schema()
