# gunicorn/prod.py
"""Gunicorn *production* config file

Production settings optimized for Cloud Run:
- Dynamic worker count based on available CPUs
- Preload app to share memory between workers
- No migrations here (run via separate Cloud Run Job)
"""

import multiprocessing
import os

# FastAPI ASGI application path
wsgi_app = "app.main:app"

# Logging
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
accesslog = errorlog = "-"  # Log to stdout/stderr for Docker
capture_output = True

# Concurrency and Workers
# Cloud Run provides 1 vCPU by default, but can be configured up to 8
# Formula: (2 x num_cores) + 1 is a good starting point for I/O bound apps
# WEB_CONCURRENCY env var allows override for fine-tuning
_cpu_count = multiprocessing.cpu_count()
_default_workers = (_cpu_count * 2) + 1
workers = int(os.getenv("WEB_CONCURRENCY", _default_workers))

# Use Uvicorn worker for ASGI support
worker_class = "uvicorn.workers.UvicornWorker"

# Max simultaneous connections per worker
worker_connections = int(os.getenv("WORKER_CONNECTIONS", "1000"))

# Request timeout (Cloud Run has max 3600s)
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# Graceful timeout for worker shutdown
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Preload application code before forking workers
# This shares memory between workers and catches startup errors early
preload_app = True

# Production settings
reload = False
daemon = False


# Worker lifecycle hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    import logging

    logging.info(f"🚀 Starting Gunicorn with {workers} workers (CPUs: {_cpu_count})")


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    import logging

    logging.info(f"👷 Worker {worker.pid} spawned")


def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    import logging

    logging.info(f"👋 Worker {worker.pid} exited")
