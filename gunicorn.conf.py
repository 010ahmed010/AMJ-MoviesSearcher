import multiprocessing
import os

bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_class = "gthread"
worker_tmp_dir = "/dev/shm"
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = True
wsgi_app = "app:app"

def when_ready(server):
    server.log.info("AMJ-MoviesSearcher is ready to accept requests.")
