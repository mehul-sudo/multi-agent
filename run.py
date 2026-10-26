"""
Development entrypoint.

This file only loads environment variables and starts the app created
by the factory. All application logic lives inside app/, not here.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (import after load_dotenv on purpose)

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_RUN_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_RUN_PORT", 5000)),
        debug=app.config.get("DEBUG", False),
        use_reloader=False,
    )
