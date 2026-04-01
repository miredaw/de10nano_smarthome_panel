"""
WSGI entry point for production deployment with Gunicorn + gthread.

Flask-SocketIO is configured with async_mode='threading', so the correct
gunicorn worker is 'gthread' — no monkey-patching needed.

Usage:
    gunicorn --worker-class gthread -w 1 --threads 4 \
             --bind 0.0.0.0:4500                      \
             --timeout 120                            \
             wsgi:application

Notes:
  - Use exactly ONE worker (-w 1).
    Multiple workers each create their own MQTT client and their own
    SocketIO room space, which breaks real-time broadcasting.
  - --threads 4 lets gunicorn serve concurrent HTTP/WS requests within
    that single worker.
"""

from app_with_auth import app   # noqa: E402

application = app               # gunicorn looks for 'application' by default
