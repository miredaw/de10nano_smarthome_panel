#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start.sh  —  Smart Home Dashboard startup script
#
# Flask-SocketIO in 'threading' async_mode is best served by its own
# built-in server.  Gunicorn workers (gthread/gevent/eventlet) all have
# compatibility issues with paho-mqtt background threads.
#
# The built-in server is safe here because:
#   • FLASK_DEBUG=False   → no debugger, no Werkzeug reloader
#   • use_reloader=False  → single process, no duplicate MQTT client
#
# Usage:
#   ./start.sh          (foreground, logs to terminal)
#   ./start.sh &        (background)
# ---------------------------------------------------------------------------

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if present
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
fi

echo "==> Starting Smart Home Dashboard"
python app_with_auth.py
