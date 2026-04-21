"""
main.py — Application entry point.
Gunicorn points here in production. Run directly for local dev.
"""

import os
from dotenv import load_dotenv

# Load .env variables before importing anything else
load_dotenv()

from app.api import app
from app.config import HOST, PORT, DEBUG

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
